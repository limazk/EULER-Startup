# EULER — Third-Party Notices

Este arquivo mantém um inventário mínimo dos componentes de terceiros identificados na versão pública da EULER.

> Este inventário não substitui os textos integrais das licenças, avisos de copyright ou obrigações dos projetos de origem. Deve ser revisado sempre que uma dependência for adicionada, removida ou atualizada.

## Dependências Python

| Componente | Versão declarada no projeto | Licença identificada | Uso na EULER |
| --- | --- | --- | --- |
| pandas | 3.0.6 | BSD | Tratamento e análise de dados |
| NumPy | >= 2.0 | BSD modificada / BSD-3-Clause | Computação numérica |
| iapws | 1.5.5 | GNU GPL v3 | Propriedades termodinâmicas de água/vapor |
| openpyxl | >= 3.1 | MIT | Leitura de arquivos Excel no motor/importador |

## Frontend e recursos visuais

| Componente | Licença identificada | Uso na EULER |
| --- | --- | --- |
| Three.js | MIT | Cena e recursos 3D da interface |
| Geist / Geist Mono | SIL Open Font License 1.1 | Tipografia da interface |

## Observações importantes

1. O código próprio da EULER não recebe automaticamente a licença dos componentes permissivos apenas por utilizá-los.
2. Componentes copyleft, especialmente o pacote `iapws` sob GPLv3, exigem análise específica das obrigações aplicáveis à forma de uso, distribuição e eventual entrega do software.
3. Antes de distribuir pacotes executáveis, código-fonte ou imagens de implantação contendo dependências de terceiros, revisar os textos integrais das licenças e os avisos de copyright exigidos.
4. O bundle JavaScript compilado deve ser reavaliado sempre que o frontend for recompilado para identificar componentes adicionais eventualmente incorporados.
5. Este arquivo não concede licença para o código próprio da EULER.

## Referências dos projetos

- pandas: https://pandas.pydata.org/
- NumPy: https://numpy.org/
- openpyxl: https://pypi.org/project/openpyxl/
- iapws: https://pypi.org/project/iapws/1.5.5/
- Three.js: https://github.com/mrdoob/three.js
- Geist: https://github.com/vercel/geist-font

Última revisão deste inventário: 2026-10-05.
