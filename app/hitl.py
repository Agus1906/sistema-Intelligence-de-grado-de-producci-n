"""Toda publicación es crítica; la decisión no depende del texto del usuario."""
from langgraph.types import interrupt


def approval(state):
    decision = interrupt({'action': 'publish_report',
                          'reason': 'Publicar el informe requiere aprobación humana.'})
    return {'approved': decision is True}
