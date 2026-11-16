"""Lanzador local: API y worker separados, apagado coordinado."""
import os
import signal
import subprocess
import sys
import time


def main():
    os.environ.setdefault('STORAGE_BACKEND', 'sqlite')
    if os.environ['STORAGE_BACKEND'] != 'sqlite':
        raise ValueError('El lanzador local requiere STORAGE_BACKEND=sqlite')
    children = []
    def stop(*args):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        for command in [['uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'],
                        ['app.worker']]:
            children.append(subprocess.Popen([sys.executable, '-m', *command]))
        print('Swagger: http://127.0.0.1:8000/docs', flush=True)
        while all(p.poll() is None for p in children):
            time.sleep(0.5)
        raise RuntimeError('Un servicio finalizó; revisar los logs anteriores')
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == '__main__':
    main()
