import time
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service as audit_service
from app.auth.dependencies import UserContext, get_current_user
from app.config import settings
from app.db.database import get_db
from app.db.models import ApprovalTask
from app.policies.engine import PolicyDecision, evaluate as policy_evaluate
from sqlalchemy import select
from app.rag.retrieval import retrieve

router = APIRouter(prefix="/query", tags=["Query"])

# Keywords that map to policy topic values
_TOPIC_MAP = {
    "data_protection": ["data protection", "gdpr", "dpa", "data subject", "data privacy"],
    "privacy":         ["privacy", "personal data", "pii", "personally identifiable"],
    "gdpr":            ["gdpr", "general data protection"],
    "personal_data":   ["personal data", "pii"],
    "credentials":     ["password", "passwords", "credential", "secret", "api key", "api_key"],
    "passwords":       ["password"],
    "secrets":         ["secret key", "access key"],
    "api_keys":        ["api key", "api_key"],
}


def _detect_topic(question: str) -> str | None:
    q = question.lower()
    for topic, keywords in _TOPIC_MAP.items():
        if any(kw in q for kw in keywords):
            return topic
    return None


def _max_sensitivity(chunks) -> str:
    rank = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
    if not chunks:
        return "public"
    return max((c.sensitivity for c in chunks), key=lambda s: rank.get(s, 0))


class QueryRequest(BaseModel):
    question: str
    source_systems: list[str] | None = None
    departments: list[str] | None = None
    max_sources: int = 8
    approved_task_id: str | None = None  # set on retry after approval


class Citation(BaseModel):
    id: int
    source_system: str
    document_name: str
    excerpt: str
    similarity: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    unauthorized_sources_filtered: int
    latency_ms: int
    approval_required: bool = False
    approval_task_id: str | None = None
    policy_name: str | None = None


@router.post("", response_model=QueryResponse)
async def query(
    body: QueryRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    start = time.monotonic()

    chunks, filtered_count = await retrieve(
        db,
        query=body.question,
        user=user,
        top_k=body.max_sources,
        source_systems=body.source_systems,
        departments=body.departments,
    )

    # Only consider chunks that are actually relevant (similarity >= 0.4)
    # Irrelevant low-similarity chunks should not drive the sensitivity level up
    RELEVANCE_THRESHOLD = 0.4
    relevant_chunks = [c for c in chunks if c.similarity >= RELEVANCE_THRESHOLD]

    # Build action_data for policy evaluation
    action_data = {
        "type": "rag_query",
        "max_sensitivity": _max_sensitivity(relevant_chunks),
        "question": body.question,
        "topic": _detect_topic(body.question),
        "cross_department": bool(
            relevant_chunks and user.department and
            any(c.source_system for c in relevant_chunks)
        ),
    }

    # If the caller supplies an approved_task_id, verify it and skip policy
    if body.approved_task_id:
        res = await db.execute(
            select(ApprovalTask).where(
                ApprovalTask.id == body.approved_task_id,
                ApprovalTask.tenant_id == user.tenant_id,
            )
        )
        task = res.scalar_one_or_none()
        if task and task.decision == "approve":
            # Policy already approved — jump straight to answer
            policy_result = None
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Approval task not found or not yet approved.",
            )
    else:
        policy_result = await policy_evaluate(db, action="rag_query", action_data=action_data, user=user)

    # ── DENY ──────────────────────────────────────────────────────────────────
    if policy_result and policy_result.decision == PolicyDecision.DENY:
        await audit_service.write_event(
            db,
            tenant_id=user.tenant_id,
            event_type="query_denied",
            user_id=user.user_id,
            payload={"question": body.question, "policy": policy_result.policy_name,
                     "reason": policy_result.reason},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Request blocked by policy '{policy_result.policy_name}': {policy_result.reason}",
        )

    # ── REQUIRE APPROVAL ──────────────────────────────────────────────────────
    if policy_result and policy_result.decision == PolicyDecision.REQUIRE_APPROVAL:
        task_id = str(uuid.uuid4())
        task = ApprovalTask(
            id=task_id,
            tenant_id=user.tenant_id,
            run_id=None,
            policy_id=policy_result.policy_id,
            requested_by=user.email,
            approver_role=policy_result.approver_role or "admin",
            proposed_action={
                "type": "rag_query",
                "question": body.question,
                "max_sensitivity": action_data["max_sensitivity"],
                "topic": action_data["topic"],
                "source_systems": body.source_systems,
            },
            evidence=[
                {"chunk_id": c.chunk_id, "document": c.document_name, "sensitivity": c.sensitivity}
                for c in relevant_chunks[:5]
            ],
            risk_class=("high" if action_data["max_sensitivity"] == "restricted" else "medium"),
            status="pending",
            sla_deadline=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(task)
        await audit_service.write_event(
            db,
            tenant_id=user.tenant_id,
            event_type="query_pending_approval",
            user_id=user.user_id,
            payload={"question": body.question, "policy": policy_result.policy_name,
                     "approval_task_id": task_id},
        )
        await db.commit()
        latency_ms = int((time.monotonic() - start) * 1000)
        return QueryResponse(
            answer=f"Your request requires approval from a **{policy_result.approver_role}** "
                   f"before it can be answered. Policy: *{policy_result.policy_name}*.",
            citations=[],
            unauthorized_sources_filtered=filtered_count,
            latency_ms=latency_ms,
            approval_required=True,
            approval_task_id=task_id,
            policy_name=policy_result.policy_name,
        )

    # ── ALLOW (or pre-approved retry) — generate answer ──────────────────────
    if not chunks:
        answer = "No authorized sources were found for your question."
        citations = []
    else:
        context = "\n\n".join(
            f"[{i}] {c.document_name} ({c.source_system}):\n{c.content}"
            for i, c in enumerate(chunks, 1)
        )
        llm = ChatOpenAI(
            model=settings.openai_llm_model,
            api_key=settings.openai_api_key,
            temperature=0,
        )
        prompt = (
            "Answer using ONLY the provided sources. Cite each with [1], [2], etc.\n\n"
            f"Sources:\n{context}\n\nQuestion: {body.question}\n\nAnswer:"
        )
        response = await llm.ainvoke(prompt)
        answer = response.content

        citations = [
            Citation(
                id=i,
                source_system=c.source_system,
                document_name=c.document_name,
                excerpt=c.content[:200],
                similarity=round(c.similarity, 3),
            )
            for i, c in enumerate(chunks, 1)
        ]

    latency_ms = int((time.monotonic() - start) * 1000)

    await audit_service.write_event(
        db,
        tenant_id=user.tenant_id,
        event_type="query",
        user_id=user.user_id,
        payload={
            "question": body.question,
            "chunks_used": len(chunks),
            "chunks_filtered": filtered_count,
            "latency_ms": latency_ms,
            "policy_decision": policy_result.decision if policy_result else "pre_approved",
        },
    )

    return QueryResponse(
        answer=answer,
        citations=citations,
        unauthorized_sources_filtered=filtered_count,
        latency_ms=latency_ms,
    )
