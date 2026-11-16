# Validación de la entrega final

Fecha: **16 de noviembre de 2026**, Argentina. Esta evidencia pertenece al sistema final; no reutiliza capturas ni resultados de M7 como si fueran del proyecto actual.

## Pruebas automáticas

Python 3.12.15: **35 passed, 2 skipped**. Las dos omitidas requieren Redis 8 real. Ruff y `pip check` correctos. Se verificaron especialmente reapertura del checkpointer SQLite, reanudación después del investigador sin repetirlo, aprobación concurrente única, rechazo sin publicación y contratos de embeddings con transporte simulado.

Las pruebas usan modelos/transporte simulados y no acreditan por sí solas funcionamiento de un proveedor real. El apartado siguiente documenta las llamadas reales.

Se repitió la suite en un entorno virtual propio de esta entrega, instalado desde `requirements-lock.txt`: **35 passed, 2 skipped**, Ruff correcto y ninguna dependencia incompatible. La búsqueda de tests se limita a `tests/` para evitar recopilar clones o evidencias guardados en `output/`.

## Clon limpio

Se clonó el repositorio publicado en otra carpeta, sin `.env`, bases de datos ni archivos de las preentregas. Se generaron claves aleatorias nuevas con `scripts/bootstrap.py` y se levantaron API y worker con el entorno Python 3.12 independiente de la entrega. `/health` respondió correctamente y una tarea HTTP offline terminó en DONE con 190 horas de ahorro. [Registro](../evidence/clean-clone-smoke.json).

Esta comprobación valida el código clonado con dependencias instaladas, sin credenciales externas. No equivale a validar una instalación completa sobre otro sistema operativo; `run.sh` y el perfil Docker requieren comprobación en sus respectivos entornos.

También se ejecutó `run.ps1` en la copia principal con el entorno virtual ya instalado. El lanzador levantó API y worker y `/health` devolvió `{"status":"ok"}`. El primer paso de creación de venv requiere Python 3.12 disponible mediante `py -3.12`, según el README.

## Cinco ejecuciones reales por HTTP

Configuración: SQLite durable, un worker secuencial, `AGENT_MODE=llm`, Anthropic `claude-haiku-4-5-20251001`, recuperación BM25 y LangSmith habilitado. Cinco POST enviados concurrentemente; todos terminaron en DONE. El worker procesa secuencialmente, por lo que los tiempos de cliente incluyen espera en cola y polling.

| Job ID | Estado | Tiempo del cliente |
|---|---|---:|
| `d4593748-f995-4e5c-9494-a1f89aab2ad2` | DONE | 50,100 s |
| `7f0f0689-053d-4a4a-95c9-87e538a32930` | DONE | 11,492 s |
| `14be4513-4581-421f-a5aa-6be51c4774c3` | DONE | 39,955 s |
| `c0d682a7-1b66-4219-8043-41e8dde93005` | DONE | 21,714 s |
| `b0946a9b-257a-43ff-9e47-37402f719bc1` | DONE | 29,810 s |

[JSON original](../evidence/five-live-jobs.json). p95 cliente por nearest rank con cinco muestras: **50,100 s**, igual al máximo. No es la latencia de inferencia ni un benchmark de capacidad.

## Observabilidad comprobada en la interfaz

Proyecto: `intelligence-final-validada`. [Abrir en LangSmith](https://smith.langchain.com/o/4c0b58ac-c0d3-4026-8f6e-459c2ea6d318/a/intelligence-final-validada/projects/p/1d4271d7-553d-4e2e-8137-e3f1b14a4c3d). Requiere acceso a la cuenta; las capturas del repositorio permiten revisar la evidencia sin ese acceso.

1. [Cinco trazas raíz exitosas con tokens y costos](../evidence/01-five-traces.jpg).
2. [Árbol con supervisor, investigador, herramienta y span RAG](../evidence/02-trace-tree.jpg).
3. [Analista, supervisión final y síntesis con fuentes](../evidence/03-analysis-and-synthesis.jpg).

En el orden mostrado en la tabla de LangSmith (más reciente primero), las latencias de las cinco trazas son 9,71; 9,70; 8,96; 9,83 y 10,52 s. Los costos visibles son USD 0,01041; 0,01014; 0,009914; 0,01019; 0,01006, cuya suma de valores mostrados es **USD 0,050714**. Son valores del dashboard, con redondeo. El agregado de la barra lateral puede diferir por redondeo/agregación; no se usa para sustituir la suma detallada.

La traza inspeccionada muestra 28 ejecuciones hijas y cinco llamadas LLM. El analista utiliza 1.657 tokens en una llamada de 2,20 s. Las tres decisiones del supervisor consumen aproximadamente 1,95 + 2,10 + 2,53 s; concentran la mayor latencia acumulada del grafo observado. La recuperación local y los cálculos aparecen alrededor de 0 s por la resolución de la interfaz. Esto describe una traza, no demuestra un cuello de botella general.

Resultado comprobado: 190 h/mes de ahorro ponderado sobre los pilotos **simulados**, 74,03%, con tres fuentes citadas. No se interpreta como ahorro empresarial real.

## Límites de lo validado

- Docker Desktop devolvió `Docker Desktop is unable to start`. La ejecución E2E validada usa SQLite; Redis/Compose queda pendiente de ejecución en un motor operativo.
- La rama híbrida tiene pruebas con embeddings simulados. No se llamó al servicio real de embeddings en esta corrida.
- Cinco muestras demuestran funcionamiento y recepción de trazas, no SLA, escalabilidad ni evaluación estadística de recuperación.
- Las trazas remotas están sujetas a retención del servicio. Las capturas y el JSON quedan versionados.
- No se incluye CI/CD ni infraestructura cloud porque no forman parte del alcance de evaluación.
