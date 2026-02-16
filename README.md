# Robo de Coleta - Server

API Flask para previsao de multiplicadores 10+ com dados do Firebase.

## Estrutura

- `server/app.py`: API Flask
- `server/requirements.txt`: dependencias Python
- `render.yaml`: configuracao de deploy no Render

## Rotas

- `GET /health`
- `GET /bet/10-plus`

## Rodar localmente

```powershell
cd "D:\Robo de coleta"
.venv\Scripts\python.exe -m pip install -r server/requirements.txt
.venv\Scripts\python.exe server/app.py
```

## Variaveis de ambiente

- `FIREBASE_DB_URL` (opcional; default ja configurado no codigo)
- `FIREBASE_SERVICE_ACCOUNT_JSON` (recomendado para deploy)
- `FIREBASE_SERVICE_ACCOUNT` (opcional, caminho de arquivo local)
- `PORT` (definido automaticamente no Render)

### Firebase no Render (recomendado)

No Render, defina `FIREBASE_SERVICE_ACCOUNT_JSON` com o JSON completo da service account em uma unica linha.

## Deploy no Render

1. Suba este repositorio no GitHub.
2. No Render, crie um novo Web Service usando o repo.
3. O Render vai ler `render.yaml` automaticamente.
4. Configure as variaveis `FIREBASE_DB_URL` e `FIREBASE_SERVICE_ACCOUNT_JSON`.
5. Deploy.

## Seguranca

- Nao suba `server/adminService.json` para o GitHub.
- Nao suba `server/modelo_estado.json` (estado local de execucao).
