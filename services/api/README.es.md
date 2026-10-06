# API de Brasaland

Aplicación FastAPI centralizada para Brasaland. El endpoint inicial es
`GET /health`; la documentación interactiva está disponible en `/docs` mientras
el servidor está activo.

## Ejecución local

Desde este directorio, crea y activa un entorno virtual y ejecuta:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Por defecto, el servidor de desarrollo escucha en `http://127.0.0.1:8000`.

English documentation: [README.md](./README.md).