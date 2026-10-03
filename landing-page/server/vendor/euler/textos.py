"""Textos fixos mostrados ao usuário final (app e relatórios).

O rodapé de segurança é obrigatório em todas as telas e relatórios
(docs/produto/visao_produto.md, seção "Rodapé de segurança"). O teste
tests/test_textos.py garante que o texto daqui é idêntico ao do documento.
"""

RODAPE_SEGURANCA = (
    "Ferramenta de registro e apoio à investigação. Não emite comandos operacionais "
    "nem substitui procedimentos da instalação, alarmes, intertravamentos ou a "
    "avaliação do responsável técnico. Não é um Registro de Segurança conforme a NR-13."
)

FRASE_PRODUTO = "Quanto de energia a fábrica comprou, quanto virou vapor e onde o resto foi parar."

PERGUNTA_CENTRAL = (
    "O consumo de combustível mudou. O que os registros sustentam, quais explicações "
    "continuam possíveis e qual verificação separa essas explicações?"
)

AVISO_PROTOTIPO = (
    "Protótipo em construção (Fase 0). Todos os dados usados aqui são sintéticos ou públicos."
)

SITUACAO_MODELO = (
    "Situação do modelo: cálculos implementados e verificados por testes automáticos; "
    "hipóteses físicas em revisão científica, ainda sem aprovação; sem validação com dados "
    "reais de caldeira."
)
"""Frase única usada na tela inicial e no relatório (separa as três situações)."""

ESTAGIOS_MODELO = (
    (
        "Implementado e verificado",
        (
            "Cálculos de vapor (IAPWS-IF97), combustão, balanço e incerteza, e as regras da "
            "investigação. Cerca de 300 testes automáticos, parte deles contra referências "
            "externas."
        ),
    ),
    (
        "Em revisão científica",
        (
            "Equações, critérios e hipóteses (ex.: uso do pátio, amostragem de umidade, "
            "leitura das incertezas) aguardam revisores. Nenhuma está aprovada ainda."
        ),
    ),
    (
        "Ainda não feito",
        "Validação com dados reais de uma caldeira, com resultado de referência medido.",
    ),
)
