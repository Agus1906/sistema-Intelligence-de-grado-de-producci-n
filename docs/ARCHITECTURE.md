# Decisiones de arquitectura

## ADR-01: ensamblar M6 y M7

Se preservan los contratos de tareas, la cola Redis Streams, el supervisor con rúbrica, los especialistas y la aprobación humana. Se reemplazan llamadas LLM síncronas por `ainvoke` y la búsqueda por solapamiento por recuperación BM25 e híbrida opcional. El estado compartido permanece tipado; las fronteras externas y herramientas se validan con Pydantic.

## ADR-02: checkpoints entre especialistas

El grafo final registra cada especialista como nodo del grafo persistido, en lugar de ejecutar un subgrafo completo como una única operación. `thread_id=job_id` identifica cada conversación de trabajo y permite continuarla después de un reinicio o aprobación. No se ofrece chat multiturno general ni memoria entre trabajos distintos. Si el worker muere tras guardar un nodo, la siguiente ejecución consulta el checkpoint y continúa. Una llamada LLM interrumpida antes de guardar su checkpoint puede repetirse y volver a consumir tokens.

## ADR-03: dos perfiles de almacenamiento

SQLite mediante `aiosqlite` y `AsyncSqliteSaver` permite arranque local sin Docker. La cola es el estado durable de la tabla de tareas, sin una transacción distribuida adicional. Un archivo de bloqueo SQLite impide dos workers locales simultáneos. El worker es secuencial, por lo que no sirve para demostrar escalado horizontal.

Redis conserva la arquitectura distribuida de M7: transacción de estado y Stream, consumidores, ACK, recuperación XAUTOCLAIM y lock por trabajo. Los dos perfiles tienen archivos y espacios independientes. No migran datos automáticamente entre sí.

## ADR-04: RAG local y evidencia atómica

El corpus M6 contiene tres registros estructurados y cada uno equivale a un chunk completo. Se conserva su ID, fuente y números. BM25 aporta relevancia léxica; el modo híbrido implementa rankings lexical y semántico unidos por RRF de peso igual y constante 60. El umbral semántico es una configuración que requiere evaluación con corpus real. No hay fallback silencioso a lexical cuando falla el proveedor de embeddings.

Se adapta la separación recuperación/generación de M3 y el enfoque BM25/RRF de M4, eliminando la dependencia obligatoria de Pinecone para cumplir el despliegue local. Este corpus pequeño no demuestra calidad general de recuperación ni capacidad de una vector DB empresarial. La síntesis citada es determinista para asegurar fidelidad de las cifras; el razonamiento y la selección de herramientas usan el modelo en modo LLM.

## ADR-05: async en las fronteras de red y disco

LLMs usan SDK async, embeddings `httpx.AsyncClient`, Redis su cliente async y SQLite `aiosqlite`. Lectura de archivos y ranking BM25 se desplazan a `asyncio.to_thread`. La aritmética acotada es local. No se utiliza `requests` ni un SDK de vector DB síncrono dentro del flujo final. La rúbrica recalcula localmente para verificar los resultados del analista.

## ADR-06: seguridad y observabilidad

Sólo los datos del contexto mínimo llegan a cada rol. El modelo no puede saltar la rúbrica ni alterar los documentos autorizados del analista. No se ejecuta código ni SQL generado por LLM. Las consultas y los documentos se tratan como datos. `X-API-Key` protege tareas y `X-Approval-Key` agrega control para publicar. No representan identidades individuales ni roles empresariales.

LangSmith recibe spans por trabajo, nodos, herramientas y LLM con uso real. El costo depende del catálogo del proveedor en LangSmith, no de una tarifa inventada en código. El envío de telemetría del SDK puede usar su propio hilo interno; la comunicación del negocio permanece async.

Referencias: [persistencia LangGraph](https://docs.langchain.com/oss/python/langgraph/persistence), [tracing LangChain](https://docs.langchain.com/langsmith/trace-with-langchain), [AsyncRedisSaver](https://redis-developer.github.io/langgraph-redis/main/api/async_checkpoint_saver.html).
