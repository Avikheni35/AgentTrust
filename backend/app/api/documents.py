import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import UserContext, get_current_user
from app.db.database import get_db
from app.db.models import Document
from app.rag.ingestion import ingest_document

router = APIRouter(prefix="/documents", tags=["Documents"])


def _check_ownership(user, document) -> None:
    """Admin can touch any document. Everyone else can only touch their own."""
    if "admin" in user.roles:
        return
    if document.owner_email != user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This document was uploaded by {document.owner_email}. Only an admin can modify it.",
        )


@router.get("")
async def list_documents(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document).where(Document.tenant_id == user.tenant_id)
    )
    return result.scalars().all()


UPLOAD_ROLES = {"admin", "it_admin", "hr_manager", "finance_controller", "procurement_manager"}

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    sensitivity: str = Form("internal"),
    department: str = Form(None),
    region: str = Form(None),
    access_roles: str = Form(""),  # comma-separated
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not any(r in UPLOAD_ROLES for r in user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and managers may upload documents.",
        )
    file_bytes = await file.read()
    file_type = (file.filename or "").rsplit(".", 1)[-1].lower()

    roles = [r.strip() for r in access_roles.split(",") if r.strip()]

    document = Document(
        id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        source_system="upload",
        name=file.filename or "untitled",
        file_type=file_type,
        owner_email=user.email,
        department=department,
        region=region,
        sensitivity=sensitivity,
        access_roles=roles,
        created_at=datetime.now(timezone.utc),
    )
    db.add(document)
    await db.flush()

    chunk_count = await ingest_document(db, tenant_id=user.tenant_id, document=document, file_bytes=file_bytes)

    return {
        "document_id": document.id,
        "name": document.name,
        "chunk_count": chunk_count,
        "indexed_at": document.indexed_at,
    }


@router.patch("/{document_id}/sensitivity")
async def update_sensitivity(
    document_id: str,
    body: dict,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not any(r in UPLOAD_ROLES for r in user.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins and managers may update document sensitivity.")
    new_sensitivity = body.get("sensitivity", "")
    if new_sensitivity not in ("public", "internal", "confidential", "restricted"):
        raise HTTPException(status_code=400, detail="Invalid sensitivity value.")
    result = await db.execute(select(Document).where(Document.id == document_id, Document.tenant_id == user.tenant_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    _check_ownership(user, document)
    document.sensitivity = new_sensitivity
    # Keep chunks in sync
    from app.db.models import DocumentChunk
    from sqlalchemy import update as sql_update
    await db.execute(sql_update(DocumentChunk).where(DocumentChunk.document_id == document_id).values(sensitivity=new_sensitivity))
    await db.commit()
    return {"document_id": document_id, "sensitivity": new_sensitivity}


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not any(r in UPLOAD_ROLES for r in user.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and managers may delete documents.",
        )
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.tenant_id == user.tenant_id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    _check_ownership(user, document)
    await db.delete(document)
    await db.commit()
