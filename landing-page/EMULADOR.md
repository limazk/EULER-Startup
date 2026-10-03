# EULER — demonstração integrada à landing page

A demonstração existente foi ampliada, preservando o site e seus bundles originais. O convite fica depois de `#investigacao`; o botão “Testar a EULER” abre esse trecho. O formulário funciona em uma janela própria e retorna à proposta comercial existente em `#proposta`.

## Experimentar localmente

Com o serviço ativo, abra http://127.0.0.1:8766/#euler-demo.

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/pip install -r server/requirements.txt
.venv/bin/python server/app.py --port 8766
```

Ou execute `bash abrir-demo.sh`, que prepara o ambiente caso necessário.

No Windows, use `ABRIR-DEMO.cmd` com Python 3.11 ou superior instalado. Abra o endereço indicado no terminal e mantenha a janela aberta.

Não basta abrir `index.html` diretamente: o cálculo usa o motor Python original. Uma hospedagem apenas estática, como GitHub Pages, precisa de um serviço Python separado, com `/api/analyze` encaminhado pelo mesmo domínio. Nenhuma publicação, alteração remota ou envio de dados reais foi realizado neste trabalho.

## O que está implementado

- Entrada manual de todos os **78 campos** do contrato original, distribuídos em cinco grupos: operação (39), combustível (10), amostras (14), eventos (5) e instrumentos (10).
- Campos complementares expansíveis, seleção de registros, adição, duplicação, remoção, importação de CSV e download de modelos. O CSV acrescenta registros: não substitui o preenchimento existente.
- Exemplos sintéticos originais dos atos completo e insuficiente, com os mesmos registros de operação e incertezas diferentes. Todos os valores continuam editáveis.
- Revisão dos registros, altitude e seleção de dois períodos com datas e horários de Brasília. Os períodos não podem se sobrepor.
- Chamada real ao motor original: importação, qualidade de dados, propriedades do vapor, balanços, incertezas e investigação conforme as capacidades habilitadas pelos registros. Não há respostas fixas ou probabilidades inventadas.
- Prévia com consumo específico, variação, gráfico comparativo, até duas explicações compatíveis, limitações, avisos de qualidade e próxima verificação.
- Convite ao produto completo com evidências, incertezas detalhadas e relatório, direcionado ao formulário comercial existente. O botão não transmite os registros nem promete desbloqueio imediato.
- Modal acessível, controle de foco, teclado, Escape, responsividade, mensagens de erro e preservação do preenchimento ao fechar e reabrir na mesma página.
- Resultados antigos são descartados após alterações. Cancelamentos não podem sobrescrever uma análise posterior.
- Exemplos que terminam de carregar após fechar a janela são descartados. CSVs permanecem no grupo escolhido no início da importação; reiniciar, fechar ou selecionar outro arquivo invalida a leitura pendente.

## Limite comercial e tratamento de dados

A API calcula a investigação e devolve somente a projeção pública da prévia. O JSON completo, a decomposição financeira e as evidências detalhadas não são enviados escondidos ao navegador. As limitações necessárias para interpretar o resultado continuam visíveis.

Os registros são mantidos na memória do navegador até “Gerar prévia”. Nesse momento são enviados ao serviço do próprio site, processados em memória e descartados após a requisição. Não há banco de dados, armazenamento local persistente, telemetria de registros ou integração com terceiros. O fechamento da janela preserva o formulário; recarregar a página o limpa.

O protótipo aceita uma caldeira por análise, até 5.000 registros e 3 MB por envio. A importação da interface aceita CSV UTF-8 com cabeçalhos do modelo, separador vírgula ou ponto e vírgula. Números admitem vírgula ou ponto decimal, sem separadores de milhar. Os limites existem para a demonstração pública; não representam a capacidade total do motor.

O serviço incluso é um servidor local de demonstração. Para publicação pública, usar a infraestrutura adequada ao tráfego esperado, HTTPS e roteamento do serviço Python. Não publicar `server/`, testes ou ambientes virtuais como arquivos estáticos.

## Organização

- `assets/euler-demo.js`: componente e fluxo da demonstração, isolados em Shadow DOM.
- `assets/euler-demo.css`: estilos internos, alinhados às variáveis visuais da landing.
- `assets/euler-demo-data.mjs`: leitura de CSV e validações do formulário.
- `assets/euler-schema.json`: metadados gerados do contrato original.
- `assets/euler-example-*.json`: os dois casos sintéticos originais, em formato editável.
- `server/app.py`: validação do envio, integração com o motor e projeção pública dos resultados.
- `server/vendor/euler/`: cópia inalterada dos 29 arquivos Python do motor.
- `assets/euler-demo-core.mjs`: calculadora anterior, preservada por compatibilidade; não é usada na nova interface.

Os bundles `assets/index-CBAnsQIh.js` e `assets/index-nbNCdXHx.css` não foram editados. `assets/euler-demo-scene.css` isola as camadas fixas da cena (canvas, etiquetas, pontos clicáveis e painéis) quando a demonstração ocupa o centro da tela ou está aberta. A rolagem atualiza esse estado inclusive em seções maiores que a tela. Ao sair, as camadas voltam a seguir a cena original. Entrar na demonstração encerra a exploração 3D pelos controles existentes, liberando a câmera e a rolagem.

## Origem

- Landing: https://github.com/limazk/EULER-Startup — cópia local existente, com alterações anteriores preservadas.
- Motor e exemplos: https://github.com/rodriguesadryan06-a11y/softwer-euler — commit local `b9bc9ca2aa71e2369fac293b6eeff6196df138c9`.
- Não foram alteradas equações, tolerâncias ou decisões físicas do software. Os metadados vêm de `euler/io/esquemas.py`; os exemplos vêm de `demo/caso_demo_completo` e `demo/caso_demo`.

## Verificações

```sh
node --test tests/*.test.mjs
.venv/bin/python -m unittest discover -s tests -p 'test_preview_api.py' -v
```

Para o teste real de navegador, mantenha o serviço na porta 8766, instale Playwright no ambiente de desenvolvimento e execute:

```sh
.venv/bin/pip install playwright
.venv/bin/python tests/check-demo-browser.py
.venv/bin/python tests/check-scene-browser.py
```

O teste usa Chromium em `/usr/bin/chromium`; ajuste esse caminho em outro sistema. As capturas geradas ficam em `tests/artifacts/`, fora do controle de versão.

O teste da cena requer WebGL, verifica pixels do canvas e a separação entre cena e demonstração em desktop e celular. Ele aceita `EULER_TEST_URL` para testar outra porta. Após a liberação do ambiente, passou em Chromium nas larguras de 1440 e 375 px, incluindo abertura e fechamento da janela e retorno à cena.

Os testes verificam os dois atos, efeito de mudanças nas entradas, separação entre ausência e zero, equivalência entre ponto e vírgula decimal, datas inválidas, fronteira da prévia comercial, entradas próprias, telas de 320 a 1440 px, teclado, retorno ao contato e modo leitura. Nenhum dado real de cliente é usado.
