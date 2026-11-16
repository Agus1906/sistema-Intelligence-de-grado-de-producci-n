"""Construcción del StateGraph y barreras de errores recuperables."""
import inspect
import logging
from functools import partial
from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.m6.agents.analyst_agent import analyst_agent
from app.m6.agents.research_agent import research_agent
from app.m6.agents.supervisor import make_supervisor
from app.m6.state import State, initial_state

logger = logging.getLogger(__name__)


def guarded(name, function):
    async def node(state):
        logger.info('node=%s step=%s', name, state['steps'])
        try:
            value = function(state)
            return await value if inspect.isawaitable(value) else value
        except Exception as exc:
            # No se registran consulta, documentos, claves ni el mensaje remoto.
            logger.error('node=%s error_type=%s', name, type(exc).__name__)
            update = {'error': f'{name}: {type(exc).__name__}',
                      'contributions': [{'agent': name, 'step': state['steps'],
                                         'detail': 'Error controlado; no se declara éxito'}]}
            if name == 'supervisor':
                update['next_agent'] = 'stop'
            return update
    return node


def route(state: State) -> Literal['research', 'analyst', 'synthesis', 'stop']:
    return state['next_agent']


def synthesis(state):
    a = state['analysis']
    sources = '\n'.join(f"- [{d['id']}] {d['title']}: {d['source']}"
                        for d in state['research']['documents'])
    text = (f"Consulta: {state['query']}\n\n"
            f"Según los pilotos SIMULADOS recuperados, el tiempo mensual pasa de "
            f"{a['before_hours']:.2f} a {a['after_hours']:.2f} horas. "
            f"Ahorro: {a['saved_hours']:.2f} horas/mes ({a['reduction_pct']:.2f}%).\n"
            'El porcentaje es ponderado por tiempo inicial y volumen; no es un promedio simple.\n'
            'Supuesto: volúmenes y tiempos constantes. No implica ahorro monetario ni evidencia real.\n'
            f'Fuentes:\n{sources}')
    return {'final_answer': text, 'task_completed': True,
            'messages': [('assistant', text)],
            'contributions': [{'agent': 'synthesis', 'step': state['steps'], 'detail': 'Síntesis con fuentes y límites'}]}


def stop(state):
    text = 'No se completó la tarea: ' + (state.get('error') or '; '.join(state.get('issues', []))
                                          or 'Supervisión detenida')
    return {'task_completed': False, 'final_answer': text, 'messages': [('assistant', text)]}


def build_graph(max_steps=8, model=None, research_node=None, analyst_node=None, checkpointer=None):
    builder = StateGraph(State)
    builder.add_node('supervisor', guarded('supervisor', make_supervisor(max_steps, model)))
    builder.add_node('research', guarded('research', research_node or partial(research_agent, model=model)))
    builder.add_node('analyst', guarded('analyst', analyst_node or partial(analyst_agent, model=model)))
    builder.add_node('synthesis', synthesis)
    builder.add_node('stop', stop)
    builder.add_edge(START, 'supervisor')
    builder.add_conditional_edges('supervisor', route)
    builder.add_edge('research', 'supervisor')
    builder.add_edge('analyst', 'supervisor')
    builder.add_edge('synthesis', END)
    builder.add_edge('stop', END)
    return builder.compile(checkpointer=checkpointer)


async def run(query, **kwargs):
    return await build_graph(**kwargs).ainvoke(initial_state(query), {'recursion_limit': 100})
