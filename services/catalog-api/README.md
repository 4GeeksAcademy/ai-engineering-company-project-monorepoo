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

## Limites y seguridad

- Cache y datos viven en memoria: reiniciar restaura los ejemplos.
- Ejecutar solo un worker. Multiples procesos tendrian datos y caches divergentes.
- Claves acotadas a dos familias y tres filtros: maximo seis entradas.
- TTL monotonic: menu 60 segundos; locales 300 segundos.
- Lectura/escritura atomicamente serializadas; invalidacion por familia, incluidos todos sus filtros.
- Solo se cachean catalogos publicos. No existen rutas de clientes, ventas o RRHH.
- `Cache-Control: no-store` evita otra capa HTTP que sobreviva a la invalidacion.
- `X-Cache` permite comprobar HIT/MISS; `Server-Timing` y `api.timing` miden latencia.
- Para produccion: repositorio persistente, autenticacion con roles y cache compartida
  (Redis) con invalidacion coordinada; no escalar esta demo como si fuera produccion.

## Pruebas

```sh
cd services/catalog-api
python -m unittest -v test_main
```

Los tests usan reloj falso sin esperas para TTL y eventos para concurrencia.