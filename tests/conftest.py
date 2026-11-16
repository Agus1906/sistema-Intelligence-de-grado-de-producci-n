"""La suite es local: nunca envía telemetría a una cuenta externa."""
import os

os.environ['LANGSMITH_TRACING'] = 'false'
