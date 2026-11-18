import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import run_agent
from app.auth.dependencies import UserContext, get_current_user
from app.db.database import get_db
from app.db.models import Agent, AgentRun

router = APIRouter(prefix="/agents", tags=["Agents"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    version: str = "1.0"
    owner: str
    purpose: str
    allowed_tools: list[str] = []
    forbidden_actions: list[str] = []
    required_approvals: list[str] = []
    data_scope: list[str] = []
    risk_class: str = "medium"
    max_tokens_per_call: int = 4000


class AgentRunRequest(BaseModel):
    request: str
    planned_action: dict | None = None


class AgentRunResponse(BaseModel):
    run_id: str
    status: str
    answer: str | None = None
    citations: list[dict] = []
    approval_task_id: str | None = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
async def list_agents(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Agent).where(Agent.tenant_id == user.tenant_id, Agent.is_active == True)
    )
    return result.scalars().all()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentCreate,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = Agent(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        **body.model_dump(),
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == user.tenant_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/{agent_id}/run", response_model=AgentRunResponse)
async def run(
    agent_id: str,
    body: AgentRunRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == user.tenant_id, Agent.is_active == True)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    run_id = str(uuid.uuid4())

    # Persist the run record
    agent_run = AgentRun(
        id=run_id,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        user_id=user.user_id,
        request=body.request,
        status="running",
    )
    db.add(agent_run)
    await db.commit()

    # Execute the LangGraph agent
    state = await run_agent(
        db=db,
        run_id=run_id,
        agent_id=agent_id,
        user=user,
        request=body.request,
        planned_action=body.planned_action,
    )

    # Update run record
    agent_run.status = state.status
    agent_run.answer = state.answer
    agent_run.citations = state.citations
    agent_run.completed_at = datetime.now(timezone.utc)
    if state.error:
        agent_run.error = state.error
    await db.commit()

    return AgentRunResponse(
        run_id=run_id,
        status=state.status,
        answer=state.answer or None,
        citations=state.citations,
        approval_task_id=state.approval_task_id,
    )


@router.get("/{agent_id}/runs/{run_id}")
async def get_run(
    agent_id: str,
    run_id: str,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.agent_id == agent_id,
            AgentRun.tenant_id == user.tenant_id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
