"""Snapshot BM25 y fusión RRF opcional con embeddings vía HTTP asíncrono."""
import asyncio
import json
import math
import os
from pathlib import Path

import httpx
from langsmith import traceable
from rank_bm25 import BM25Okapi

from app.contracts import Document


class Retriever:
    def __init__(self, documents):
        from app.m6.tools import tokens
        self.documents = documents
        self.tokenize = tokens
        self.bm25 = BM25Okapi([list(tokens(d.text)) for d in documents], epsilon=0.5)
        self.vectors = None
        self.lock = asyncio.Lock()

    @classmethod
    async def load(cls):
        path = Path(os.getenv('CORPUS_PATH', str(Path(__file__).parent / 'm6/data/corpus.json')))
        raw = await asyncio.to_thread(path.read_text, encoding='utf-8')
        docs = [Document.model_validate(d) for d in json.loads(raw)]
        if not docs or len({d.id for d in docs}) != len(docs):
            raise ValueError('Corpus vacío o con IDs duplicados')
        return await asyncio.to_thread(cls, docs)

    async def embed(self, texts):
        key, model = os.getenv('EMBEDDING_API_KEY'), os.getenv('EMBEDDING_MODEL')
        if not key or not model:
            raise ValueError('Hybrid requiere EMBEDDING_API_KEY y EMBEDDING_MODEL')
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post('https://api.openai.com/v1/embeddings',
                                         headers={'Authorization': f'Bearer {key}'},
                                         json={'model': model, 'input': texts})
            response.raise_for_status()
        data = sorted(response.json()['data'], key=lambda d: d['index'])
        vectors = [d['embedding'] for d in data]
        if len(vectors) != len(texts) or not vectors:
            raise ValueError('Cantidad de embeddings inválida')
        dimension = len(vectors[0])
        if not dimension or any(len(v) != dimension or not all(math.isfinite(x) for x in v)
                                or not any(v) for v in vectors):
            raise ValueError('Embedding inválido')
        return vectors

    @traceable(name='rag_retrieval', run_type='retriever')
    async def search(self, query, limit):
        query_tokens = self.tokenize(query)
        scores = await asyncio.to_thread(self.bm25.get_scores, list(query_tokens))
        # El filtro de solapamiento evita recuperar documentos irrelevantes con score cero.
        lexical = sorted([i for i, d in enumerate(self.documents)
                          if query_tokens & self.tokenize(d.text)], key=lambda i: -scores[i])
        ranks = {i: 1 / (60 + rank) for rank, i in enumerate(lexical, 1)}
        mode = os.getenv('RETRIEVAL_MODE', 'bm25')
        if mode not in ('bm25', 'hybrid'):
            raise ValueError('RETRIEVAL_MODE inválido')
        if mode == 'hybrid':
            async with self.lock:
                if self.vectors is None:
                    self.vectors = await self.embed([d.text for d in self.documents])
            vector = (await self.embed([query]))[0]
            if len(vector) != len(self.vectors[0]):
                raise ValueError('Dimensiones incompatibles')
            def cosine(v):
                return sum(a*b for a, b in zip(v, vector, strict=True)) / (
                    math.sqrt(sum(x*x for x in v)) * math.sqrt(sum(x*x for x in vector)))
            threshold = float(os.getenv('SEMANTIC_MIN_SCORE', '0.35'))
            semantic = sorted([i for i, v in enumerate(self.vectors) if cosine(v) >= threshold],
                              key=lambda i: -cosine(self.vectors[i]))
            for rank, i in enumerate(semantic, 1):
                ranks[i] = ranks.get(i, 0) + 1 / (60 + rank)
        selected = sorted(ranks, key=lambda i: -ranks[i])[:limit]
        return [self.documents[i].model_dump() for i in selected]


_retriever = None


async def retrieve(query, limit):
    global _retriever
    if _retriever is None:
        _retriever = await Retriever.load()
    return await _retriever.search(query, limit)
