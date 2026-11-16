"""Configuración inicial sin credenciales embebidas."""
import sys
from pathlib import Path
from secrets import token_urlsafe

if sys.version_info < (3, 12):
    raise RuntimeError('Se requiere Python 3.12 o superior')

path = Path('.env')
if not path.exists():
    content = Path('.env.example').read_text(encoding='utf-8')
    content = content.replace('REPLACE_API_KEY', token_urlsafe(32))
    content = content.replace('REPLACE_APPROVAL_KEY', token_urlsafe(32))
    path.write_text(content, encoding='utf-8')
    print('Creado .env con claves locales aleatorias. Consultarlas en el archivo.')
