"""Perfil local durable. Un worker; Redis ofrece consumo distribuido."""
import asyncio
import json
from pathlib import Path
from uuid import uuid4

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.graph import build_graph
from app.store import now


class SqliteStore:
    def __init__(self, db):
        self.db = db
        self.redis = self  # Interfaz mínima de salud/publicación usada por API y worker.
        self.lock = asyncio.Lock()

    @classmethod
    async def open(cls, path):
        await asyncio.to_thread(Path(path).parent.mkdir, parents=True, exist_ok=True)
        db = await aiosqlite.connect(path)
        await db.execute('PRAGMA journal_mode=WAL')
        await db.execute('PRAGMA busy_timeout=10000')
        await db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        await db.execute('CREATE TABLE IF NOT EXISTS reports (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
        await db.commit()
        return cls(db)

    async def ping(self):
        async with self.db.execute('SELECT 1') as cursor:
            return bool(await cursor.fetchone())

    async def aclose(self):
        await self.db.close()

    async def get(self, job_id):
        async with self.db.execute('SELECT body FROM jobs WHERE id=?', (job_id,)) as cursor:
            row = await cursor.fetchone()
        return json.loads(row[0]) if row else None

    async def submit(self, query, action):
        job = dict(job_id=str(uuid4()), query=query, action=action, status='PENDING',
                   created_at=now(), updated_at=now(), result=None, error=None)
        async with self.lock:
            await self.db.execute('INSERT INTO jobs VALUES (?, ?)', (job['job_id'], json.dumps(job)))
            await self.db.commit()
        return job

    async def update(self, job, status, **values):
        job.update(status=status, updated_at=now(), **values)
        async with self.lock:
            await self.db.execute('UPDATE jobs SET body=? WHERE id=?', (json.dumps(job), job['job_id']))
            await self.db.commit()

    async def set(self, key, value):
        async with self.lock:
            await self.db.execute('INSERT OR REPLACE INTO reports VALUES (?, ?)', (key, value))
            await self.db.commit()

    async def approve(self, job_id, approved):
        async with self.lock:
            await self.db.execute('BEGIN IMMEDIATE')
            try:
                job = await self.get(job_id)
                result = 0 if not job else -1
                if job and job['status'] == 'WAITING_APPROVAL':
                    job.update(status='PENDING', decision=approved, updated_at=now())
                    await self.db.execute('UPDATE jobs SET body=? WHERE id=?', (json.dumps(job), job_id))
                    result = 1
                await self.db.commit()
                return result
            except BaseException:
                await self.db.rollback()
                raise

    async def pending(self):
        async with self.db.execute("SELECT id FROM jobs WHERE json_extract(body, '$.status') "
                                   "IN ('PENDING', 'RUNNING') ORDER BY rowid") as cursor:
            return [row[0] for row in await cursor.fetchall()]


async def run_worker(config, llm):
    from app.worker import process
    store = await SqliteStore.open(config.sqlite_path)
    # Bloqueo exclusivo del proceso para impedir dos workers locales simultáneos.
    lease = await aiosqlite.connect(config.sqlite_path + '.worker-lock', timeout=1)
    try:
        await lease.execute('CREATE TABLE IF NOT EXISTS lease (id INTEGER)')
        await lease.commit()
        await lease.execute('BEGIN EXCLUSIVE')
        await asyncio.to_thread(Path(config.checkpoint_path).parent.mkdir, parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(config.checkpoint_path) as saver:
            graph = build_graph(saver, llm)
            while True:
                jobs = await store.pending()
                if not jobs:
                    await asyncio.sleep(0.25)
                for job_id in jobs:
                    await process(store, graph, job_id, config.job_timeout)
    finally:
        await lease.close()
        await store.aclose()
