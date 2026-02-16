# predit

API Flask em `server/app.py`.

## Local

```powershell
.venv\Scripts\python.exe -m pip install -r server/requirements.txt
.venv\Scripts\python.exe server/app.py
```

## Render

- O projeto ja tem `render.yaml`.
- Build: `pip install -r server/requirements.txt`
- Start: `gunicorn server.app:app`

Variaveis no Render:
- `FIREBASE_DB_URL`
- `FIREBASE_SERVICE_ACCOUNT_JSON`

Rotas:
- `GET /health`
- `GET /bet/10-plus`
