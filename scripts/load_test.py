"""Cinco tareas concurrentes reales. La p95 local no sustituye al dashboard."""
import asyncio
import json
import os
import time
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import load_dotenv


async def main():
    load_dotenv()
    batch = str(uuid4())
    async with httpx.AsyncClient(base_url=os.getenv('API_URL', 'http://localhost:8000'),
                                 headers={'X-API-Key': os.environ['API_KEY']}, timeout=15) as client:
        async def one(index):
            start = time.perf_counter()
            response = await client.post('/tasks', json={
                'query': f'Investiga pilotos RPA y calcula ahorro mensual. Corrida {batch} tarea {index}'})
            response.raise_for_status()
            job_id = response.json()['job_id']
            accepted = time.perf_counter() - start
            for _ in range(300):
                response = await client.get('/tasks/' + job_id)
                response.raise_for_status()
                job = response.json()
                if job['status'] in ('DONE', 'FAILED', 'REJECTED', 'WAITING_APPROVAL'):
                    return dict(job_id=job_id, status=job['status'], enqueue_seconds=accepted,
                                total_seconds=time.perf_counter() - start)
                await asyncio.sleep(1)
            raise TimeoutError(job_id)
        results = await asyncio.gather(*(one(i) for i in range(5)))
    output = Path('output')
    output.mkdir(exist_ok=True)
    # nearest rank: ceil(.95 * 5) = 5. Muestra pequeña, sólo referencia cliente.
    report = dict(batch=batch, jobs=results,
                  client_p95_seconds=max(row['total_seconds'] for row in results))
    (output / 'load_test.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    if any(row['status'] != 'DONE' for row in results):
        raise SystemExit(1)


if __name__ == '__main__':
    asyncio.run(main())
