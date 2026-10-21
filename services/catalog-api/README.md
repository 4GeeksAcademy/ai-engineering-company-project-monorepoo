# Brasaland Public Catalog API

API FastAPI de demostracion, no conectada a POS ni a datos de produccion.
El menu, precios y locales son ejemplos ficticios; no representan el catalogo real.

## Ejecutar

Desde la raiz del monorepo, con Python 3.11 o posterior:

```sh
python -m pip install -r services/catalog-api/requirements.txt
python -m uvicorn main:app --app-dir services/catalog-api --host 0.0.0.0 --port 8000 --workers 1 --log-config services/catalog-api/logging.json
```

Documentacion interactiva: http://localhost:8000/docs.
Lecturas publicas: `GET /menu`, `GET /locations`, filtro opcional `?country=CO|US`.
`GET /health` informa explicitamente el modo demo.

Las escrituras `PUT /menu/{item_id}` y `PUT /locations/{item_id}` requieren
`Authorization: Bearer <token>` y la variable de entorno `CATALOG_ADMIN_TOKEN`
configurada por el operador. Sin esa variable quedan deshabilitadas (503).
No guardar el token en el repositorio ni enviarlo desde el website publico.

## DEV-55: importacion asincrona

Se acordo mantener las lecturas existentes y agregar `POST /menu/imports`, porque
esta demo no tenia informes, pipeline ni una operacion pesada existente.
Reutiliza `PublicCatalog.update_many`, tambien utilizada por las escrituras individuales.
Actualiza IDs existentes; no crea nuevos productos.

Desde la raiz:

```sh
export CATALOG_ADMIN_TOKEN=$(openssl rand -hex 24)
docker compose up --build -d --wait
```

En este Codespaces, antes de levantar los servicios:

```sh
export COMPOSE_FILE=docker-compose.yml:docker-compose.codespaces.yml
```

Este override opcional comparte el namespace de red de Redis, no el proceso.
El Compose estandar utiliza DNS `redis` y una red bridge.

```sh
curl -i http://localhost:8000/menu/imports \
  -H "Authorization: Bearer $CATALOG_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"id":"demo-co","name":"Pollo importado","country":"CO","price":32000}]}'
curl http://localhost:8000/tasks/TASK_ID -H "Authorization: Bearer $CATALOG_ADMIN_TOKEN"
curl http://localhost:8000/tasks/dead-letter -H "Authorization: Bearer $CATALOG_ADMIN_TOKEN"
```

El POST devuelve `202 {"task_id":"..."}` y `Location: /tasks/{task_id}`.
El lote (hasta 1000 registros) queda en SQLite; Redis recibe solo el UUID.
Las tres rutas requieren el mismo token de administracion. ID desconocido: 404;
UUID invalido: 422; broker/backend no disponible: 503.
Estados: `pending`, `started`, `success`, `failure`; `RETRY` se representa como
`pending`. `result` es nulo hasta SUCCESS; `error` esta disponible en FAILURE.

Flower: http://localhost:5555/tasks. Flower muestra SUCCESS/FAILURE; la DLQ es
la tabla SQLite `dead_letters`, consultable desde la ruta administrativa anterior.
No es una cola de reejecucion automatica ni un estado nativo de Flower.

El worker tiene `max_retries=3`: una ejecucion inicial mas tres reintentos,
esperas de 2/4/8 segundos y DLQ en el intento 4. Esto resuelve la contradiccion
entre "tres fallos" y "max_retries=3" del enunciado a favor de la configuracion
explicita de Celery. La DLQ registra UUID, intento, error completo y timestamp UTC.
Cada intento registra estado, duracion y traceback en caso de error.

Los workers usan ACK tardio, prefetch=1, limite blando de 50s y duro de 60s.
Una caida del proceso consumidor devuelve mensajes no confirmados a la cola;
`visibility_timeout=120` supera el timeout de tarea. El resultado de importar y
los cambios del catalogo se confirman en una sola transaccion SQLite: la
redelivery del mismo UUID no aplica dos veces el lote.
Un fallo definitivo se confirma despues de guardar la DLQ (configuracion
normal de Celery para errores terminales), evitando reentrega infinita.

```sh
docker compose logs -f worker
docker compose stop worker       # cierre ordenado; hasta 75s de gracia
docker compose start worker
docker compose stop api          # no detiene al worker
docker compose down              # conserva los volumenes
python services/catalog-api/verify_async.py
```

El ultimo comando necesita las dependencias instaladas en el host y el mismo
`CATALOG_ADMIN_TOKEN` con que se inicio Compose. Detiene temporalmente API/worker;
ejecutarlo solo en desarrollo aislado, sin otros productores.
Comprueba 202 <200ms para 1000 filas, pending, eventos STARTED/SUCCESS en Redis,
resultado via HTTP, mensaje ligero, procesamiento sin API, reintentos y DLQ.

Para procesos locales independientes, abrir terminales separadas y usar en todas:

```sh
cd services/catalog-api
export PYTHONPATH="$PWD" REDIS_URL=redis://localhost:6379/0
export CATALOG_DB_PATH="$PWD/var/catalog.sqlite3"
# Terminal 1:
python -m uvicorn main:app --port 8000
# Terminal 2:
python -m celery -A celery_app:celery_app worker --loglevel=INFO --concurrency=2 --events
# Terminal 3:
python -m celery -A celery_app:celery_app flower --port=5555
```

Para este modo iniciar solo Redis (`docker compose up -d redis`) y detener primero
API, worker y Flower de Compose si estuvieran usando esos puertos. Ctrl+C cierra
cada proceso; parar FastAPI no termina Celery.

## Limites y seguridad

- Datos demo, lotes y DLQ persisten en SQLite; cache TTL por proceso.
- Cada lectura comprueba revisiones persistentes para invalidar cambios de otros procesos.
- SQLite compartido requiere el mismo volumen local; no usar en workers distribuidos en varios hosts.
- `REDIS_URL` configura tanto broker como backend. Los resultados Redis expiran en 24 horas;
  despues el estado nativo vuelve a PENDING. Lotes y DLQ no tienen purga automatica en esta demo.
- Redis usa AOF con fsync always, volumen persistente y memoria `noeviction`.
- Puertos vinculados a loopback; Flower sin autenticacion solo para desarrollo privado.
- No hay outbox: un fallo de publicacion deja un lote sin encolar y devuelve 503;
  reintentar el POST crea otro UUID. Una desconexion ambigua puede haber publicado ya.
- Los timeouts de tarea cubren trabajo ejecutado; una caida repetida del proceso por OOM/SIGKILL
  no incrementa `max_retries` como un error Python. Se necesita deteccion de tareas venenosas
  antes de usar esto como infraestructura de produccion.
- Claves acotadas a dos familias y tres filtros: maximo seis entradas.
- TTL monotonic: menu 60 segundos; locales 300 segundos.
- Lectura/escritura atomicamente serializadas; invalidacion por familia, incluidos todos sus filtros.
- Solo se cachean catalogos publicos. No existen rutas de clientes, ventas o RRHH.
- `Cache-Control: no-store` evita otra capa HTTP que sobreviva a la invalidacion.
- `X-Cache` permite comprobar HIT/MISS; `Server-Timing` y `api.timing` miden latencia.
- Para produccion: PostgreSQL, outbox, autenticacion por usuario/roles, cuotas y retencion,
  TLS/ACL de Redis, autenticacion de Flower y politica de recuperacion ante caidas duras.
  No escalar esta demo como si fuera produccion.

## Pruebas

```sh
cd services/catalog-api
python -m unittest -v test_main test_storage
```

Los 22 tests usan SQLite temporal, reloj falso para TTL, eventos para concurrencia
y mocks solo en las pruebas unitarias del broker. La demostracion real es independiente.