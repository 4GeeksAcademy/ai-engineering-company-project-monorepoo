# Auditoria de serializacao da API

Data: 2026-10-06
Aplicacao: `services/api/` (Brasaland API)

## Escopo

A API atualmente tem uma unica rota de negocio declarada: `GET /health`. Nao ha
rotas de autenticacao, leitura de recursos, escrita, listagem ou relacoes ORM.
Por isso, nao existem payloads de usuarios, credenciais, chaves estrangeiras ou
objetos ORM a auditar nesta versao.

FastAPI tambem registra rotas auxiliares para documentacao. Elas sao listadas
separadamente porque entregam HTML ou o proprio documento OpenAPI, nao dados de
negocio serializados por esquemas Pydantic. Essas rotas nao aparecem como
operacoes de negocio no documento OpenAPI.

## Rotas de negocio

| Metodo e rota | Proposito | Comportamento original | Estado original | Contrato alvo e alteracao |
| --- | --- | --- | --- | --- |
| `GET /health` | Verificar disponibilidade da API | Devolvia `{"status": "ok"}` como `dict[str, str]`, inferido da anotacao de retorno; o decorator nao declarava `response_model`. Nao retornava ORM. | ⚠️ Parcialmente serializado | Resposta explicita `HealthResponse` com o unico campo `status: "ok"`. O esquema nomeado limita e documenta o payload. |

## Rotas auxiliares do FastAPI

| Metodo e rota | Proposito | Resposta atual | Tratamento |
| --- | --- | --- | --- |
| `GET`, `HEAD /openapi.json` | Expor o contrato OpenAPI | JSON gerado a partir das rotas da aplicacao | Gerida pelo FastAPI; nao contem dados de negocio nem objetos ORM. |
| `GET`, `HEAD /docs` | Interface Swagger UI | HTML da documentacao | Gerida pelo FastAPI; nao e uma resposta de recurso da API. |
| `GET`, `HEAD /docs/oauth2-redirect` | Callback OAuth da Swagger UI | HTML de callback | Gerida pelo FastAPI; nao e uma resposta de recurso da API. |
| `GET`, `HEAD /redoc` | Interface ReDoc | HTML da documentacao | Gerida pelo FastAPI; nao e uma resposta de recurso da API. |

As rotas auxiliares nao aceitam nem devolvem modelos de dominio, portanto nao
se lhes aplica um `response_model` Pydantic de recurso. Permanecem acessiveis
para documentacao e verificacao manual.

## Resultado apos a implementacao

| Metodo e rota | `response_model` explicito | Payload permitido | Estado |
| --- | --- | --- | --- |
| `GET /health` | `HealthResponse` | `{"status": "ok"}` | ✅ Ja serializado |

Nao ha endpoints de escrita, logo nao sao necessarios esquemas de entrada nesta
versao. Tambem nao ha relacoes para aninhar ou achatar. Quando forem adicionados
endpoints de dominio, esta auditoria deve identificar os consumidores e os
campos publicos necessarios antes de definir cada esquema.

## Verificacao

- `GET /health` respondeu `200` com `{"status": "ok"}`.
- `GET /docs` e `GET /redoc` responderam `200`.
- `GET /openapi.json` respondeu `200` e declarou `HealthResponse` como esquema
  da resposta de `/health`, contendo somente `status`.
- A aplicacao foi iniciada com Uvicorn e nao retorna objetos ORM em nenhuma
  rota de negocio existente.