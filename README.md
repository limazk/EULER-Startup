# EULER

Site institucional com demonstracao interativa de investigacao do consumo de
combustivel em caldeiras. O motor cientifico compara dois periodos e apresenta
consumo especifico, hipoteses compativeis, incertezas e limites da analise.
Os exemplos sao sinteticos; a previa nao substitui uma investigacao tecnica.

## Funcionalidades

- Formulario com 78 campos, importacao CSV e exemplos editaveis.
- Comparacao com dados suficientes, limitados ou insuficientes.
- Cena 3D, navegacao responsiva e modo de leitura sem WebGL.
- Processamento sem persistencia dos registros pela aplicacao.
- Contato por e-mail preparado no navegador, sem envio automatico dos registros.

## Arquitetura e tecnologias

```text
Frontend -> POST /api/analyze -> Python -> motor EULER -> JSON

index.html                    Pagina publica
assets/                       CSS, JavaScript, esquema e exemplos
og-image.png                  Imagem social
api/analyze.py                Funcao Python da Vercel
server/app.py                 Servidor local, validacao e previa
server/vendor/euler/          Motor cientifico preservado
server/requirements.txt       Dependencias locais
tests/                       Testes JS, Python, HTTP e navegador
pyproject.toml                Dependencias da Vercel
vercel.json                   Configuracao e bloqueio de arquivos internos
```

O frontend HTML/CSS/JavaScript ja esta compilado, incluindo Three.js. Nao ha build
npm. O servidor usa a biblioteca padrao Python; pandas e NumPy tratam dados,
IAPWS calcula propriedades termodinamicas e openpyxl permite a leitura de Excel
no importador do motor. As quatro dependencias sao utilizadas e consistentes
nos dois manifestos. O formulario publico importa CSV.
O bundle `assets/index-CBAnsQIh.js` e seus estilos sao necessarios ao site.
Fontes externas usam Google Fonts.

## Requisitos e instalacao

Python 3.11 ou superior com `venv` e `pip`, Git e internet para instalar pacotes.
Node.js 20 ou superior e necessario apenas para os testes JavaScript.

```sh
git clone https://github.com/limazk/EULER-Startup.git
cd EULER-Startup
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.txt
.venv/bin/python -m pip check
.venv/bin/python server/app.py
```

Abra http://127.0.0.1:8766/ ou http://127.0.0.1:8766/#euler-demo.
Use Ctrl+C para encerrar; acrescente `--port 8767` para outra porta.
O servidor local fica restrito a `127.0.0.1` por padrao.

Atalho Linux/macOS: `bash abrir-demo.sh`. No Windows, execute `ABRIR-DEMO.cmd`,
que cria `.venv` e instala as dependencias. Para comandos manuais no Windows,
use `py -3 -m venv .venv` e `.venv\Scripts\python.exe` no lugar de
`.venv/bin/python`. Nao e necessario configurar secrets ou criar `.env`.

## API

`POST /api/analyze`, na mesma origem do site, recebe `Content-Type: application/json`.
O corpo tem `tables` (grupos e linhas conforme `assets/euler-schema.json`),
`altitude` (metros, opcional), `reference` e `comparison` (pares de datas ISO 8601
com fuso horario). Os periodos nao podem se sobrepor. Limites: 3 MB, 5.000 registros
e uma unica caldeira por requisicao. Campos vazios representam dados ausentes.

Exemplo executavel com o servidor local ativo:

```sh
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from urllib.request import Request, urlopen
payload = {
    "tables": json.loads(Path("assets/euler-example-complete.json").read_text()),
    "altitude": 1000,
    "reference": ["2026-08-03T07:30:00-03:00", "2026-08-31T07:30:00-03:00"],
    "comparison": ["2026-08-31T07:30:00-03:00", "2026-09-14T07:30:00-03:00"],
}
request = Request("http://127.0.0.1:8766/api/analyze",
                  data=json.dumps(payload).encode(),
                  headers={"Content-Type": "application/json"})
with urlopen(request) as response:
    print(json.dumps(json.load(response), ensure_ascii=False, indent=2))
PY
```

Respostas: `200` para previa (`supported`, `limited` ou `insufficient`) ou
avisos de importacao (`validation: true`); `403` para origem rejeitada; `405`
para GET; `413` para tamanho invalido; `415` para formato incorreto; `422` para
entrada invalida; `500` para falha interna. Erros incluem `message`, sem traceback.
A API usa `Cache-Control: no-store`. A resposta publica preserva limitacoes
cientificas, sem expor a investigacao completa. O servidor de desenvolvimento
nao deve ser usado como servidor publico de producao.

## Testes

```sh
node --test tests/*.test.mjs
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

Os testes Python verificam o motor com dados sinteticos e os dois adaptadores HTTP,
incluindo JSON invalido, origem, limites, status e bloqueio de arquivos privados.
Os testes dos adaptadores processam requisicoes HTTP em memoria, sem abrir portas.
Os testes de navegador abaixo verificam a conexao com um servidor real.

Para testar o navegador, mantenha o servidor local ativo em outro terminal:

```sh
.venv/bin/python -m pip install playwright
.venv/bin/python -m playwright install chromium
.venv/bin/python tests/check-demo-browser.py
.venv/bin/python tests/check-scene-browser.py
```

Em Linux, instale tambem as bibliotecas de sistema solicitadas pelo Playwright.
Use `EULER_CHROMIUM_PATH=/usr/bin/chromium` para um Chromium do sistema e
`EULER_TEST_URL=http://127.0.0.1:8767/` para outra porta.
Os testes cobrem fluxo completo, layouts de 320 a 1440 pixels, modal, fallback
e pixels da cena WebGL. Capturas ficam em `tests/artifacts/` (ignorado).

## Segurança da prévia pública

A landing page é pública; os controles protegem principalmente a API de demonstração e evitam exposição acidental de arquivos internos.

O projeto aplica CSP e headers contra clickjacking/sniffing, HSTS na Vercel, restrição de métodos/origem para `POST /api/analyze`, limite de 3 MB, validação rigorosa dos registros, tratamento de erro sem traceback e rate limit best-effort por cliente. Consulte [`SECURITY.md`](./SECURITY.md) para detalhes e a configuração recomendada do Firewall da Vercel.

> Em produção, use também Rate Limiting no Firewall da Vercel para `/api/analyze`. O limitador Python não é global entre todas as instâncias serverless.

## Deploy na Vercel

Importe o repositorio GitHub e configure:

| Campo | Valor |
| --- | --- |
| Framework Preset | **Other** |
| Root Directory | **raiz do repositorio** (campo vazio ou `.`) |
| Build Command | **vazio** (nao necessario) |
| Output Directory | **vazio** (nao necessario) |
| Install Command | padrao automatico |

Nao selecione `server` como Root Directory. A raiz contem o site estatico,
`api/`, `pyproject.toml` e `vercel.json`. A Vercel detecta a funcao Python em
`api/analyze.py` e instala as dependencias do manifesto da raiz, conforme a
[documentacao oficial do runtime Python](https://vercel.com/docs/functions/runtimes/python).
O limite configurado para a funcao e 30 segundos. Nao ha necessidade de variaveis
de ambiente ou credenciais da aplicacao.

`server/` e seu motor devem entrar no pacote da funcao. O bloqueio HTTP em
`vercel.json` impede acesso publico ao codigo sem remove-lo do deploy.
`.vercelignore` exclui testes, ambientes, caches e scripts locais, preservando
os arquivos de producao. A publicacao real deve ser validada no painel e nos logs
da Vercel: abra `/`, execute uma previa e confirme que `/server/app.py` retorna 404.
Testes locais dos adaptadores nao substituem essa verificacao na plataforma.

## GitHub e arquivos ignorados

Antes de enviar alteracoes:

```sh
git status
git diff --check
node --test tests/*.test.mjs
.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
git add -A
git diff --cached
git commit -m "Descreva a alteracao"
git push origin HEAD
```

Confira o conteudo preparado antes de commitar. `.gitignore` cobre ambientes
virtuais, bytecode Python, caches, cobertura, `.vercel/`, capturas de testes,
logs, arquivos do sistema e `.env*` (com excecao de `.env.example`). Nenhum desses
arquivos e necessario para clonar e executar o projeto. Nunca versione credenciais.
