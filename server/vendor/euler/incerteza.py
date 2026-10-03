"""Incerteza de medição por componentes, segundo o GUM (JCGM 100:2008) — Fase R.

Conceitos usados (seções do GUM citadas para conferência do revisor):

- **Incerteza-padrão** u (k = 1). Resultados exibidos como U = k·u com k = 2 (GUM 6.2.1).
  k = 2 só corresponde a ~95% se a distribuição combinada for aproximadamente normal
  (GUM 6.3.3); por isso os textos dizem "k = 2", sem prometer 95% (D36).
- **Incerteza declarada** de um instrumento é convertida conforme o tipo informado:
  `padrao` → u = valor; `expandida` com k → u = valor/k (GUM 4.3.3); `limite` → limites
  ±a com distribuição retangular, u = a/√3 (GUM 4.3.7). **Sem tipo, ou "expandida" sem k:
  hipótese do projeto (D35), não determinação do GUM** — o valor é lido como limite ±a e
  recebe o modelo retangular do GUM 4.3.7. É mais cauteloso que supor k = 2 (u = a/2),
  mas menos que supor incerteza-padrão (u = a). Nunca se assume k = 2 sem declaração.
- **Componentes** carregam a contribuição relativa **com sinal** para a grandeza final
  (coeficiente de sensibilidade × u, GUM 5.1.3) e uma **chave** da fonte de erro:
    * `medicao:` → é literalmente a mesma leitura usada em dois cálculos (ex.: o estoque
      que fecha um período e abre o seguinte): correlação r = 1 exata;
    * `instrumento:` → mesmo instrumento, leituras diferentes, sem calibração ou troca entre
      elas: o erro sistemático tende a se repetir, mas r não é conhecido. Calculamos os
      dois extremos (r = 0 e r = 1) e chamamos de **condicional** o que só é detectável
      com r = 1 (GUM 5.2.2, D37);
    * sem chave → independente.
- **Natureza**: `instrumental` (calibração/especificação), `aleatoria` (dispersão dos
  dados), `modelo` (hipótese de cálculo quantificada).
- **O que falta × o que não se inclui** (auditoria A3): uma incerteza **necessária** que não
  foi informada (instrumento sem cadastro, dispersão sem dias suficientes) vai para
  `faltam` e **nunca vira zero**: o orçamento fica `parcial` (ou `indisponivel`) e a
  grandeza fica sem incerteza (`None`). Limitações de modelo que o contrato de dados não
  permite quantificar (representatividade da amostra, título do vapor, uso do pátio) vão
  para `nao_incluidos`: são declaradas no resultado, nunca viram número inventado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import Literal

Natureza = Literal["instrumental", "aleatoria", "modelo"]
K_PADRAO = 2.0


def incerteza_padrao(
    valor: float, tipo: str | None = None, k: float | None = None
) -> tuple[float, str]:
    """Converte uma incerteza declarada em incerteza-padrão (k = 1).

    Retorna (u, como_foi_interpretada). Ver docstring do módulo (GUM 4.3.3 e 4.3.7).
    """
    if valor < 0:
        raise ValueError("incerteza declarada negativa")
    if tipo == "padrao":
        return valor, "declarada como incerteza-padrão"
    if tipo == "expandida" and k:
        return valor / k, f"declarada como expandida com k = {k:g} (GUM 4.3.3)"
    if tipo == "limite":
        return valor / sqrt(3), "declarada como limites ±a: retangular, u = a/√3 (GUM 4.3.7)"
    motivo = "expandida sem k declarado" if tipo == "expandida" else "sem tipo declarado"
    como = (
        f"{motivo}: por hipótese do projeto (D35), lida como limites ±a; modelo retangular "
        "do GUM 4.3.7, u = a/√3"
    )
    return valor / sqrt(3), como


@dataclass(frozen=True)
class Componente:
    """Contribuição de uma fonte de erro para uma grandeza.

    u_rel: contribuição relativa **com sinal** (sensibilidade × incerteza-padrão ÷ valor).
    chave: identifica a fonte de erro ("medicao:..." ou "instrumento:..."); None = independente.
    entrada: dado primário pelo qual o erro entra (ex.: "umidade_bu_frac"); permite que uma
        entrada usada por dois caminhos entre uma vez só, pelo gradiente conjunto (A2).
    """

    nome: str
    u_rel: float
    natureza: Natureza
    chave: str | None = None
    nota: str = ""
    entrada: str | None = None

    def escalado(self, fator: float) -> Componente:
        """Mesma fonte, com sensibilidade multiplicada (ex.: −1 para quem está no denominador)."""
        return Componente(
            self.nome, self.u_rel * fator, self.natureza, self.chave, self.nota, self.entrada
        )


@dataclass(frozen=True)
class Falta:
    """Incerteza necessária que não foi informada.

    sistematica: True quando é o erro de um instrumento ou método (o mesmo erro se repete
    se for o mesmo instrumento nos dois períodos); False para o resto (ex.: dispersão).
    """

    nome: str
    sistematica: bool = True


Situacao = Literal["completo", "parcial", "indisponivel"]


def _unir_faltas(*listas: list[Falta]) -> list[Falta]:
    return list(dict.fromkeys(f for lista in listas for f in lista))


@dataclass
class Orcamento:
    """Orçamento de incerteza relativa de uma grandeza de um período.

    componentes: contribuições conhecidas; nao_incluidos: limitações declaradas e não
    quantificáveis; faltam: incertezas necessárias que não foram informadas (A3).
    """

    componentes: list[Componente] = field(default_factory=list)
    nao_incluidos: list[str] = field(default_factory=list)
    faltam: list[Falta] = field(default_factory=list)

    @property
    def situacao(self) -> Situacao:
        if not self.faltam:
            return "completo"
        return "parcial" if self.componentes else "indisponivel"

    def incerteza_k2(self, valor: float) -> float | None:
        """U = 2u absoluta, só com o orçamento completo; o que falta nunca vira zero."""
        return 2 * self.u_rel() * abs(valor) if self.situacao == "completo" else None

    def u_rel(self) -> float:
        """Incerteza-padrão relativa combinada (GUM 5.1.2/5.2.2).

        Componentes com a mesma chave dentro do mesmo período somam com sinal (r = 1).
        """
        por_chave: dict[str, float] = {}
        soma = 0.0
        for c in self.componentes:
            if c.chave is None:
                soma += c.u_rel**2
            else:
                por_chave[c.chave] = por_chave.get(c.chave, 0.0) + c.u_rel
        return sqrt(soma + sum(v**2 for v in por_chave.values()))

    def mais(self, outro: Orcamento, fator: float = 1.0) -> Orcamento:
        """Junta orçamentos de um produto/razão: X = A · B^fator (fator = ±1)."""
        return Orcamento(
            self.componentes + [c.escalado(fator) for c in outro.componentes],
            list(dict.fromkeys(self.nao_incluidos + outro.nao_incluidos)),
            _unir_faltas(self.faltam, outro.faltam),
        )

    def incluindo(
        self, *componentes: Componente, nao_incluidos: list[str] | None = None
    ) -> Orcamento:
        return Orcamento(
            self.componentes + list(componentes),
            list(dict.fromkeys(self.nao_incluidos + (nao_incluidos or []))),
            list(self.faltam),
        )


def u_combinada(contribuicoes: list[tuple[float, str | None]], r_instrumento: float) -> float:
    """Incerteza-padrão de uma soma de contribuições absolutas com sinal (GUM 5.2.2).

    contribuicoes: (c_i · u_i, chave). Contribuições com a mesma chave são da mesma fonte
    de erro: somam com sinal quando r = 1 ("medicao:" sempre; "instrumento:" com
    r = r_instrumento). Sem chave → independentes.
    """
    livres = sum(u**2 for u, chave in contribuicoes if chave is None)
    por_chave: dict[str, list[float]] = {}
    for u, chave in contribuicoes:
        if chave is not None:
            por_chave.setdefault(chave, []).append(u)
    var = livres
    for chave, us in por_chave.items():
        r = 1.0 if chave.startswith("medicao:") else r_instrumento
        soma = sum(us)
        quadrados = sum(u**2 for u in us)
        var += r * soma**2 + (1 - r) * quadrados
    return sqrt(max(var, 0.0))


def contribuicoes(
    valor: float, orc: Orcamento, fator: float = 1.0
) -> list[tuple[float, str | None]]:
    """Contribuições absolutas (com sinal) de um orçamento, multiplicadas por `fator`."""
    return [(fator * c.u_rel * valor, c.chave) for c in orc.componentes]


def u_diferenca(
    valor_a: float,
    orc_a: Orcamento,
    valor_b: float,
    orc_b: Orcamento,
    r_instrumento: float,
) -> float:
    """Incerteza-padrão de Δ = b − a (absoluta), considerando fontes comuns (GUM 5.2.2).

    Para cada chave presente nos dois períodos: r = 1 se "medicao:", r = r_instrumento se
    "instrumento:". Dentro de um mesmo período, a mesma chave soma com sinal (r = 1).
    """
    a = contribuicoes(valor_a, orc_a, -1.0)
    b = contribuicoes(valor_b, orc_b, +1.0)
    return u_combinada(agregar_por_fonte(a) + agregar_por_fonte(b), r_instrumento)


def agregar_por_fonte(
    lista: list[tuple[float, str | None]],
) -> list[tuple[float, str | None]]:
    """Dentro de UM período, a mesma chave é o mesmo erro (r = 1): soma com sinal antes de
    combinar com outro período, onde r pode ser desconhecido (GUM 5.2.2)."""
    saida, por_chave = [], {}
    for u, chave in lista:
        if chave is None:
            saida.append((u, None))
        else:
            por_chave[chave] = por_chave.get(chave, 0.0) + u
    return saida + [(u, chave) for chave, u in por_chave.items()]


Detectabilidade = Literal["sim", "condicional", "nao"]


def detectabilidade(
    delta: float, u_independente: float | None, u_correlacionado: float | None, k: float = K_PADRAO
) -> Detectabilidade | None:
    """'sim' se |Δ| > k·u mesmo com erros de instrumento independentes (r = 0);
    'condicional' se só com r = 1; 'nao' se nem com r = 1; None sem incerteza."""
    if u_independente is None or u_correlacionado is None:
        return None
    if abs(delta) > k * u_independente:
        return "sim"
    if abs(delta) > k * u_correlacionado:
        return "condicional"
    return "nao"


def detectabilidade_parcial(
    delta: float, u_conhecida: float, faltam: list[Falta], k: float = K_PADRAO
) -> Detectabilidade | None:
    """Detecção com orçamento incompleto (A3). O que falta só pode aumentar a incerteza,
    então 'nao' (|Δ| ≤ k·u da parte conhecida) continua valendo; 'sim' nunca é possível.
    Se só faltam erros sistemáticos de instrumento (que se cancelam quando o mesmo erro se
    repete nos dois períodos), uma diferença maior é 'condicional'; senão, None."""
    if abs(delta) <= k * u_conhecida:
        return "nao"
    return "condicional" if all(f.sistematica for f in faltam) else None
