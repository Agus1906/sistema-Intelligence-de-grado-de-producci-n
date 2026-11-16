"""Especialista de recuperación: no realiza cálculos ni ve el historial global."""
from app.m6.agents.tool_agent import call_role_tool
from app.m6.tools import search_corpus

PROMPT = 'Investiga exclusivamente en el corpus autorizado. Devuelve evidencia con ID y fuente; no inventes datos.'


async def research_agent(state, model=None):
    documents = await call_role_tool(model, PROMPT, {'query': state['query'], 'feedback': state['issues']},
                               search_corpus, {'query': state['query']})
    return {'research': {'documents': documents, 'version': state['steps']},
            'analysis': {},
            'contributions': [{'agent': 'research', 'step': state['steps'],
                               'detail': f'search_corpus: {len(documents)} documentos'}]}
