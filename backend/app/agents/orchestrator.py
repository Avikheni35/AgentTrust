from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import service as audit_service
from app.auth.dependencies import UserContext
from app.config import settings
from app.db.models import AgentRun
from app.policies.engine import PolicyDecision, evaluate as policy_evaluate
from app.rag.retrieval import RetrievedChunk, retrieve


@dataclass
class AgentState:
    run_id: str
    tenant_id: str
    agent_id: str
    user: UserContext
    request: str
    db: Any  # AsyncSession — not typed to avoid dataclass issues

    # Filled during run
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    filtered_count: int = 0
    answer: str = ""
    citations: list[dict] = field(default_factory=list)
    planned_action: dict | None = None
    policy_decision: str = ""
    policy_reason: str = ""
    approval_task_id: str | None = None
    status: Literal[
        "created", "running", "awaiting_approval", "executing", "completed", "failed"
    ] = "created"
    error: str = ""


llm = ChatOpenAI(
    model=settings.openai_llm_model,
    api_key=settings.openai_api_key,
    temperature=0,
)


async def _node_retrieve(state: AgentState) -> AgentState:
    state.status = "running"
    chunks, filtered = await retrieve(state.db, state.request, state.user)
    state.retrieved_chunks = chunks
    state.filtered_count = filtered

    await audit_service.write_event(
        state.db,
        tenant_id=state.tenant_id,
        event_type="retrieval_complete",
        run_id=state.run_id,
        user_id=state.user.user_id,
        agent_id=state.agent_id,
        payload={
            "chunks_retrieved": len(chunks),
            "chunks_filtered": filtered,
            "sources": [c.document_name for c in chunks],
        },
    )
    return state


async def _node_generate(state: AgentState) -> AgentState:
    context_parts = []
    for i, chunk in enumerate(state.retrieved_chunks, start=1):
        context_parts.append(f"[{i}] Source: {chunk.document_name} ({chunk.source_system})\n{chunk.content}")

    context = "\n\n".join(context_parts) if context_parts else "No authorized sources found."

    prompt = f"""You are an enterprise AI assistant. Answer the user's question using ONLY the provided sources.
Cite each source by its number [1], [2], etc. If sources are insufficient, say so clearly.

Sources:
{context}

Question: {state.request}

Answer:"""

    response = await llm.ainvoke(prompt)
    state.answer = response.content

    state.citations = [
        {
            "id": i,
            "source_system": chunk.source_system,
            "document_name": chunk.document_name,
            "excerpt": chunk.content[:200],
            "similarity": round(chunk.similarity, 3),
        }
        for i, chunk in enumerate(state.retrieved_chunks, start=1)
    ]
    return state


async def _node_policy_check(state: AgentState) -> AgentState:
    if not state.planned_action:
        state.policy_decision = PolicyDecision.ALLOW
        state.policy_reason = "No action planned"
        return state

    result = await policy_evaluate(
        state.db,
        action=state.planned_action.get("type", ""),
        action_data=state.planned_action,
        user=state.user,
    )
    state.policy_decision = result.decision
    state.policy_reason = result.reason

    await audit_service.write_event(
        state.db,
        tenant_id=state.tenant_id,
        event_type="policy_evaluation",
        run_id=state.run_id,
        user_id=state.user.user_id,
        agent_id=state.agent_id,
        payload={
            "action": state.planned_action,
            "decision": result.decision,
            "policy": result.policy_name,
            "reason": result.reason,
        },
    )
    return state


async def _node_complete(state: AgentState) -> AgentState:
    state.status = "completed"
    await audit_service.write_event(
        state.db,
        tenant_id=state.tenant_id,
        event_type="run_completed",
        run_id=state.run_id,
        user_id=state.user.user_id,
        agent_id=state.agent_id,
        payload={"answer_length": len(state.answer), "citations": len(state.citations)},
    )
    return state


async def _node_await_approval(state: AgentState) -> AgentState:
    state.status = "awaiting_approval"
    await audit_service.write_event(
        state.db,
        tenant_id=state.tenant_id,
        event_type="approval_required",
        run_id=state.run_id,
        user_id=state.user.user_id,
        agent_id=state.agent_id,
        payload={"action": state.planned_action, "reason": state.policy_reason},
    )
    return state


def _route_after_policy(state: AgentState) -> str:
    if state.policy_decision == PolicyDecision.DENY:
        return "failed"
    if state.policy_decision == PolicyDecision.REQUIRE_APPROVAL:
        return "await_approval"
    return "complete"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("retrieve", _node_retrieve)
    graph.add_node("generate", _node_generate)
    graph.add_node("policy_check", _node_policy_check)
    graph.add_node("complete", _node_complete)
    graph.add_node("await_approval", _node_await_approval)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "policy_check")
    graph.add_conditional_edges("policy_check", _route_after_policy, {
        "complete": "complete",
        "await_approval": "await_approval",
        "failed": END,
    })
    graph.add_edge("complete", END)
    graph.add_edge("await_approval", END)

    return graph.compile()


agent_graph = build_graph()


async def run_agent(
    db: AsyncSession,
    run_id: str,
    agent_id: str,
    user: UserContext,
    request: str,
    planned_action: dict | None = None,
) -> AgentState:
    state = AgentState(
        run_id=run_id,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        user=user,
        request=request,
        db=db,
        planned_action=planned_action,
    )
    return await agent_graph.ainvoke(state)
