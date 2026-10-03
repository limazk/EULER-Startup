"""Linha de base e comparação entre períodos (E15) e detecção de degrau (T12).

Uma mudança só é chamada de **detectável** quando é maior que U = 2u da diferença.
Para leituras do diário, a dispersão da média de um período vem da variação entre
**médias diárias** (leituras de 2 em 2 h são correlacionadas; dias são mais próximos de
independentes) — D25. Quando as grandezas trazem orçamento de incerteza (Fase R), a
diferença considera os erros que se repetem nos dois períodos (GUM 5.2.2):

- `sim`: detectável mesmo supondo erros de instrumento independentes (r = 0);
- `condicional`: só detectável se o erro do mesmo instrumento se repetir (r = 1);
- `nao`: nem assim; `None`: falta incerteza para decidir (D37).

Orçamento incompleto (auditoria A3): o que falta só pode aumentar a incerteza. Então
`nao` continua seguro (a diferença cabe na parte conhecida); `sim` nunca sai; se só falta
o erro sistemático de algum instrumento, uma diferença maior é `condicional` (vale se o
mesmo erro se repetir nos dois períodos); senão, `None`. O que falta vai em `faltam`.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import pandas as pd

from euler.incerteza import (
    Componente,
    Detectabilidade,
    Orcamento,
    detectabilidade,
    detectabilidade_parcial,
    u_diferenca,
)
from euler.tipos import Grandeza


@dataclass(frozen=True)
class Estatistica:
    """Média de uma leitura no período, com erro-padrão das médias diárias."""

    media: float
    unidade: str
    n_leituras: int
    n_dias: int
    erro_padrao: float | None

    @property
    def incerteza(self) -> float | None:
        """Incerteza expandida da média (k = 2)."""
        return None if self.erro_padrao is None else 2 * self.erro_padrao


def estatistica_diaria(
    valores: pd.Series, instantes: pd.Series, unidade: str
) -> Estatistica | None:
    """Média e erro-padrão (pelas médias diárias) de uma leitura; None sem leituras."""
    df = pd.DataFrame(
        {"v": pd.to_numeric(valores, errors="coerce").astype(float).values, "t": instantes.values}
    ).dropna()
    if df.empty:
        return None
    diarias = df.groupby(pd.to_datetime(df["t"]).dt.date)["v"].mean()
    erro = float(diarias.std(ddof=1) / sqrt(len(diarias))) if len(diarias) >= 2 else None
    return Estatistica(float(df["v"].mean()), unidade, len(df), len(diarias), erro)


@dataclass(frozen=True)
class Comparacao:
    """Diferença entre o período de comparação e o de referência.

    incerteza_delta: U = 2u da diferença supondo erros de instrumento independentes (r = 0).
    incerteza_delta_correlacionada: U supondo que o mesmo instrumento repete o erro (r = 1).
    detectavel: True ('sim'), False ('nao'), None ('condicional' ou sem incerteza).
    faltam: incertezas necessárias que não foram informadas (orçamento incompleto, A3);
        nesse caso incerteza_delta é None e incerteza_delta_correlacionada é só a parte
        conhecida (um mínimo).
    """

    nome: str
    unidade: str
    referencia: float | None
    comparacao: float | None
    delta: float | None
    incerteza_delta: float | None
    detectavel: bool | None
    incerteza_delta_correlacionada: float | None = None
    detectabilidade: Detectabilidade | None = None
    faltam: tuple[str, ...] = ()

    @property
    def disponivel(self) -> bool:
        return self.delta is not None


def _como_grandeza(x: Estatistica | Grandeza | None) -> Grandeza | None:
    if x is None or isinstance(x, Grandeza):
        return x
    orc = Orcamento()
    if x.erro_padrao is not None and x.media != 0:
        orc.componentes.append(Componente("dispersão", x.erro_padrao / x.media, "aleatoria"))
    return Grandeza(
        x.media, x.unidade, "medido", x.incerteza, "", orc if x.erro_padrao is not None else None
    )


def comparar(
    nome: str,
    unidade: str,
    referencia: Estatistica | Grandeza | None,
    comparacao: Estatistica | Grandeza | None,
) -> Comparacao:
    """Compara dois períodos; a detectabilidade usa U = 2u da diferença (ver docstring)."""
    a, b = _como_grandeza(referencia), _como_grandeza(comparacao)
    if a is None or b is None:
        return Comparacao(
            nome, unidade, None if a is None else float(a.valor), None if b is None else float(b.valor),
            None, None, None,
        )  # fmt: skip
    delta = float(b.valor - a.valor)
    if a.orcamento is not None and b.orcamento is not None:
        u0 = u_diferenca(a.valor, a.orcamento, b.valor, b.orcamento, r_instrumento=0.0)
        u1 = u_diferenca(a.valor, a.orcamento, b.valor, b.orcamento, r_instrumento=1.0)
        u_ind, u_cor = max(u0, u1), min(u0, u1)
        faltam = list(dict.fromkeys(a.orcamento.faltam + b.orcamento.faltam))
        if faltam:
            nivel = detectabilidade_parcial(delta, u_cor, faltam)
            return Comparacao(
                nome, unidade, float(a.valor), float(b.valor), delta, None,
                {"nao": False}.get(nivel), float(2 * u_cor), nivel, tuple(f.nome for f in faltam),
            )  # fmt: skip
    elif a.incerteza is not None and b.incerteza is not None:
        u_ind = u_cor = sqrt((a.incerteza / 2) ** 2 + (b.incerteza / 2) ** 2)
    else:
        return Comparacao(nome, unidade, float(a.valor), float(b.valor), delta, None, None)
    nivel = detectabilidade(delta, u_ind, u_cor)
    return Comparacao(
        nome,
        unidade,
        float(a.valor),
        float(b.valor),
        delta,
        float(2 * u_ind),
        {"sim": True, "nao": False}.get(nivel),
        float(2 * u_cor),
        nivel,
    )
