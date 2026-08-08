# Propuesta de Arquitectura de Backend

## 1) Objetivo del documento

Definir una propuesta inicial de arquitectura para el backend de Brasaland antes de implementar código, de forma que el equipo comparta un criterio claro sobre:

- el patrón arquitectónico más adecuado para el negocio,
- la estructura de carpetas y módulos,
- la organización de dominios y routers en FastAPI,
- la relación entre frontend y backend como sistemas separados,
- los riesgos técnicos y operativos que deben controlarse desde el inicio.

La meta es evitar un backend improvisado y alinear las primeras decisiones del sprint con la realidad operativa de Brasaland: operación multipaís, multimoneda, integraciones heterogéneas y necesidad de visibilidad casi en tiempo real.

## 2) Contexto de decisión

Brasaland opera 14 restaurantes propios entre Colombia y Florida y hoy sufre fragmentación tecnológica en casi todos los procesos clave:

- ventas y actividad de locales sin visibilidad consolidada en tiempo real,
- pedidos de abastecimiento manuales por WhatsApp o teléfono,
- POS distintos por país sin integración central,
- fidelización física sin trazabilidad digital,
- procesos de RRHH y formación distribuidos en email, Excel y Google Drive,
- reportes tardíos para dirección ejecutiva.

El backend que se diseñe debe servir como base para la iniciativa Brasaland Digital y resolver un problema estructural: Brasaland no necesita solo endpoints, necesita una plataforma central capaz de unificar datos operativos, comerciales y de soporte para dos países, dos monedas y múltiples áreas del negocio.

Además, el proyecto vive dentro de un monorepo ya organizado por responsabilidades, por lo que la propuesta debe encajar con esa estructura y dejar espacio para productos futuros de datos, IA, interfaces internas y experiencias de cliente.

## 3) Patrón arquitectónico propuesto

Se propone construir el backend como un **monolito modular** en FastAPI con **arquitectura en capas orientada por dominios**.

Las capas serían:

- **API**: routers, validación HTTP, autenticación, serialización y respuestas.
- **Aplicación**: casos de uso y orquestación de procesos del negocio.
- **Dominio**: entidades, invariantes, políticas y reglas de negocio.
- **Infraestructura**: persistencia, integraciones con POS, proveedores externos, mensajería, cache y telemetría.

### Por qué encaja con Brasaland

1. Brasaland necesita una API central única para consolidar ventas, stock, clientes, proveedores, personal y calidad. Un monolito modular permite arrancar con una superficie coherente sin repartir la lógica en varios despliegues desde el día 1.
2. La empresa todavía está resolviendo su modelo de datos común. Ir a microservicios demasiado pronto fragmentaría aún más las decisiones sobre entidades que hoy ya están dispersas.
3. FastAPI permite construir una capa HTTP moderna y bien documentada, útil para frontend, dashboards, automatizaciones y futuras capacidades de IA.
4. La separación por capas evita que reglas críticas, como conversión de moneda, consistencia de stock o validaciones de proveedores, queden mezcladas dentro de routers o integraciones.
5. Si más adelante dominios como telemetría, fidelización o analytics requieren escalado independiente, la modularidad dejará preparada una eventual extracción.

### Alternativas consideradas

- **Microservicios desde el inicio**: no son la mejor primera decisión porque Brasaland todavía necesita centralizar datos y lenguaje de negocio antes de distribuir responsabilidades técnicas.
- **MVC plano**: sería más rápido de iniciar, pero degradaría pronto la mantenibilidad porque el negocio involucra múltiples áreas, reglas transversales y varias integraciones externas.
- **Serverless puro**: puede ser útil para tareas puntuales, como jobs o webhooks, pero no como patrón dominante para un backend transaccional y analítico conectado.

## 4) Dominios del negocio que deberían estructurar el backend

Con el contexto de Brasaland ya definido, sí es posible proponer dominios iniciales concretos.

### Dominios principales

1. **Locales y operación**
   Gestiona restaurantes, turnos, estado operativo, alertas de actividad y visibilidad diaria por local.
2. **Ventas y transacciones**
   Centraliza ventas provenientes de POS, tickets, medios de pago, moneda y agregados comerciales.
3. **Inventario y abastecimiento**
   Gestiona stock por local, pedidos de insumos, quiebres, sobrestock y proyecciones de demanda.
4. **Proveedores y compras**
   Mantiene catálogo de proveedores, precios históricos, órdenes de compra y alertas de variación.
5. **Menús, recetas y estándares**
   Representa productos, recetas, cambios operativos y distribución de estándares entre locales.
6. **Clientes, fidelización y CRM**
   Gestiona perfiles de cliente, historial de pedidos, Brasa Points, segmentos y preferencias.
7. **Personas y cultura**
   Atiende colaboradores, ausencias, onboarding, vacaciones y métricas de RRHH por país.
8. **Formación**
   Organiza contenidos, itinerarios de incorporación, adopción de materiales y trazabilidad de cambios.
9. **Analytics y reporting ejecutivo**
   Expone KPIs, consultas agregadas y soporte para dashboards e informes automáticos.
10. **Identidad e integraciones**
   Resuelve autenticación, autorización, usuarios internos y la conexión con POS u otros sistemas externos.

### Criterio de priorización

No todos estos dominios deben implementarse en la primera iteración. Dado el objetivo actual del negocio, la prioridad inicial debería centrarse en:

1. locales y operación,
2. ventas y transacciones,
3. inventario y abastecimiento,
4. clientes y fidelización,
5. proveedores y compras.

Ese orden responde a los dolores más urgentes de Brasaland: visibilidad de ventas, control operativo, decisiones de abastecimiento y base de CRM digital.

## 5) Estructura propuesta de carpetas y módulos

Se propone una aplicación principal en `services/api` con una estructura reconocible en FastAPI y separada por dominio:

```text
services/
  api/
    app/
      main.py
      core/
        config.py
        security.py
        logging.py
        dependencies.py
        middleware.py
      api/
        v1/
          router.py
          health.py
          auth.py
          domains/
            locations.py
            sales.py
            inventory.py
            suppliers.py
            menu.py
            customers.py
            people.py
            training.py
            analytics.py
            integrations.py
      modules/
        locations/
          domain/
          application/
          infrastructure/
          schemas/
        sales/
          domain/
          application/
          infrastructure/
          schemas/
        inventory/
          domain/
          application/
          infrastructure/
          schemas/
        suppliers/
          domain/
          application/
          infrastructure/
          schemas/
        menu/
          domain/
          application/
          infrastructure/
          schemas/
        customers/
          domain/
          application/
          infrastructure/
          schemas/
        people/
          domain/
          application/
          infrastructure/
          schemas/
        training/
          domain/
          application/
          infrastructure/
          schemas/
        analytics/
          domain/
          application/
          infrastructure/
          schemas/
        integrations/
          domain/
          application/
          infrastructure/
          schemas/
      db/
        session.py
        migrations/
      tests/
        unit/
        integration/
```

### Justificación de esta estructura

- La separación principal es por dominio porque Brasaland necesita reflejar áreas operativas distintas, no solo agrupar archivos por tipo técnico.
- La capa `api/` expone contratos HTTP sin invadir la lógica del negocio.
- `modules/` permite mantener las reglas de cada dominio cerca de sus propios casos de uso y adaptadores.
- `core/` concentra configuración transversal relevante para operación multipaís, CORS, autenticación, logging y middleware.
- `integrations/` merece módulo propio porque Brasaland depende de POS heterogéneos por país y esa heterogeneidad no debe contaminar los demás dominios.

## 6) Organización de routers y endpoints en FastAPI

### Principio

Las rutas deben agruparse por dominio y no por pantalla o por equipo. Esto hace que la API sea reconocible, mantenible y estable para múltiples consumidores: frontend, dashboards, jobs, automatizaciones y agentes de IA.

En la practica, cada dominio deberia tener su propio `APIRouter` y todos esos routers deberian registrarse desde un agregador comun en `api/v1/router.py`. Ese punto de ensamblado permite mantener una entrada unica de versionado y evita que el crecimiento de endpoints termine concentrado en un solo archivo.

### Propuesta de prefijos

- `/api/v1/health`
- `/api/v1/auth`
- `/api/v1/locations`
- `/api/v1/sales`
- `/api/v1/inventory`
- `/api/v1/suppliers`
- `/api/v1/menu`
- `/api/v1/customers`
- `/api/v1/people`
- `/api/v1/training`
- `/api/v1/analytics`
- `/api/v1/integrations`

### Ejemplos de endpoints alineados con Brasaland

- `GET /api/v1/locations`
- `GET /api/v1/locations/{location_id}/status`
- `GET /api/v1/sales/summary?country=CO&from=...&to=...`
- `POST /api/v1/sales/ingestion/pos-events`
- `GET /api/v1/inventory/locations/{location_id}/stock-risk`
- `POST /api/v1/inventory/purchase-orders`
- `GET /api/v1/suppliers/price-history`
- `GET /api/v1/menu/items`
- `POST /api/v1/customers/loyalty/transactions`
- `GET /api/v1/customers/segments`
- `POST /api/v1/people/onboarding`
- `GET /api/v1/training/content-updates`
- `GET /api/v1/analytics/executive-dashboard`
- `POST /api/v1/integrations/webhooks/pos/{provider}`

### Reglas de diseño de API

- Un `APIRouter` por dominio o subdominio.
- Los payloads de request y response deben quedar tipados y aislados por dominio.
- Los endpoints operativos y analíticos no deben mezclarse en el mismo router si responden a casos de uso distintos.
- Las respuestas deben contemplar país, moneda y zona horaria cuando sean relevantes para el negocio.
- Los errores deben ser homogéneos, especialmente en integraciones y procesos asincrónicos.
- Los endpoints de ingestión deben diseñarse para soportar reintentos e idempotencia.

## 7) Convenciones de FastAPI investigadas y cómo influyen

La propuesta sigue convenciones ampliamente adoptadas en proyectos FastAPI de mediana escala:

1. Uso de múltiples archivos y `APIRouter` por módulo, como recomienda FastAPI para aplicaciones grandes.
2. Separación entre capa HTTP, dependencias compartidas y casos de uso.
3. Validación y serialización con modelos Pydantic para mantener contratos claros.
4. Configuración centralizada por entorno para credenciales, puertos, CORS e integraciones.
5. OpenAPI autogenerado como contrato para frontend y otros consumidores.
6. Middleware explícito para CORS, trazabilidad y manejo consistente de errores.

### Cómo afectan a Brasaland

- Brasaland necesita integrar frontend, dashboards y procesos internos; por eso OpenAPI debe asumirse como contrato base.
- La inyección de dependencias es útil para aislar sesiones de base de datos, autenticación y adaptadores de POS.
- La separación en routers por dominio evita que el crecimiento funcional de la empresa termine en un `main.py` monolítico y desordenado.
- La configuración por entorno es obligatoria debido a la operación entre países, entornos y proveedores distintos.
- La convención de usar modelos tipados de request y response influye directamente en la decisión de ubicar contratos HTTP por dominio dentro de `modules/*/schemas`, para que validación, serialización y documentación de la API queden alineadas con cada módulo.
- La convención de centralizar settings influye en la decisión de reservar `core/config.py` para variables de entorno, credenciales, CORS, países soportados y moneda por defecto, evitando que esa configuración quede dispersa entre routers o integraciones.

### Origen explícito de estas convenciones

La propuesta se apoya en:

1. Documentación oficial de FastAPI sobre aplicaciones grandes y múltiples archivos.
2. Documentación oficial de FastAPI sobre `APIRouter`.
3. Documentación oficial de FastAPI sobre `Dependencies`.
4. Documentación oficial de FastAPI sobre `CORS`.
5. Documentación oficial de FastAPI sobre settings y variables de entorno.
6. OpenAPI como especificación de contrato para integraciones cliente-servidor.

## 8) Frontend y backend como sistemas separados

### Modelo de relación

El frontend de Brasaland, ya sea web pública, app de fidelización o portales internos, debe consumir el backend exclusivamente por API. Ninguna interfaz debería depender de acceso directo a la base de datos ni de lógica embebida fuera del backend central.

Para este proyecto, la decision recomendada es mantener frontend y backend dentro del mismo monorepo, pero tratarlos como sistemas separados en terminos de responsabilidades, configuracion, despliegue y contrato de integracion. Es decir, se comparte repositorio por conveniencia organizativa, no porque deban compartir acoplamiento tecnico.

### Decisiones técnicas iniciales

1. **Versión de API desde el inicio**: usar `/api/v1` para proteger a clientes digitales e integraciones futuras.
2. **CORS explícito por entorno**: permitir en desarrollo los orígenes necesarios y en producción usar listas blancas estrictas para web, app y herramientas internas.
3. **Variables de entorno por servicio**: al menos `APP_ENV`, `API_PORT`, `DATABASE_URL`, `JWT_SECRET`, `CORS_ALLOWED_ORIGINS`, `DEFAULT_CURRENCY`, `SUPPORTED_COUNTRIES` y credenciales de POS.
4. **Autenticación centralizada**: sesiones para equipos internos y clientes deben resolverse en el backend, con políticas distintas si el caso lo requiere.
5. **Contrato API primero**: frontend y backend deben coordinarse a través de OpenAPI y mocks, no por acuerdos verbales.
6. **Observabilidad desde el día 1**: correlation IDs, logs estructurados y eventos mínimos para rastrear fallas entre POS, API y frontend.
7. **Separación de despliegue**: aunque vivan en el mismo monorepo, frontend y backend deben tener ciclos de despliegue y configuración independientes.

## 9) Consideraciones técnicas específicas de Brasaland

### Multipaís y multimoneda

El backend debe modelar explícitamente país, moneda y local porque varias preguntas del negocio comparan Colombia con Florida. No conviene dejar conversiones o contexto monetario implícitos en el frontend o en reportes manuales.

### Integraciones con POS heterogéneos

Las ventas no nacerán en un único sistema homogéneo. Por eso conviene diseñar una capa de integración que traduzca eventos o archivos de POS hacia un modelo interno unificado de venta, ticket y producto.

### Telemetría y operación en tiempo cercano al real

Las alertas como “local abierto sin ventas” requieren eventos o ingestión frecuente, no solo cierres diarios. La arquitectura debe contemplar ingestión operativa y no solo CRUD administrativo.

### Soporte para IA futura

Los casos de uso de predicción de demanda, personalización y asistentes necesitan datos ordenados y eventos confiables. La arquitectura del backend debe cuidar desde el principio trazabilidad, calidad de datos y consistencia de identificadores.

## 10) Riesgos y puntos de atención

1. **Modelo de datos demasiado ambicioso desde el inicio**: intentar cubrir todos los dominios a la vez puede frenar la entrega del primer backend útil.
2. **Dependencia excesiva de integraciones POS**: si se diseña toda la plataforma alrededor de un proveedor, se perderá flexibilidad entre países.
3. **Manejo inconsistente de monedas y fechas**: errores de conversión o zonas horarias pueden romper dashboards ejecutivos y comparativas entre mercados.
4. **Lógica de negocio en endpoints**: peligro típico en FastAPI si no se fuerza separación por capas.
5. **Módulo analítico acoplado al transaccional**: mezclar consultas pesadas con flujos operativos puede degradar tiempos de respuesta.
6. **Crecimiento desordenado del dominio de clientes**: fidelización, CRM y personalización pueden explotar de complejidad si no se define una frontera clara.
7. **Distribución inconsistente de cambios operativos**: recetas y estándares requieren trazabilidad para no perder consistencia de marca.

### Mitigaciones recomendadas

- Empezar por un núcleo operativo reducido: locales, ventas, inventario y clientes.
- Diseñar adaptadores por proveedor en el dominio de integraciones, con contrato interno estable.
- Definir desde el inicio reglas únicas para moneda, país y zona horaria.
- Mantener el dominio analítico separado del transaccional, aunque compartan aplicación al principio.
- Exigir revisiones de PR enfocadas en fronteras de dominio, no solo en comportamiento HTTP.

## 11) Decisiones iniciales para el primer sprint

1. Crear el esqueleto de `services/api` con los módulos `locations`, `sales`, `inventory`, `customers`, `suppliers`, `auth` e `integrations`.
2. Definir un modelo de datos común mínimo para local, venta, item de menú, stock, cliente y proveedor.
3. Implementar `health`, autenticación y endpoints base de lectura para locales, ventas resumidas e inventario crítico.
4. Preparar un flujo inicial de ingestión desde POS o fuentes disponibles hacia el dominio de ventas.
5. Publicar OpenAPI y usarlo como contrato con frontend y dashboards.
6. Dejar listos settings de CORS, moneda, país y credenciales de integración.

## 12) Cierre

La arquitectura recomendada para Brasaland es un monolito modular en FastAPI con separación por dominio y por capas. Es la opción que mejor equilibra velocidad, orden técnico y capacidad de evolución para una empresa que necesita centralizar su operación digital sin agregar complejidad operativa prematura.

Esta propuesta no solo organiza código: organiza cómo Brasaland convertirá ventas, inventario, clientes, proveedores y operación diaria en una plataforma común. Si el backend respeta esta estructura desde el inicio, la empresa quedará mejor posicionada para avanzar hacia dashboards en tiempo real, automatizaciones e iniciativas de IA sobre datos confiables.