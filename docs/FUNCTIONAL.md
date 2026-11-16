# Análisis funcional y aceptación

## Confirmado

AS-IS: M6 coordina agentes sobre pilotos simulados; M7 los expone mediante API y cola. Existían llamadas LLM síncronas y búsqueda léxica simple. TO-BE: una aplicación autónoma con recuperación documental, decisiones supervisadas, persistencia entre nodos y observabilidad.

Actores: solicitante (persona o RPA), supervisor del grafo, investigador, analista y aprobador humano. Entrada: consulta y acción. Salida: informe con fuentes, tiempos y ahorro ponderado, o error controlado. Dependencias: Python, almacenamiento y, en modo LLM/tracing, servicios externos y credenciales.

## Reglas de negocio conservadas

1. Sólo se analiza evidencia con identidad y fuente, sin duplicados.
2. Tiempo inicial mayor que cero; posterior entre cero e inicial; volumen mensual entero positivo. Números finitos y sin booleanos.
3. Horas iniciales = suma(minutos iniciales × volumen / 60). Horas posteriores análogas. Ahorro = iniciales − posteriores. Reducción = ahorro / iniciales × 100.
4. La reducción global es ponderada, no promedio de porcentajes.
5. El análisis debe corresponder a la versión actual de investigación y conciliar con la aritmética local.
6. Máximo de ocho decisiones de supervisión, sin ciclos ilimitados. Una propuesta LLM no elude controles.
7. `publish_report` requiere aprobación externa independientemente del contenido del prompt.
8. Rechazar no publica. Repetir una aprobación devuelve conflicto. Publicar sólo guarda un informe local.

## Criterios de aceptación

| Caso | Resultado verificable |
|---|---|
| Consulta general RPA | 256,6667 h iniciales, 66,6667 h posteriores, 190 h de ahorro, 74,026% |
| Consulta fuera de dominio | Sin evidencia, límite acotado y tarea FAILED |
| Análisis adulterado | Supervisor exige corrección; no sintetiza datos incorrectos |
| Campos vacíos, extra o números inválidos | Rechazo mediante Pydantic |
| Publicación crítica | WAITING_APPROVAL, luego DONE o REJECTED |
| Reinicio tras investigación | Continúa con checkpoint sin repetir investigación guardada |
| Fallo del proveedor o timeout | FAILED y tipo de error sin texto remoto sensible |
| Cinco solicitudes reales | Cinco DONE y cinco árboles de spans visibles |

## Supuestos y límites

Volúmenes y tiempos constantes; pilotos ficticios. No se convierten horas a dinero ni se afirma ahorro real. Beneficio esperado: reducir revisión manual y hacer reproducible el análisis. KPIs propuestos: tasa de tareas completadas, errores por tipo, tiempo en cola, latencia de inferencia, costo por trabajo, porcentaje con fuentes válidas y aprobaciones pendientes. La muestra de cinco ejecuciones sólo demuestra funcionamiento.

Pendiente para un caso empresarial: validar corpus y responsables, reglas económicas, objetivos de SLA, umbral semántico, permisos por usuario y tratamiento de datos. Esas reglas no se inventan en esta entrega.
