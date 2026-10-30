# Brasaland API

The centralized FastAPI application for Brasaland. The initial endpoint is
`GET /health`; interactive API documentation is available at `/docs` while the
server is running.

## Run locally

From this directory, create and activate a virtual environment, then run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

The development server listens on `http://127.0.0.1:8000` by default.

Spanish documentation: [README.es.md](./README.es.md).