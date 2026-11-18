import io
from datetime import datetime, timezone
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Document, DocumentChunk

openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.default_chunk_size,
    chunk_overlap=settings.default_chunk_overlap,
    length_function=len,
)


def extract_text(file_bytes: bytes, file_type: str) -> str:
    if file_type == "pdf":
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if file_type in ("docx", "doc"):
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs)

    if file_type in ("txt", "md"):
        return file_bytes.decode("utf-8", errors="ignore")

    return ""


async def embed_texts(texts: list[str]) -> list[list[float]]:
    response = await openai_client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
        dimensions=settings.openai_embedding_dimensions,
    )
    return [item.embedding for item in response.data]


async def ingest_document(
    db: AsyncSession,
    tenant_id: str,
    document: Document,
    file_bytes: bytes,
) -> int:
    text = extract_text(file_bytes, document.file_type or "txt")
    if not text.strip():
        return 0

    chunks = _splitter.split_text(text)
    if not chunks:
        return 0

    # Embed in batches of 100 (OpenAI limit)
    all_embeddings: list[list[float]] = []
    for i in range(0, len(chunks), 100):
        batch = chunks[i : i + 100]
        embeddings = await embed_texts(batch)
        all_embeddings.extend(embeddings)

    chunk_objects = [
        DocumentChunk(
            tenant_id=tenant_id,
            document_id=document.id,
            chunk_index=idx,
            content=content,
            embedding=embedding,
            sensitivity=document.sensitivity,
            access_roles=document.access_roles,
            department=document.department,
            region=document.region,
        )
        for idx, (content, embedding) in enumerate(zip(chunks, all_embeddings))
    ]

    db.add_all(chunk_objects)
    document.chunk_count = len(chunk_objects)
    document.indexed_at = datetime.now(timezone.utc)
    await db.commit()

    return len(chunk_objects)
