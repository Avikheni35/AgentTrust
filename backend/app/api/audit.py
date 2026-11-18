from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.service import get_receipt, verify_chain
from app.auth.dependencies import UserContext, get_current_user
from app.db.database import get_db
from app.db.models import AuditEvent

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/receipts")
async def list_receipts(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    event_type: str | None = Query(None),
    workflow: str | None = Query(None),
    agent_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.tenant_id == user.tenant_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if event_type:
        stmt = stmt.where(AuditEvent.event_type == event_type)
    if workflow:
        stmt = stmt.where(AuditEvent.workflow == workflow)
    if agent_id:
        stmt = stmt.where(AuditEvent.agent_id == agent_id)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/receipts/{run_id}")
async def get_run_receipt(
    run_id: str,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_receipt(db, run_id=run_id, tenant_id=user.tenant_id)


@router.get("/verify")
async def verify(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    valid = await verify_chain(db, tenant_id=user.tenant_id)
    return {"tenant_id": user.tenant_id, "chain_valid": valid}
