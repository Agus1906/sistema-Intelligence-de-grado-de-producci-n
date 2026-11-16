# Operación y recuperación

1. Conservar `.env` fuera de Git. Los lanzadores generan claves locales distintas; para LLM configurar secretos propios. No compartir capturas con credenciales.
2. Arrancar con `run.ps1`, `sh run.sh` o Compose según el perfil. No arrancar dos perfiles sobre el mismo puerto. Si 8000 está ocupado, detener la instancia propia anterior.
3. Consultar `/health` y una tarea de prueba. La API puede aceptar trabajos con worker apagado: permanecen PENDING hasta que vuelve.
4. Una computadora apagada no ejecuta trabajos. Para operación continua se requiere un host encendido; la evaluación admite despliegue local.
5. Tras reiniciar, SQLite selecciona PENDING/RUNNING y reanuda desde checkpoint. Redis reclama pendientes abandonados después de `JOB_TIMEOUT+60` segundos. Los terminales no se vuelven a ejecutar.
6. Timeout o excepción dejan FAILED. No hay reintento automático del trabajo fallido; el cliente crea otro trabajo explícitamente. Los SDK LLM realizan hasta un reintento de transporte, con posibilidad de costo adicional.
7. Dos POST independientes crean dos trabajos. No existe deduplicación entre solicitudes. La publicación local es idempotente por UUID; un futuro sistema externo debe ofrecer su propia clave de idempotencia transaccional.
8. Los errores se consultan por API y logs con UUID y tipo. No se configuraron correo ni alertas externas. LangSmith no sustituye las alertas operativas.
9. Respaldar `data/` con servicios detenidos para SQLite. En Redis respaldar el volumen/AOF; `appendfsync everysec` admite pérdida aproximada del último segundo en una caída brusca. No usar `docker compose down -v` si se quiere conservar estado.
10. Definir retención y limpieza antes de operar con volumen real: tareas, informes y checkpoints no vencen automáticamente. No subir archivos SQLite, AOF ni `.env` al repositorio.

SQLite permite lectura/API concurrente pero su worker es secuencial. En Redis se controla concurrencia 1–20 y timeout 10–600 s. No mezclar una instancia Redis de pruebas con datos reales: las pruebas crean grupos y trabajos propios y dejan checkpoints.

Para producción empresarial faltan TLS/proxy, identidad individual, autorización por recurso, rate limiting, auditoría externa, backups probados, retención, alertas y evaluación del corpus. Este entregable es un prototipo académico con controles operativos y despliegue local validado; el título de la consigna no certifica aptitud empresarial sin esos trabajos.
