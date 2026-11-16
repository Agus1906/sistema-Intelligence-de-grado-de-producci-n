"""Herramientas acotadas: recuperación local y cálculo sin eval ni ejecución de código."""
import math
import re
import unicodedata

from langchain_core.tools import tool

from app.contracts import CalculationInput, CalculationOutput, SearchInput, SearchOutput


def tokens(text: str) -> set[str]:
    normalized = ''.join(c for c in unicodedata.normalize('NFD', text.lower())
                         if unicodedata.category(c) != 'Mn')
    stopwords = {'los', 'las', 'del', 'una', 'por', 'para', 'con', 'que', 'sus', 'como'}
    return set(re.findall(r'[a-z0-9]{3,}', normalized)) - stopwords


@tool(args_schema=SearchInput)
async def search_corpus(query: str, limit: int = 3) -> list[dict]:
    """Recupera evidencia RAG del corpus autorizado con fuentes verificadas."""
    from app.retrieval import retrieve
    result = SearchOutput(documents=await retrieve(query, limit))
    return [d.model_dump() for d in result.documents]


@tool(args_schema=CalculationInput)
def calculate_savings(documents: list[dict]) -> dict:
    """Valida registros y calcula ahorro mensual en horas y porcentaje ponderado."""
    documents = [d.model_dump() if hasattr(d, 'model_dump') else d for d in documents]
    if not documents:
        raise ValueError('No hay documentos para analizar')
    ids = set()
    rows = []
    for d in documents:
        if not d.get('id') or d['id'] in ids or not d.get('source'):
            raise ValueError('Documento sin identidad/fuente o duplicado')
        ids.add(d['id'])
        values = [d[k] for k in ('before_minutes', 'after_minutes', 'volume_month')]
        if any(isinstance(v, bool) or not isinstance(v, (int, float))
               or not math.isfinite(v) for v in values):
            raise ValueError('Datos numéricos inválidos')
        before, after, volume = values
        if before <= 0 or after < 0 or after > before or volume <= 0 or int(volume) != volume:
            raise ValueError('Tiempos o volumen fuera de dominio')
        rows.append({'id': d['id'], 'source': d['source'],
                     'before_hours': before * volume / 60,
                     'after_hours': after * volume / 60,
                     'saved_hours': (before - after) * volume / 60})
    before = sum(r['before_hours'] for r in rows)
    after = sum(r['after_hours'] for r in rows)
    return CalculationOutput.model_validate({'rows': rows, 'before_hours': before, 'after_hours': after,
            'saved_hours': before - after, 'reduction_pct': (before - after) / before * 100,
            'source_ids': [d['id'] for d in documents]}).model_dump()
