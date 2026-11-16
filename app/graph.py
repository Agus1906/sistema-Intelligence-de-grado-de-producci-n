"""M6 encapsulado + barrera HITL antes del efecto persistente."""
from typing import Literal

from langgraph.graph import END, START, StateGraph

from app.hitl import approval
from app.m6.state import State as M6State
from app.m6.state import initial_state


class State(M6State):
    action: str
    approved: bool
    publication: str


def build_graph(checkpointer, model=None):
    from functools import partial

    from app.m6.agents.analyst_agent import analyst_agent
    from app.m6.agents.research_agent import research_agent
    from app.m6.agents.supervisor import make_supervisor
    from app.m6.graph import guarded, stop, synthesis

    def initialize(state):
        return initial_state(state['query'])

    def completed(state):
        raise RuntimeError(state.get('error') or 'Sin evidencia suficiente')

    def route(state) -> Literal['approval', '__end__']:
        return 'approval' if state['action'] == 'publish_report' else END

    def publish(state):
        # El worker materializa este informe una vez, usando job_id como clave.
        return {'publication': state['final_answer'] if state['approved'] else ''}

    builder = StateGraph(State)
    builder.add_node('initialize', initialize)
    builder.add_node('supervisor', guarded('supervisor', make_supervisor(model=model)))
    builder.add_node('research', guarded('research', partial(research_agent, model=model)))
    builder.add_node('analyst', guarded('analyst', partial(analyst_agent, model=model)))
    builder.add_node('synthesis', synthesis)
    builder.add_node('stop', stop)
    builder.add_node('incomplete', completed)
    builder.add_node('approval', approval)
    builder.add_node('publish', publish)
    builder.add_edge(START, 'initialize')
    builder.add_edge('initialize', 'supervisor')
    builder.add_conditional_edges('supervisor', lambda s: s['next_agent'],
                                 {n: n for n in ['research', 'analyst', 'synthesis', 'stop']})
    builder.add_edge('research', 'supervisor')
    builder.add_edge('analyst', 'supervisor')
    builder.add_edge('stop', 'incomplete')
    builder.add_conditional_edges('synthesis', route)
    builder.add_edge('approval', 'publish')
    builder.add_edge('publish', END)
    return builder.compile(checkpointer=checkpointer)
