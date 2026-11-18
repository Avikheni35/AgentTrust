from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditEvent


async def write_event(
    db: AsyncSession,
    *,
    tenant_id: str,
    event_type: str,
    payload: dict,
    run_id: str | None = None,
    user_id: str | None = None,
    agent_id: str | None = None,
    workflow: str | None = None,
) -> AuditEvent:
    # Get the hash of the most recent event for this tenant (hash chain)
    result = await db.execute(
        select(AuditEvent.event_hash)
        .where(AuditEvent.tenant_id == tenant_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(1)
    )
    previous_hash = result.scalar_one_or_none() or "genesis"

    event = AuditEvent(
        tenant_id=tenant_id,
        run_id=run_id,
        user_id=user_id,
        agent_id=agent_id,
        event_type=event_type,
        workflow=workflow,
        payload=payload,
        previous_hash=previous_hash,
        created_at=datetime.now(timezone.utc),
    )
    event.event_hash = event.compute_hash()

    db.add(event)
    await db.commit()
    return event


async def get_receipt(db: AsyncSession, run_id: str, tenant_id: str) -> list[AuditEvent]:
    result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.run_id == run_id, AuditEvent.tenant_id == tenant_id)
        .order_by(AuditEvent.created_at)
    )
    return result.scalars().all()


async def verify_chain(db: AsyncSession, tenant_id: str, limit: int = 100) -> bool:
    result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.tenant_id == tenant_id)
        .order_by(AuditEvent.created_at)
        .limit(limit)
    )
    events = result.scalars().all()

    for event in events:
        expected = event.compute_hash()
        if event.event_hash != expected:
            return False
    return True
