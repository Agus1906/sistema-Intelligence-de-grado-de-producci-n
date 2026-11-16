import asyncio

import httpx
import pytest
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from app.graph import build_graph
from app.retrieval import Retriever
from app.sqlite_store import SqliteStore
from app.worker import process

QUERY = 'Investiga pilotos RPA y calcula ahorro mensual'


async def test_sqlite_restart_and_single_approval(tmp_path):
    path = str(tmp_path / 'jobs.sqlite')
    checkpoints = str(tmp_path / 'checkpoints.sqlite')
    store = await SqliteStore.open(path)
    job = await store.submit(QUERY, 'publish_report')
    async with AsyncSqliteSaver.from_conn_string(checkpoints) as saver:
        await process(store, build_graph(saver), job['job_id'], 20)
    assert (await store.get(job['job_id']))['status'] == 'WAITING_APPROVAL'
    await store.aclose()
    store = await SqliteStore.open(path)
    try:
        decisions = await asyncio.gather(*(store.approve(job['job_id'], True) for _ in range(5)))
        assert decisions.count(1) == 1
        async with AsyncSqliteSaver.from_conn_string(checkpoints) as saver:
            await process(store, build_graph(saver), job['job_id'], 20)
        assert (await store.get(job['job_id']))['status'] == 'DONE'
        async with store.db.execute('SELECT COUNT(*) FROM reports') as cursor:
            assert (await cursor.fetchone())[0] == 1
    finally:
        await store.aclose()


async def test_checkpoint_mid_graph_survives_new_connection(tmp_path):
    path = str(tmp_path / 'checkpoint.sqlite')
    config = {'configurable': {'thread_id': 'restart'}}
    async with AsyncSqliteSaver.from_conn_string(path) as saver:
        graph = build_graph(saver)
        result = await graph.ainvoke({'query': QUERY, 'action': 'analyze'}, config,
                                    interrupt_after=['research'])
        assert result['research']['documents']
        assert not result.get('analysis')
    async with AsyncSqliteSaver.from_conn_string(path) as saver:
        graph = build_graph(saver)
        result = await graph.ainvoke(None, config)
        assert result['task_completed']
        assert sum(c['agent'] == 'research' for c in result['contributions']) == 1


async def test_sqlite_rejection(tmp_path):
    config = {'configurable': {'thread_id': 'reject'}}
    async with AsyncSqliteSaver.from_conn_string(str(tmp_path / 'checkpoint.sqlite')) as saver:
        graph = build_graph(saver)
        await graph.ainvoke({'query': QUERY, 'action': 'publish_report'}, config)
        result = await graph.ainvoke(Command(resume=False), config)
        assert result['publication'] == ''


async def test_hybrid_rrf_with_mock_embeddings(monkeypatch):
    retriever = await Retriever.load()
    async def embeddings(texts):
        return [[1.0, 0.0] for _ in texts]
    monkeypatch.setattr(retriever, 'embed', embeddings)
    monkeypatch.setenv('RETRIEVAL_MODE', 'hybrid')
    result = await retriever.search(QUERY, 3)
    assert len(result) == 3
    assert len({d['id'] for d in result}) == 3


async def test_hybrid_missing_credentials_fails_explicitly(monkeypatch):
    retriever = await Retriever.load()
    monkeypatch.setenv('RETRIEVAL_MODE', 'hybrid')
    monkeypatch.delenv('EMBEDDING_API_KEY', raising=False)
    with pytest.raises(ValueError, match='Hybrid requiere'):
        await retriever.search(QUERY, 3)


async def test_embedding_http_async_validation(monkeypatch):
    retriever = await Retriever.load()
    monkeypatch.setenv('EMBEDDING_API_KEY', 'fake-test')
    monkeypatch.setenv('EMBEDDING_MODEL', 'model-test')
    async def respond(request):
        return httpx.Response(200, json={'data': [{'index': 0, 'embedding': [0, 0]}]})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(
        transport=httpx.MockTransport(respond), **kw))
    with pytest.raises(ValueError, match='Embedding inválido'):
        await retriever.embed(['test'])
