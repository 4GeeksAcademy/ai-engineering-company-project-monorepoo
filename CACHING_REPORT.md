# Informe tecnico: caching en Brasaland

## Alcance y estado inicial

Rama: `feature/caching-optimisation`. Dominios modificados: UI interna en
`uis/backoffice`, nueva API demo en `services/catalog-api`, documentacion y memoria.
No se modificaron rutas protegidas ni el modulo canonico `packages/shared/types`.
Las aplicaciones Next.js existentes pasaron build y lint antes de los cambios.
`services/` solo contenia README: no existia FastAPI, base de datos, trafico ni
latencias de backend que analizar. Se creo una API publica de demostracion;
no se presenta como optimizacion de un backend de produccion existente.
El website publico y su formulario permanecen sin cambios; el backoffice sigue
usando sus datos de muestra, no consulta esta API ni expone datos internos en ella.

## Decisiones del frontend

### Dos componentes con lazy loading

- `SupplierPanel`: alertas de compras, secundarias para el flujo inicial de stock.
  `next/dynamic` lo importa solo cuando se selecciona Proveedores.
- `HrPanel`: alertas de RRHH, relevantes para una funcion distinta y no necesarias
  para visualizar ventas o stock. Se importa al seleccionar RRHH.

Las declaraciones dinamicas estan en `components/Dashboard.tsx`, un Client
Component. La pagina mantiene la frontera servidor y entrega el input estable.
La condicion de render evita solicitar ambos chunks al inicio; separar archivos
sin esa condicion no bastaria. Cada import tiene estado de carga accesible.
Los botones muestran seleccion con `aria-pressed`, admiten teclado y la region
tiene altura minima para reducir saltos. Hay estados sin alertas.
No se cambia la identidad visual ni se mueve toda la UI publica a cliente.

Evidencia: Playwright en Chromium desktop (1280x720) y mobile (390x664) verifica
una descarga nueva por cada panel al abrirlo, ausencia inicial de sus contenidos,
reutilizacion sin otra descarga al volver, ausencia de errores JS y de overflow.
Las capturas se generan en `uis/backoffice/test-results/` y no se versionan.
Chunks del build validado: Proveedores 378 bytes y RRHH 363 bytes sin comprimir
(los nombres hash dependen del build). El ahorro actual es pequeno; no se afirma
una mejora de TTI ni de bundle total frente a la pagina original de servidor.
La frontera cliente agrega JavaScript e hidratacion: tiene sentido para la nueva
navegacion interactiva, pero no seria justificado migrar secciones estaticas solo
para usar imports dinamicos. El patron cobra mas valor cuando crecen estos paneles.

### useMemo y coste de calculo

`useMemo(() => buildBrasalandSnapshot(input), [input])` conserva el resultado del
modulo canonico, sin duplicar reglas. El calculo agrega ventas y pedidos por pais,
calcula tickets, copia/ordena ventas para seleccionar el local destacado, filtra
riesgos de inventario/proveedores y recorre KPIs de RRHH. Es no trivial: crece
aproximadamente como O(S log S + I + P + H), donde S son ventas y los demas son
filas de inventario, proveedores y RRHH.

Cambiar una pestana solo modifica `view`, no `input`, por lo que no vuelve a
ejecutar esa cadena. Cambiar datos requiere reemplazar el objeto `input`
inmutablemente; mutarlo en sitio daria un resultado obsoleto y no esta soportado.
React puede descartar la memoizacion: es una optimizacion, no garantia de correccion.
Con tres filas de ventas de muestra el ahorro es minimo. No se memoizan textos
ni formatos triviales. La memoria es local al componente montado, no una cache
compartida; se invalida por dependencia y desmontaje, no por TTL de backend.

## Decisiones del backend

Se usan diccionario en memoria, reloj monotonic y copias defensivas, sin Redis
ni dependencias adicionales para la cache o el middleware de timing.
Las claves son `(familia, pais)`; pais solo admite CO, US o ausencia de filtro.
Hay como maximo seis entradas, con purga de expirados durante las lecturas.
Un HIT evita filtrar, proyectar moneda y ordenar otra vez; aun debe copiar y
serializar el resultado. La frecuencia de llamadas real es desconocida.

### Inventario completo de endpoints

| Endpoint | Coste y frecuencia | Estabilidad y decision |
| --- | --- | --- |
| GET /menu?country=CO\|US | Filtrado, copia, moneda y ordenacion; lectura publica previsiblemente recurrente, sin frecuencia medida | Catalogo editorial, TTL 60 s; cacheado |
| GET /locations?country=CO\|US | Filtrado, copia y ordenacion; consultas publicas recurrentes, sin frecuencia medida | Locales cambian menos que precios, TTL 300 s; cacheado |
| PUT /menu/{item_id} | Validacion y actualizacion puntual; frecuencia administrativa desconocida, esperada menor que lecturas | No cachear una escritura; invalida toda la familia menu |
| PUT /locations/{item_id} | Validacion y actualizacion puntual; frecuencia administrativa desconocida | No cachear; invalida toda la familia locations |
| GET /health | Comprobacion constante de bajo coste, frecuencia de sondeos por definir | No cachear: debe mostrar disponibilidad actual |
| GET/HEAD /openapi.json | Esquema generado por FastAPI, frecuencia baja de herramientas/docs | Sin cache TTL propia; FastAPI conserva su esquema estatico internamente |
| GET/HEAD /docs | HTML de Swagger, llamadas de desarrollo ocasionales | Sin cache de datos propia |
| GET/HEAD /docs/oauth2-redirect | HTML de soporte Swagger, uso ocasional | Sin cache propia |
| GET/HEAD /redoc | HTML de documentacion, uso ocasional | Sin cache propia |

El filtro ausente representa ambos paises; moneda COP/USD se deriva en la API
solo para este catalogo nuevo. No se reimplementa el resumen de negocio del shared.
Menu y locales son ficticios, explicitamente marcados como demo. `available` es
un indicador editorial del ejemplo, no stock en tiempo real ni garantia de compra.

### TTL e invalidacion

- Menu: 60 segundos limita antiguedad de precios/catalogo; locales: 300 segundos
  porque su descripcion cambia con menor frecuencia. Son politicas iniciales
  basadas en semantica, no en una medicion de cambios reales.
- Un PUT exitoso elimina todas las variantes de su familia, incluso el listado
  global y el pais anterior si cambia de pais. No invalida la otra familia.
- Lecturas, actualizacion e invalidacion comparten `RLock`: una lectura en curso
  no puede repoblar la cache con un valor viejo despues de terminar la escritura.
- Los errores 401, 404 y 422 no modifican datos ni invalidan entradas sanas.
- No hay persistencia ni escritores externos en esta demo. Si se incorporan,
  todos deben publicar invalidaciones; TTL solo acota la obsolescencia restante.
- Solo un worker: datos/cache locales al proceso. Para multiples workers o
  replicas hacen falta almacenamiento persistente y Redis/invalidation coordinada.
  Un reinicio pierde actualizaciones y restaura las muestras.

### Seguridad y observabilidad

Solo se cachean representaciones publicas iguales para cualquier visitante.
No se guardan tokens, headers, sesiones ni datos de clientes, ventas, proveedores
o RRHH en la cache. La clave compartida es segura solo bajo ese contrato publico.
Un endpoint privado futuro requerira autenticacion antes de consultar la cache
y claves por usuario/tenant/permisos, o debera quedar sin cache.

PUT requiere token Bearer comparado en tiempo constante con `CATALOG_ADMIN_TOKEN`,
exclusivamente del entorno del servidor; sin configurarlo las escrituras devuelven
503. No se versiona ningun secreto. Esta proteccion demo no sustituye RBAC/OIDC.

El middleware usa `perf_counter` y el logger `api.timing`; registra metodo,
path sin query, status y milisegundos incluso si falla la peticion. No registra
credenciales ni bodies. `logging.json` habilita INFO al ejecutar uvicorn.
`Server-Timing` facilita inspeccion y `X-Cache: HIT|MISS` distingue las lecturas.
`Cache-Control: no-store` evita caches de navegador/CDN que sobrevivan a la
invalidacion en proceso. El timing mide hasta obtener los headers, no la descarga
completa de un stream; estos endpoints no usan streaming.

## Mediciones y verificaciones

Python 3.14.2, FastAPI 0.142.2, Next.js 16.2.12, React 19.2.4 en este Codespace.
`benchmark.py` mide HTTP via TestClient con 20 parejas MISS/HIT por endpoint;
borra la cache entre parejas, no inserta sleeps ni llamadas lentas artificiales.
El experimento grande crea 10.000 filas sinteticas y consulta CO (5.000 resultados).
Las muestras pequenas tienen dos filas totales (un resultado CO).

| Endpoint | Filas totales | Mediana MISS (ms) | Mediana HIT (ms) |
| --- | ---: | ---: | ---: |
| /menu | 2 | 1,243 | 1,250 |
| /locations | 2 | 1,265 | 1,260 |
| /menu | 10.000 sinteticas | 85,653 | 72,565 |
| /locations | 10.000 sinteticas | 60,677 | 50,404 |

Con la muestra pequena no hay beneficio significativo y menu fue marginalmente
mas lento. Con filas sinteticas el ahorro fue aproximadamente 15-17%; copiado y
serializacion siguen dominando. Esto no demuestra ahorro en produccion, frecuencia
alta ni queries de cientos de ms; se necesita medir una fuente real antes de
escalar esta estrategia. Se incluye caching para cumplir y verificar el ejercicio,
no porque dos filas en memoria justifiquen por si solas una infraestructura de cache.
Una comprobacion real con uvicorn devolvio MISS seguido de HIT y no-store.

Validaciones realizadas:

- Build y lint iniciales: website y backoffice OK.
- Build y lint finales del backoffice, incluido TypeScript: OK.
- 11 tests unittest: TTL exacto, omision del cargador en HIT, claves por pais,
  limite de entradas, ambos PUT, cambio de pais, errores sin invalidacion,
  concurrencia, copia defensiva, secreto ausente, logs sin secretos y rutas sin cache.
- Dos tests Playwright: desktop y mobile OK, chunks diferidos, retorno sin nueva
  descarga, estados de seleccion, contenido, overflow y errores JS.
- Diagnosticos del editor de archivos modificados: sin errores observados.

Reproducir:

```sh
npm --prefix uis/backoffice ci
npm --prefix uis/backoffice run lint
npm --prefix uis/backoffice run build
python -m pip install -r services/catalog-api/requirements.txt
cd services/catalog-api
python -m unittest -v test_main
python benchmark.py
```

Para el navegador, desde la raiz, iniciar `npm --prefix uis/backoffice run start
-- --hostname 0.0.0.0 --port 3001` en otra terminal y ejecutar:

```sh
cd uis/backoffice
npx playwright install --with-deps chromium
npm run test:ui
```

La instalacion de librerias de sistema puede requerir intervencion del operador.
En este contenedor se validaron bibliotecas extraidas sin sudo en
`/tmp/brasaland-browser-libs/root` usando `LD_LIBRARY_PATH` al ejecutar los tests.
No son parte del repositorio. `BACKOFFICE_URL` permite usar otro puerto.

## Intercambios y exclusiones

- Se acepta antiguedad limitada del catalogo; no se reutilizarian estos TTL para
  cobros, saldos, precios finales de checkout o inventario transaccional.
- Memoria limitada por claves, pero cada lista crece con los datos; un catalogo
  real grande necesita paginacion, limites de respuesta y capacidad medida.
- El bloqueo evita carreras y estampidas locales, pero serializa accesos: si el
  cargador pasa a ser I/O lento, revisar bloqueo por clave o single-flight.
- No se cachean escrituras, health, errores, sesiones, formulario de postulacion
  ni datos privados. Los datos internos existentes siguen siendo muestras.
- No se aplican useMemo ni lazy loading a textos publicos estaticos: introducir
  cliente/hidratacion alli seria probablemente mas caro que mantener SSR estatico.
- Los modulos JS se reutilizan por su URL hash hasta un nuevo despliegue; no son
  cache de datos con TTL. La memoizacion depende de input; la cache API depende de
  tiempo y escrituras. Son mecanismos con ciclos de vida distintos.
- `npm install` detecto 12 vulnerabilidades preexistentes (11 high y 1 critical)
  en cada frontend antes de editar. No se hicieron upgrades ajenos al alcance.
- Starlette emite aviso de deprecacion del adaptador TestClient con httpx;
  las pruebas pasan. Planificar migracion de herramienta de test por separado.

Siguiente paso de produccion: conectar un repositorio persistente, medir trafico,
latencias y cambios reales, recalibrar TTL, y agregar autenticacion por roles
antes de habilitar datos internos o despliegue multirreplica.