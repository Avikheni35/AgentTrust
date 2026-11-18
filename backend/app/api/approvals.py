import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service as audit_service
from app.auth.dependencies import UserContext, get_current_user
from app.db.database import get_db
from app.db.models import ApprovalTask

router = APIRouter(prefix="/approvals", tags=["Approvals"])


class DecideRequest(BaseModel):
    decision: str   # approve | reject | escalate
    comment: str | None = None


@router.get("")
async def list_approvals(
    task_status: str | None = None,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ApprovalTask).where(ApprovalTask.tenant_id == user.tenant_id)

    # Non-admins only see tasks they can approve based on their roles
    if "admin" not in user.roles:
        stmt = stmt.where(ApprovalTask.approver_role.in_(user.roles))

    if task_status:
        stmt = stmt.where(ApprovalTask.status == task_status)

    stmt = stmt.order_by(ApprovalTask.created_at.desc())
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return [
        {
            "id": t.id,
            "tenant_id": t.tenant_id,
            "policy_id": t.policy_id,
            "approver_role": t.approver_role,
            "proposed_action": t.proposed_action,
            "evidence": t.evidence,
            "risk_class": t.risk_class,
            "status": t.status,
            "decision": t.decision,
            "decided_by": t.decided_by,
            "comment": t.comment,
            "sla_deadline": t.sla_deadline.isoformat() if t.sla_deadline else None,
            "created_at": t.created_at.isoformat(),
            "decided_at": t.decided_at.isoformat() if t.decided_at else None,
        }
        for t in tasks
    ]


@router.get("/mine")
async def my_requests(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Tasks submitted by the current user — so they can track their own request status."""
    result = await db.execute(
        select(ApprovalTask)
        .where(
            ApprovalTask.tenant_id == user.tenant_id,
            ApprovalTask.requested_by == user.email,
        )
        .order_by(ApprovalTask.created_at.desc())
    )
    tasks = result.scalars().all()
    return [
        {
            "id": t.id,
            "approver_role": t.approver_role,
            "proposed_action": t.proposed_action,
            "risk_class": t.risk_class,
            "status": t.status,
            "decision": t.decision,
            "decided_by": t.decided_by,
            "comment": t.comment,
            "sla_deadline": t.sla_deadline.isoformat() if t.sla_deadline else None,
            "created_at": t.created_at.isoformat(),
            "decided_at": t.decided_at.isoformat() if t.decided_at else None,
        }
        for t in tasks
    ]


@router.get("/{task_id}")
async def get_approval(
    task_id: str,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ApprovalTask).where(
            ApprovalTask.id == task_id,
            ApprovalTask.tenant_id == user.tenant_id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Approval task not found")
    return task


@router.post("/{task_id}/decide")
async def decide(
    task_id: str,
    body: DecideRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Normalise to verb form regardless of whether frontend sends past/present tense
    decision = body.decision.rstrip("d").replace("escalat", "escalate")
    if decision not in ("approve", "reject", "escalate"):
        raise HTTPException(status_code=400, detail="decision must be approve, reject, or escalate")

    result = await db.execute(
        select(ApprovalTask).where(
            ApprovalTask.id == task_id,
            ApprovalTask.tenant_id == user.tenant_id,
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Approval task not found")

    if task.status != "pending":
        raise HTTPException(status_code=409, detail=f"Task already in status '{task.status}'")

    # Role check: only the designated approver role (or admin) may decide
    if "admin" not in user.roles and task.approver_role not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{task.approver_role}' required to decide this task",
        )

    task.status = "decided"
    task.decision = decision
    task.decided_by = user.email
    task.comment = body.comment
    task.decided_at = datetime.now(timezone.utc)

    await audit_service.write_event(
        db,
        tenant_id=user.tenant_id,
        event_type=f"approval_{decision}d",
        user_id=user.user_id,
        payload={
            "task_id": task_id,
            "decision": body.decision,
            "comment": body.comment,
            "proposed_action": task.proposed_action,
        },
    )
    await db.commit()
    return {"task_id": task_id, "decision": body.decision, "status": "decided"}
