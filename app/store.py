"""Estado y cola atómicos en Redis; no expiran tareas pendientes."""
import json
from datetime import datetime, timezone
from uuid import uuid4

STREAM = 'p7:queue'
GROUP = 'workers'


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, redis):
        self.redis = redis

    async def get(self, job_id):
        value = await self.redis.get('p7:job:' + job_id)
        return json.loads(value) if value else None

    async def submit(self, query, action):
        job_id = str(uuid4())
        job = dict(job_id=job_id, query=query, action=action, status='PENDING',
                   created_at=now(), updated_at=now(), result=None, error=None)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.set('p7:job:' + job_id, json.dumps(job))
            pipe.xadd(STREAM, {'job_id': job_id})
            await pipe.execute()
        return job

    async def update(self, job, status, **values):
        job.update(status=status, updated_at=now(), **values)
        await self.redis.set('p7:job:' + job['job_id'], json.dumps(job))

    async def approve(self, job_id, approved):
        # Compare-and-set evita doble aprobación y doble entrada de reanudación.
        return await self.redis.eval('''
local raw = redis.call('GET', KEYS[1])
if not raw then return 0 end
local job = cjson.decode(raw)
if job.status ~= 'WAITING_APPROVAL' then return -1 end
job.status = 'PENDING'
job.decision = ARGV[1] == 'true'
job.updated_at = ARGV[2]
redis.call('SET', KEYS[1], cjson.encode(job))
redis.call('XADD', KEYS[2], '*', 'job_id', job.job_id)
return 1
''', 2, 'p7:job:' + job_id, STREAM, json.dumps(approved), now())
