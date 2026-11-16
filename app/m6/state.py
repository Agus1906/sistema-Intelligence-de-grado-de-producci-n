"""Estado compartido: resultados versionados y contribuciones acumulativas."""
from operator import add
from typing import Annotated, Literal, TypedDict

from langgraph.graph import MessagesState

Route = Literal['research', 'analyst', 'synthesis', 'stop']


class Contribution(TypedDict):
    agent: str
    step: int
    detail: str


class State(MessagesState):
    query: str
    research: dict
    analysis: dict
    contributions: Annotated[list[Contribution], add]
    next_agent: Route
    steps: int
    issues: list[str]
    task_completed: bool
    final_answer: str
    error: str


def initial_state(query: str) -> State:
    if not isinstance(query, str) or not query.strip() or len(query) > 4000:
        raise ValueError('La consulta debe contener entre 1 y 4000 caracteres.')
    return State(messages=[('user', query)], query=query.strip(), research={}, analysis={},
                 contributions=[], next_agent='research', steps=0, issues=[],
                 task_completed=False, final_answer='', error='')
