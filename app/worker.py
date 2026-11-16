"""Consumidor durable: recuperación de mensajes, timeout y estado FAILED."""
import asyncio
import logging
from contextlib import suppress
from uuid import uuid4

from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from langgraph.types import Command
from langsmith import traceable
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from app.config import settings
from app.graph import build_graph
from app.observability import configure, model
from app.store import GROUP, STREAM, Store

log = logging.getLogger(__name__)


@traceable(name='task_execution')
async def execute(graph, job):
    config = {'configurable': {'thread_id': job['job_id']}, 'recursion_limit': 100,
              'metadata': {'job_id': job['job_id']}, 'tags': ['intelligence-final']}
    snapshot = await graph.aget_state(config)
    if 'decision' in job:
        value = Command(resume=job['decision']) if snapshot.interrupts else None
    elif snapshot.values:
        value = None
    else:
        value = {'query': job['query'], 'action': job['action']}
    return await graph.ainvoke(value, config)


async def process(store, graph, job_id, timeout):
    job = await store.get(job_id)
    if not job or job['status'] in ('DONE', 'FAILED', 'REJECTED', 'WAITING_APPROVAL'):
        return
    await store.update(job, 'RUNNING')
    try:
        result = await asyncio.wait_for(execute(
            graph, job, langsmith_extra={'metadata': {'job_id': job_id}}), timeout)
        if result.get('__interrupt__'):
            await store.update(job, 'WAITING_APPROVAL', result=result['final_answer'])
        else:
            if result.get('publication'):
                # Idempotencia: clave estable y contenido validado por el grafo.
                await store.redis.set('p7:report:' + job_id, result['publication'])
            rejected = job.get('decision') is False
            await store.update(job, 'REJECTED' if rejected else 'DONE',
                               result=result['final_answer'])
    except Exception as exc:
        log.error('job_id=%s error_type=%s', job_id, type(exc).__name__)
        await store.update(job, 'FAILED', error=type(exc).__name__)


async def main():
    config = settings()
    if not 1 <= config.worker_concurrency <= 20 or not 10 <= config.job_timeout <= 600:
        raise ValueError('Concurrencia 1..20; timeout 10..600 segundos')
    configure(config)
    llm = model(config)
    if config.storage_backend == 'sqlite':
        from app.sqlite_store import run_worker
        await run_worker(config, llm)
        return
    redis = Redis.from_url(config.redis_url, decode_responses=True)
    store = Store(redis)
    try:
        await redis.xgroup_create(STREAM, GROUP, id='0', mkstream=True)
    except ResponseError as exc:
        if 'BUSYGROUP' not in str(exc):
            raise
    try:
        async with AsyncRedisSaver.from_conn_string(config.redis_url) as saver:
            await saver.asetup()
            graph = build_graph(saver, llm)

            async def consume():
                consumer = str(uuid4())
                while True:
                    # Lease > timeout: sólo reclamar después de que el dueño debió finalizar.
                    claimed = await redis.xautoclaim(
                        STREAM, GROUP, consumer, (config.job_timeout + 60) * 1000,
                        start_id='0-0', count=1)
                    messages = claimed[1]
                    if not messages:
                        batches = await redis.xreadgroup(GROUP, consumer, {STREAM: '>'},
                                                         count=1, block=2000)
                        messages = batches[0][1] if batches else []
                    for message_id, fields in messages:
                        job_id = fields['job_id']
                        token = str(uuid4())
                        lock = 'p7:lock:' + job_id
                        acquired = await redis.set(lock, token, nx=True,
                                                   ex=config.job_timeout + 30)
                        if not acquired:
                            continue  # Queda pendiente para recuperación posterior.
                        try:
                            await process(store, graph, job_id, config.job_timeout)
                            await redis.xack(STREAM, GROUP, message_id)
                        finally:
                            await redis.eval('''
if redis.call('GET', KEYS[1]) == ARGV[1] then
return redis.call('DEL', KEYS[1]) end
return 0
''', 1, lock, token)

            await asyncio.gather(*(consume() for _ in range(config.worker_concurrency)))
    finally:
        await redis.aclose()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
