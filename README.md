# EULER-Startup

Landing page da EULER com uma demonstracao interativa do motor de investigacao.
Permite preencher os 78 campos do software, importar CSV ou editar exemplos
simulados. A resposta publica inclui uma previa dos resultados e um convite
para conhecer a investigacao completa.

## Executar

Linux/macOS, na pasta deste projeto:

```sh
bash abrir-demo.sh
```

Windows: execute `ABRIR-DEMO.cmd`. E necessario Python 3.11 ou superior.
Na primeira execucao, a instalacao das dependencias requer internet.

Com o servidor iniciado, abra http://127.0.0.1:8766/#euler-demo.
Mantenha o terminal aberto; use Ctrl+C para encerrar.

Para usar outra porta:

```sh
bash abrir-demo.sh --port 8767
```

Nesse caso, abra http://127.0.0.1:8767/#euler-demo.

## Entrega

- O formulario aceita dados proprios e dois casos sinteticos editaveis.
- O calculo usa o motor Python original, incluido em `server/vendor/euler/`.
- A API entrega apenas a previa comercial, preservando as limitacoes da analise.
- O contato prepara um e-mail; nao envia mensagens automaticamente.
- Os registros da investigacao nao sao incluidos no contato comercial.

Para mover o projeto, leve esta pasta com `index.html`, `og-image.png`, `assets/`,
`server/` e os scripts de abertura. O ambiente `.venv/` deve ser recriado no
destino. Abrir apenas o HTML ou publicar somente arquivos estaticos nao executa
o motor Python.

Detalhes, limites e comandos de teste: [EMULADOR.md](EMULADOR.md).

## Verificacao desta revisao

Os testes JavaScript e os oito testes de integracao do motor passaram.
Foram acrescentados testes para carregamentos cancelados ou substituidos e
para importacao de CSV durante a troca de grupo.

A verificacao da cena 3D passou em Chromium, em desktop (1440 px) e celular
(375 px), incluindo pixels do canvas, isolamento da demonstracao, abertura e
fechamento da janela e retorno a cena. O teste esta em
`tests/check-scene-browser.py`; o fluxo completo esta em `tests/check-demo-browser.py`.
