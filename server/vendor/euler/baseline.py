"""Baseline simples condicionado à carga para o primeiro piloto da EULER.

Modelo deliberadamente simples e auditável:
    m_combustível/h = a + b · m_vapor/h

Não é lei universal nem diagnóstico causal. O modelo não extrapola fora da faixa de carga
observada na referência e o residual só é normalizado quando a dispersão residual é estimável.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt

import numpy as np

from euler.tipos import AnaliseBloqueada


@dataclass(frozen=True)
class ObservacaoCarga:
    carga_t_h: float
    combustivel_t_h: float


@dataclass(frozen=True)
class BaselineCarga:
    intercepto_t_h: float
    inclinacao_t_t: float
    carga_min_t_h: float
    carga_max_t_h: float
    carga_media_t_h: float
    sxx: float
    rmse_t_h: float
    n: int

    def prever_combustivel_t_h(self, carga_t_h: float) -> float:
        if not self.carga_min_t_h <= carga_t_h <= self.carga_max_t_h:
            raise AnaliseBloqueada(
                f"Carga de {carga_t_h:g} t/h fora da faixa usada no baseline "
                f"({self.carga_min_t_h:g} a {self.carga_max_t_h:g} t/h).",
                ["dados de referência em carga semelhante"],
            )
        previsto = self.intercepto_t_h + self.inclinacao_t_t * carga_t_h
        if previsto <= 0 or not isfinite(previsto):
            raise AnaliseBloqueada(
                "O baseline produziu vazão de combustível não física nesta carga.",
                ["revisar a faixa e a qualidade dos períodos de referência"],
            )
        return previsto

    def sigma_predicao_t_h(self, carga_t_h: float) -> float | None:
        self.prever_combustivel_t_h(carga_t_h)
        if self.n < 3 or self.rmse_t_h <= 0 or self.sxx <= 0:
            return None
        h = 1 / self.n + (carga_t_h - self.carga_media_t_h) ** 2 / self.sxx
        return self.rmse_t_h * sqrt(1 + h)


def ajustar_baseline_carga(observacoes: list[ObservacaoCarga]) -> BaselineCarga:
    if len(observacoes) < 3:
        raise AnaliseBloqueada(
            "São necessários ao menos três períodos de referência para ajustar o baseline "
            "por carga.",
            ["três ou mais períodos de referência quase estacionários"],
        )
    x = np.array([o.carga_t_h for o in observacoes], dtype=float)
    y = np.array([o.combustivel_t_h for o in observacoes], dtype=float)
    if not np.isfinite(x).all() or not np.isfinite(y).all() or (x <= 0).any() or (y <= 0).any():
        raise AnaliseBloqueada(
            "O baseline recebeu carga ou combustível inválido.",
            ["vazões positivas e finitas de vapor e combustível"],
        )
    xbar = float(x.mean())
    sxx = float(((x - xbar) ** 2).sum())
    if sxx <= 0:
        raise AnaliseBloqueada(
            "A referência não contém variação de carga suficiente para ajustar o baseline.",
            ["períodos de referência em pelo menos duas cargas diferentes"],
        )
    b = float(((x - xbar) * (y - y.mean())).sum() / sxx)
    a = float(y.mean() - b * xbar)
    residuos = y - (a + b * x)
    norma_residuo = float(np.linalg.norm(residuos))
    tolerancia_numerica = np.finfo(float).eps * max(1.0, float(np.linalg.norm(y))) * len(x)
    rmse = (
        0.0
        if norma_residuo <= tolerancia_numerica
        else float(sqrt(float((residuos**2).sum()) / (len(x) - 2)))
    )
    return BaselineCarga(a, b, float(x.min()), float(x.max()), xbar, sxx, rmse, len(x))


def residual_normalizado(
    modelo: BaselineCarga, *, carga_t_h: float, combustivel_t_h: float
) -> float | None:
    if not isfinite(combustivel_t_h) or combustivel_t_h <= 0:
        raise AnaliseBloqueada(
            "Vazão de combustível inválida para calcular o residual.",
            ["vazão positiva e finita de combustível"],
        )
    esperado = modelo.prever_combustivel_t_h(carga_t_h)
    sigma = modelo.sigma_predicao_t_h(carga_t_h)
    return None if sigma is None or sigma == 0 else (combustivel_t_h - esperado) / sigma
