# EULER Startup — deploy Vercel

Versão preparada para publicar o frontend estático e a API Python no mesmo projeto Vercel.

## Estrutura

- `index.html` + `assets/`: site e demonstração interativa
- `api/analyze.py`: função Python usada por `POST /api/analyze`
- `api/status.py`: teste simples em `GET /api/status`
- `api/euler_engine.zip`: motor EULER empacotado como biblioteca interna
- `requirements.txt`: dependências Python instaladas pela Vercel
- `vercel.json`: força preset **Other**, remove Build/Output antigos e configura a função
- `.python-version`: fixa Python 3.12

## Deploy

1. Suba **o conteúdo desta pasta na raiz do repositório GitHub**.
2. Na Vercel, use **Root Directory = `./` (raiz do repositório)**.
3. Importe o repositório e clique em **Deploy**.

Não configure `dist`, não crie Build Command e não selecione `server` como Root Directory.
O `vercel.json` já redefine Framework, Build Command e Output Directory para os valores corretos.

## Teste depois do deploy

- Abra `/` para conferir o site.
- Abra `/api/status` e confirme que retorna JSON com `"ready": true`.
- No site, use **Testar a EULER** e carregue um dos exemplos para validar `POST /api/analyze`.

## Observação

O primeiro deploy pode demorar mais porque a Vercel precisa instalar `pandas`, `numpy`, `scipy` e `iapws` para a função Python. Isso é esperado.
