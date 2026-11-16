"""Prueba opcional contra Redis 8 real; CI la ejecuta siempre."""
import os
from uuid import uuid4

import pytest
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.types import Command
from redis.asyncio import Redis

from app.graph import build_graph
from app.store import GROUP, STREAM, Store
from app.worker import process

pytestmark = pytest.mark.skipif(not os.getenv('TEST_REDIS_URL'), reason='Requiere Redis 8 real')


async def test_redis_checkpoint_survives_graph_recreation():
    url = os.environ['TEST_REDIS_URL']
    thread_id = str(uuid4())
    config = {'configurable': {'thread_id': thread_id}}
    async with AsyncRedisSaver.from_conn_string(url) as saver:
        await saver.asetup()
        result = await build_graph(saver).ainvoke({
            'query': 'Investiga pilotos RPA y calcula ahorro mensual',
            'action': 'publish_report'}, config)
        assert result['__interrupt__']
    async with AsyncRedisSaver.from_conn_string(url) as saver:
        result = await build_graph(saver).ainvoke(Command(resume=True), config)
        assert result['publication']


async def test_real_queue_recovery_and_failed_state():
    url = os.environ['TEST_REDIS_URL']
    redis = Redis.from_url(url, decode_responses=True)
    store = Store(redis)
    group = GROUP + '-' + str(uuid4())
    try:
        await redis.xgroup_create(STREAM, group, id='$', mkstream=True)
        job = await store.submit('Tema sin evidencia zzzxyz', 'analyze')
        first = await redis.xreadgroup(group, 'dead-worker', {STREAM: '>'}, count=1)
        assert first
        recovered = await redis.xautoclaim(STREAM, group, 'new-worker', 0, '0-0', count=1)
        assert recovered[1][0][1]['job_id'] == job['job_id']
        async with AsyncRedisSaver.from_conn_string(url) as saver:
            await saver.asetup()
            await process(store, build_graph(saver), job['job_id'], 20)
        assert (await store.get(job['job_id']))['status'] == 'FAILED'
    finally:
        await redis.xgroup_destroy(STREAM, group)
        await redis.aclose()
