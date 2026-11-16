import asyncio
from types import SimpleNamespace

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.config import settings
from app.graph import build_graph
from app.main import app
from app.store import STREAM, Store
from app.worker import process

QUERY = 'Investiga pilotos de automatización RPA y calcula ahorro mensual'


@pytest.fixture
async def store():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield Store(redis)
    await redis.aclose()


async def test_concurrent_submission(store):
    jobs = await asyncio.gather(*(store.submit(QUERY, 'analyze') for _ in range(5)))
    assert len({j['job_id'] for j in jobs}) == 5
    assert await store.redis.xlen(STREAM) == 5
    for job in jobs:
        assert (await store.get(job['job_id']))['status'] == 'PENDING'


async def test_hitl_checkpoint_and_rejection():
    saver = InMemorySaver()
    graph = build_graph(saver)
    config = {'configurable': {'thread_id': 'critical'}}
    result = await graph.ainvoke({'query': QUERY, 'action': 'publish_report'}, config)
    assert result['__interrupt__']
    assert not result.get('publication')
    # Grafo reconstruido: la decisión retoma el checkpoint, no recalcula M6.
    resumed = await build_graph(saver).ainvoke(Command(resume=False), config)
    assert resumed['publication'] == ''
    assert resumed['task_completed']


async def test_worker_success_and_approval(store):
    graph = build_graph(InMemorySaver())
    job = await store.submit(QUERY, 'publish_report')
    await process(store, graph, job['job_id'], 20)
    assert (await store.get(job['job_id']))['status'] == 'WAITING_APPROVAL'
    assert (await store.get(job['job_id']))['result']
    assert await store.redis.get('p7:report:' + job['job_id']) is None
    decisions = await asyncio.gather(*(store.approve(job['job_id'], True) for _ in range(5)))
    assert decisions.count(1) == 1
    await process(store, graph, job['job_id'], 20)
    assert (await store.get(job['job_id']))['status'] == 'DONE'
    assert await store.redis.get('p7:report:' + job['job_id'])


async def test_recovery_after_checkpoint_before_job_update(store):
    graph = build_graph(InMemorySaver())
    job = await store.submit(QUERY, 'analyze')
    await graph.ainvoke({'query': QUERY, 'action': 'analyze'},
                       {'configurable': {'thread_id': job['job_id']}})
    await store.update(job, 'RUNNING')
    await process(store, graph, job['job_id'], 20)
    recovered = await store.get(job['job_id'])
    assert recovered['status'] == 'DONE'
    assert recovered['result']


@pytest.mark.parametrize('failure', ['error', 'timeout'])
async def test_worker_failure(store, failure):
    async def fail(*args):
        if failure == 'timeout':
            await asyncio.sleep(1)
        raise RuntimeError('sensitive message')
    job = await store.submit(QUERY, 'analyze')
    await process(store, SimpleNamespace(aget_state=fail), job['job_id'], .01)
    result = await store.get(job['job_id'])
    assert result['status'] == 'FAILED'
    assert 'sensitive' not in result['error']


async def test_api_auth_validation_and_five_tasks(store, monkeypatch):
    monkeypatch.setenv('API_KEY', 'test-key')
    monkeypatch.setenv('APPROVAL_KEY', 'admin-key')
    settings.cache_clear()
    app.state.store = store
    async with AsyncClient(transport=ASGITransport(app), base_url='http://test') as client:
        assert (await client.post('/tasks', json={'query': QUERY})).status_code == 401
        client.headers['X-API-Key'] = 'test-key'
        assert (await client.post('/tasks', json={'query': ' '})).status_code == 422
        responses = await asyncio.gather(*(client.post('/tasks', json={'query': QUERY}) for _ in range(5)))
        assert all(r.status_code == 202 for r in responses)
        job_id = responses[0].json()['job_id']
        assert (await client.get('/tasks/' + job_id)).json()['status'] == 'PENDING'
        assert (await client.post(f'/tasks/{job_id}/approve', json={'approved': True})).status_code == 403
        client.headers['X-Approval-Key'] = 'admin-key'
        assert (await client.post(f'/tasks/{job_id}/approve', json={'approved': True})).status_code == 409
        assert (await client.get('/tasks/00000000-0000-0000-0000-000000000000')).status_code == 404
    settings.cache_clear()
