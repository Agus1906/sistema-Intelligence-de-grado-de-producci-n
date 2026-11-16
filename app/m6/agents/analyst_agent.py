"""Especialista de cómputo: recibe sólo evidencia seleccionada."""
from app.m6.agents.tool_agent import call_role_tool
from app.m6.tools import calculate_savings

PROMPT = 'Valida evidencia y calcula ahorro de tiempo; conserva IDs. No extrapoles a ahorro monetario.'


async def analyst_agent(state, model=None):
    arguments = {'documents': state['research']['documents']}
    result = await call_role_tool(model, PROMPT, arguments, calculate_savings, arguments, fixed_arguments=True)
    result['research_version'] = state['research']['version']
    return {'analysis': result,
            'contributions': [{'agent': 'analyst', 'step': state['steps'],
                               'detail': 'calculate_savings: validación y cálculo ponderado'}]}
