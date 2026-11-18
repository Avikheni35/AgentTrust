from dataclasses import dataclass

from openai import AsyncOpenAI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import UserContext
from app.config import settings
from app.db.models import Document, DocumentChunk

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

SENSITIVITY_RANK = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_name: str
    source_system: str
    content: str
    similarity: float
    sensitivity: str


async def embed_query(query: str) -> list[float]:
    response = await openai_client.embeddings.create(
        model=settings.openai_embedding_model,
        input=query,
        dimensions=settings.openai_embedding_dimensions,
    )
    return response.data[0].embedding


def _user_can_access_chunk(chunk: DocumentChunk, user: UserContext) -> bool:
    # Public chunks are always accessible
    if chunk.sensitivity == "public":
        return True

    # Region check
    if chunk.region and user.region and chunk.region != user.region:
        return False

    # Role check: if chunk has access_roles set, user must have at least one
    if chunk.access_roles:
        return bool(set(chunk.access_roles) & set(user.roles))

    return True


async def retrieve(
    db: AsyncSession,
    query: str,
    user: UserContext,
    top_k: int = None,
    source_systems: list[str] | None = None,
    departments: list[str] | None = None,
) -> tuple[list[RetrievedChunk], int]:
    """
    Returns (permitted_chunks, filtered_count).
    filtered_count is how many chunks were removed by permission filter.
    """
    top_k = top_k or settings.max_retrieval_chunks
    query_embedding = await embed_query(query)

    # Vector similarity search via pgvector
    # We fetch more than top_k to account for permission filtering
    fetch_k = top_k * 4

    # Build optional filter clauses so NULL array params don't confuse asyncpg
    extra_where = ""
    params: dict = {
        "embedding": str(query_embedding),
        "tenant_id": user.tenant_id,
        "fetch_k": fetch_k,
    }
    if source_systems is not None:
        extra_where += " AND d.source_system = ANY(:source_systems)"
        params["source_systems"] = source_systems
    if departments is not None:
        extra_where += " AND dc.department = ANY(:departments)"
        params["departments"] = departments

    stmt = text(f"""
        SELECT
            dc.id,
            dc.document_id,
            dc.content,
            dc.sensitivity,
            dc.access_roles,
            dc.department,
            dc.region,
            dc.source_authority,
            d.name AS document_name,
            d.source_system,
            1 - (dc.embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        WHERE dc.tenant_id = :tenant_id
          AND d.tenant_id = :tenant_id
          {extra_where}
        ORDER BY dc.embedding <=> CAST(:embedding AS vector)
        LIMIT :fetch_k
    """)

    result = await db.execute(stmt, params)
    rows = result.mappings().all()

    permitted: list[RetrievedChunk] = []
    filtered_count = 0

    for row in rows:
        # Permission filter
        user_region = user.region
        chunk_region = row["region"]
        chunk_roles = row["access_roles"] or []
        chunk_sensitivity = row["sensitivity"]

        allowed = True
        if chunk_sensitivity != "public":
            if chunk_region and user_region and chunk_region != user_region:
                allowed = False
            elif chunk_roles and not (set(chunk_roles) & set(user.roles)):
                allowed = False

        if not allowed:
            filtered_count += 1
            continue

        permitted.append(RetrievedChunk(
            chunk_id=row["id"],
            document_id=row["document_id"],
            document_name=row["document_name"],
            source_system=row["source_system"],
            content=row["content"],
            similarity=float(row["similarity"]),
            sensitivity=chunk_sensitivity,
        ))

        if len(permitted) >= top_k:
            break

    # Sort by similarity × source_authority
    permitted.sort(key=lambda c: c.similarity, reverse=True)

    return permitted, filtered_count
