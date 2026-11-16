"""API sin inferencia ni trabajo bloqueante en los endpoints."""
from contextlib import asynccontextmanager
from secrets import compare_digest
from typing import Literal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, field_validator
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.responses import JSONResponse

from app.config import settings
from app.contracts import Accepted, Health, Job
from app.store import Store

header = APIKeyHeader(name='X-API-Key', auto_error=False)
admin_header = APIKeyHeader(name='X-Approval-Key', auto_error=False)


def authenticate(value=Security(header)):
    if not value or not compare_digest(value, settings().api_key.get_secret_value()):
        raise HTTPException(401, 'Clave inválida')


def approver(value=Security(admin_header)):
    if not value or not compare_digest(value, settings().approval_key.get_secret_value()):
        raise HTTPException(403, 'Aprobador no autorizado')


class Task(BaseModel):
    model_config = {'extra': 'forbid'}
    query: str = Field(min_length=1, max_length=4000)
    action: Literal['analyze', 'publish_report'] = 'analyze'

    @field_validator('query')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Consulta vacía')
        return value.strip()


class Approval(BaseModel):
    model_config = {'extra': 'forbid'}
    approved: bool = Field(strict=True)


@asynccontextmanager
async def lifespan(app):
    if settings().storage_backend == 'sqlite':
        from app.sqlite_store import SqliteStore
        app.state.store = await SqliteStore.open(settings().sqlite_path)
        try:
            yield
        finally:
            await app.state.store.aclose()
        return
    redis = Redis.from_url(settings().redis_url, decode_responses=True)
    await redis.ping()
    app.state.store = Store(redis)
    yield
    await redis.aclose()


app = FastAPI(title='Intelligence System — RPA', version='1.0.0', lifespan=lifespan)


@app.exception_handler(RedisError)
async def redis_unavailable(request, exc):
    return JSONResponse(status_code=503, content={'detail': 'Redis no disponible'})


@app.get('/health', response_model=Health)
async def health():
    await app.state.store.redis.ping()
    return {'status': 'ok'}


@app.post('/tasks', response_model=Accepted, status_code=202, dependencies=[Depends(authenticate)])
async def submit(task: Task):
    job = await app.state.store.submit(task.query, task.action)
    return {'job_id': job['job_id'], 'status': job['status']}


@app.get('/tasks/{job_id}', response_model=Job, dependencies=[Depends(authenticate)])
async def status(job_id: UUID):
    job = await app.state.store.get(str(job_id))
    if not job:
        raise HTTPException(404, 'Tarea inexistente')
    return job


@app.post('/tasks/{job_id}/approve', response_model=Accepted, status_code=202,
          dependencies=[Depends(authenticate), Depends(approver)])
async def approve(job_id: UUID, decision: Approval):
    result = await app.state.store.approve(str(job_id), decision.approved)
    if result == 0:
        raise HTTPException(404, 'Tarea inexistente')
    if result == -1:
        raise HTTPException(409, 'La tarea no espera aprobación')
    return {'job_id': str(job_id), 'status': 'PENDING'}
