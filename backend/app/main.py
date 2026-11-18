from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.api import agents, approvals, audit, documents, query
from app.db.database import AsyncSessionLocal, init_db
from app.db.models import Tenant

log = structlog.get_logger()


async def _seed_default_tenant():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Tenant).where(Tenant.slug == "default"))
        if not result.scalar_one_or_none():
            db.add(Tenant(id="default", name="Default Tenant", slug="default"))
            await db.commit()
            log.info("Default tenant created")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting AgentTrust — initialising database")
    await init_db()
    await _seed_default_tenant()
    log.info("Database ready")
    yield
    log.info("Shutting down")


app = FastAPI(
    title="AgentTrust API",
    description="Universal AI Action Trust Layer for Enterprises",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query.router, prefix="/v1")
app.include_router(agents.router, prefix="/v1")
app.include_router(documents.router, prefix="/v1")
app.include_router(approvals.router, prefix="/v1")
app.include_router(audit.router, prefix="/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agenttrust-api"}
