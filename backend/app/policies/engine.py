from dataclasses import dataclass
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import UserContext
from app.db.models import Policy


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class EvaluationResult:
    decision: PolicyDecision
    policy_id: str | None
    policy_name: str | None
    reason: str
    approver_role: str | None = None


def _evaluate_rule(rule: dict, action_data: dict) -> bool:
    field = rule.get("field", "")
    operator = rule.get("operator", "")
    value = rule.get("value")

    actual = action_data.get(field)
    if actual is None:
        return False

    value_list = value if isinstance(value, list) else [value]

    # When actual is a list (e.g. user.roles), check membership across the list
    if isinstance(actual, list):
        match operator:
            case "in":      return any(v in value_list for v in actual)
            case "not_in":  return not any(v in value_list for v in actual)
            case "contains": return any(str(value).lower() in str(v).lower() for v in actual)
            case _:         return False

    match operator:
        case "equals":        return actual == value
        case "not_equals":    return actual != value
        case "greater_than":  return float(actual) > float(value)
        case "less_than":     return float(actual) < float(value)
        case "in":            return actual in value_list
        case "not_in":        return actual not in value_list
        case "contains":      return str(value).lower() in str(actual).lower()
        case _:               return False


def _policy_matches(policy: Policy, action: str, action_data: dict, user: UserContext) -> bool:
    rules = policy.rules
    if rules.get("action") and rules["action"] != action:
        return False

    for rule in rules.get("conditions", []):
        source = rule.get("source", "action_data")
        if source == "user":
            data = {
                "role": user.roles,
                "department": user.department,
                "region": user.region,
            }
        else:
            data = action_data

        if not _evaluate_rule(rule, data):
            return False

    return True


async def evaluate(
    db: AsyncSession,
    action: str,
    action_data: dict[str, Any],
    user: UserContext,
) -> EvaluationResult:
    """Evaluate all active tenant policies and return the most restrictive decision."""
    result = await db.execute(
        select(Policy)
        .where(Policy.tenant_id == user.tenant_id, Policy.is_active == True)
        .order_by(Policy.priority.desc())
    )
    policies = result.scalars().all()

    for policy in policies:
        if _policy_matches(policy, action, action_data, user):
            decision = PolicyDecision(policy.decision)
            return EvaluationResult(
                decision=decision,
                policy_id=policy.id,
                policy_name=policy.name,
                reason=f"Policy '{policy.name}' matched",
                approver_role=policy.approver_role,
            )

    return EvaluationResult(
        decision=PolicyDecision.ALLOW,
        policy_id=None,
        policy_name=None,
        reason="No matching policy — default allow",
    )
