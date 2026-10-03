"""Rotas físicas adaptativas baseadas em vazões do historiador.

Permitem usar plantas que não têm o balanço de pátio/totalizadores do fluxo clássico.
Integram somente intervalos observados em comum e não atravessam lacunas grandes.

A rota de fluxo de entalpia do vapor não é chamada de eficiência sem a condição da água
de entrada. Ausência continua ausência; hipóteses de estado ficam explicitadas no resultado.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from math import isfinite

import pandas as pd

from euler.tipos import AnaliseBloqueada
from euler.vapor import h_agua_mj_kg, h_vapor_mj_kg, t_sat_c


@dataclass(frozen=True)
class FluxoEntalpiaVapor:
    n: int
    n_total: int
    cobertura_leituras: float
    media_mw: float
    minimo_mw: float
    maximo_mw: float
    hipoteses: tuple[str, ...]
    nota: str


@dataclass(frozen=True)
class BalancoFluxos:
    energia_vapor_gj: float
    energia_combustivel_gj: float
    eficiencia: float
    horas_cobertas: float
    horas_totais: float
    cobertura: float
    intervalos_usados: int
    intervalos_pulados: int
    hipoteses: tuple[str, ...]
    nota: str
    motivos_exclusao: tuple[str, ...] = ()


def _estado_linha(row, assumir_saturado_seco: bool = False) -> tuple[str, dict, str]:
    estado = None
    if hasattr(row, "estado_vapor") and not pd.isna(row.estado_vapor):
        estado = str(row.estado_vapor)
    if estado == "superaquecido":
        if not hasattr(row, "t_vapor_c") or pd.isna(row.t_vapor_c):
            raise AnaliseBloqueada("Vapor superaquecido sem temperatura.")
        return estado, {"t_vapor_c": float(row.t_vapor_c)}, "registrado"
    if estado == "umido":
        if not hasattr(row, "titulo_vapor_frac") or pd.isna(row.titulo_vapor_frac):
            raise AnaliseBloqueada("Vapor úmido sem título.")
        return estado, {"titulo": float(row.titulo_vapor_frac)}, "registrado"
    if estado == "saturado_seco":
        return estado, {}, "registrado"

    if estado not in (None, ""):
        raise AnaliseBloqueada("Estado do vapor desconhecido; confira o registro.")
    # Sem rótulo, P + T identifica superaquecimento quando está claramente acima da saturação.
    if hasattr(row, "t_vapor_c") and not pd.isna(row.t_vapor_c):
        tsat = t_sat_c(float(row.p_vapor_bar_abs))
        if float(row.t_vapor_c) > tsat + 1.0:
            return "superaquecido", {"t_vapor_c": float(row.t_vapor_c)}, "inferido_de_P_e_T"
        raise AnaliseBloqueada(
            "Temperatura do vapor próxima/abaixo da saturação sem estado/título declarado.",
            ["estado do vapor ou título quando aplicável"],
        )

    if assumir_saturado_seco:
        return "saturado_seco", {}, "assumido_x_1"
    raise AnaliseBloqueada("Estado do vapor ausente: informe P/T ou estado e título aplicável.")


def fluxo_entalpia_vapor(
    diario: pd.DataFrame, *, assumir_saturado_seco: bool = False
) -> FluxoEntalpiaVapor:
    """Fluxo de entalpia no ponto do vapor, sem fingir que isso é o duty da caldeira."""
    obrig = {"vazao_vapor_t_h", "p_vapor_bar_abs"}
    faltam = obrig - set(diario.columns)
    if faltam:
        raise AnaliseBloqueada("Faltam dados para o fluxo de entalpia do vapor.", sorted(faltam))

    _uma_caldeira(diario)
    valores = []
    origens = set()
    for row in diario.itertuples(index=False):
        try:
            if pd.isna(row.vazao_vapor_t_h) or float(row.vazao_vapor_t_h) <= 0:
                continue
            if pd.isna(row.p_vapor_bar_abs):
                continue
            estado, kwargs, origem = _estado_linha(row, assumir_saturado_seco)
            h = h_vapor_mj_kg(float(row.p_vapor_bar_abs), estado, **kwargs)
            valor = float(row.vazao_vapor_t_h) * 1000 / 3600 * h
            if not isfinite(valor) or valor <= 0:
                continue
            valores.append(valor)
            origens.add(origem)
        except (AnaliseBloqueada, ValueError, TypeError):
            continue
    if not valores:
        raise AnaliseBloqueada("Nenhuma leitura válida para o fluxo de entalpia do vapor.")
    serie = pd.Series(valores, dtype=float)
    hipoteses = []
    if "inferido_de_P_e_T" in origens:
        hipoteses.append("estado superaquecido inferido porque T > Tsat + 1 °C")
    if "assumido_x_1" in origens:
        hipoteses.append("sem estado/T do vapor em parte das leituras: x = 1 assumido")
    return FluxoEntalpiaVapor(
        n=len(serie),
        n_total=len(diario),
        cobertura_leituras=len(serie) / len(diario),
        media_mw=float(serie.mean()),
        minimo_mw=float(serie.min()),
        maximo_mw=float(serie.max()),
        hipoteses=tuple(hipoteses),
        nota=(
            "Média aritmética das leituras válidas do fluxo de entalpia pela IF97; não é média "
            "ponderada pelo tempo. Sem a condição da água de entrada, "
            "não representa energia útil nem eficiência da caldeira."
        ),
    )


def _uma_caldeira(diario: pd.DataFrame) -> None:
    if "caldeira_id" in diario and diario["caldeira_id"].nunique(dropna=False) != 1:
        raise AnaliseBloqueada("Selecione os registros de uma única caldeira por análise.")


def _potencia_vapor_mw(row, assumir_saturado_seco: bool) -> tuple[float, str, str]:
    estado, kwargs, origem = _estado_linha(row, assumir_saturado_seco)
    dh = h_vapor_mj_kg(float(row.p_vapor_bar_abs), estado, **kwargs) - h_agua_mj_kg(
        float(row.p_agua_referencia_bar_abs), float(row.t_agua_alim_c)
    )
    q = float(row.vazao_vapor_t_h) * 1000 / 3600 * dh
    if not isfinite(q) or q <= 0:
        raise AnaliseBloqueada("Potência do vapor precisa ser positiva e finita.")
    return q, origem, estado


def _potencia_combustivel_mw(row) -> float:
    if hasattr(row, "potencia_combustivel_mw") and not pd.isna(row.potencia_combustivel_mw):
        q = float(row.potencia_combustivel_mw)
    else:
        if (
            not hasattr(row, "vazao_combustivel_kg_h")
            or not hasattr(row, "pci_combustivel_mj_kg")
            or pd.isna(row.vazao_combustivel_kg_h)
            or pd.isna(row.pci_combustivel_mj_kg)
        ):
            raise AnaliseBloqueada(
                "Sem potência térmica do combustível nem vazão mássica + PCI no mesmo instante."
            )
        q = float(row.vazao_combustivel_kg_h) * float(row.pci_combustivel_mj_kg) / 3600
    if not isfinite(q) or q <= 0:
        raise AnaliseBloqueada("Potência térmica do combustível precisa ser positiva e finita.")
    return q


def balanco_por_vazoes(
    diario: pd.DataFrame,
    *,
    max_gap_factor: float = 3.0,
    cobertura_minima: float = 0.5,
    assumir_saturado_seco: bool = False,
) -> BalancoFluxos:
    """Integra potência útil do vapor e potência do combustível pelo trapézio.

    Não interpola tags ausentes. Lacunas maiores que max_gap_factor × quartil inferior dos
    passos são puladas. Usa intervalos comuns, explicitamente estáveis e sem troca de estado.
    A pressão da água pertence ao mesmo ponto de sua temperatura; não é herdada do vapor.
    """
    obrig = {
        "instante_observado",
        "vazao_vapor_t_h",
        "p_vapor_bar_abs",
        "t_agua_alim_c",
        "p_agua_referencia_bar_abs",
        "regime",
    }
    faltam = obrig - set(diario.columns)
    if faltam:
        raise AnaliseBloqueada("Faltam colunas para o balanço por vazões.", sorted(faltam))

    if not isfinite(max_gap_factor) or max_gap_factor <= 0:
        raise ValueError("Fator de lacuna precisa ser positivo e finito.")
    if not isfinite(cobertura_minima) or not 0 < cobertura_minima <= 1:
        raise ValueError("Cobertura mínima precisa estar entre zero (exclusivo) e um.")
    _uma_caldeira(diario)
    d = diario.copy()
    d["instante_observado"] = pd.to_datetime(d["instante_observado"], errors="coerce", utc=True)
    if d["instante_observado"].isna().any():
        raise AnaliseBloqueada("Instantes inválidos: confira os registros antes de integrar.")
    if d["instante_observado"].duplicated().any():
        raise AnaliseBloqueada("Instantes duplicados: resolva a duplicidade antes de integrar.")
    d = d.sort_values("instante_observado")
    if len(d) < 2:
        raise AnaliseBloqueada("São necessárias ao menos duas leituras no tempo.")

    tempos = pd.to_datetime(d["instante_observado"])
    passos_h = tempos.diff().dt.total_seconds().div(3600).dropna()
    positivos = passos_h[passos_h > 0]
    if positivos.empty:
        raise AnaliseBloqueada("Os instantes não formam intervalos positivos.")
    # Quartil inferior com interpolação "lower": conservador contra uma lacuna grande que
    # contaminaria a mediana em séries curtas. Não "preenche" buracos do historiador.
    passo_tipico = float(positivos.quantile(0.25, interpolation="lower"))
    limite_gap = max_gap_factor * passo_tipico

    qv = []
    qf = []
    validos = []
    origens = set()
    estados = []
    motivos: dict[str, int] = {}
    for row in d.itertuples(index=False):
        try:
            if pd.isna(row.regime) or row.regime != "estavel":
                raise AnaliseBloqueada("Balanço estacionário exige regime explicitamente estável.")
            if pd.isna(row.vazao_vapor_t_h) or float(row.vazao_vapor_t_h) <= 0:
                raise AnaliseBloqueada("Vazão de vapor ausente ou não positiva.")
            if pd.isna(row.p_vapor_bar_abs) or pd.isna(row.t_agua_alim_c):
                raise AnaliseBloqueada("Condição do vapor/água ausente.")
            vapor_mw, origem, estado = _potencia_vapor_mw(row, assumir_saturado_seco)
            combustivel_mw = _potencia_combustivel_mw(row)
            qv.append(vapor_mw)
            qf.append(combustivel_mw)
            validos.append(True)
            estados.append(estado)
            origens.add(origem)
        except (AnaliseBloqueada, ValueError, TypeError) as erro:
            qv.append(float("nan"))
            qf.append(float("nan"))
            validos.append(False)
            estados.append(None)
            motivo = (
                erro.motivo
                if isinstance(erro, AnaliseBloqueada)
                else "Medição inválida ou ausente."
            )
            motivos[motivo] = motivos.get(motivo, 0) + 1

    d["qv_mw"] = qv
    d["qf_mw"] = qf
    d["valido_balanco"] = validos
    d["estado_calculado"] = estados

    ev = ef = 0.0
    horas = 0.0
    usados = pulados = 0
    rows = list(d.itertuples(index=False))
    for a, b in pairwise(rows):
        dt_h = (b.instante_observado - a.instante_observado).total_seconds() / 3600
        if (
            dt_h <= 0
            or dt_h > limite_gap
            or not (a.valido_balanco and b.valido_balanco)
            or a.estado_calculado != b.estado_calculado
        ):
            pulados += 1
            continue
        # MW × h × 3,6 = GJ
        ev += 0.5 * (a.qv_mw + b.qv_mw) * dt_h * 3.6
        ef += 0.5 * (a.qf_mw + b.qf_mw) * dt_h * 3.6
        horas += dt_h
        usados += 1

    total_h = (tempos.iloc[-1] - tempos.iloc[0]).total_seconds() / 3600
    cobertura = 0.0 if total_h <= 0 else horas / total_h
    if usados == 0 or ev <= 0 or ef <= 0:
        raise AnaliseBloqueada("Nenhum intervalo comum válido para fechar o balanço por vazões.")
    if cobertura < cobertura_minima:
        raise AnaliseBloqueada(
            f"Cobertura comum insuficiente para o balanço por vazões ({100 * cobertura:.0f}%).",
            [f"cobertura de ao menos {100 * cobertura_minima:.0f}% nos mesmos intervalos"],
        )

    eta = ev / ef
    if not isfinite(eta) or eta <= 0:
        raise AnaliseBloqueada("Eficiência por vazões não finita ou não positiva.")

    hipoteses = []
    if "inferido_de_P_e_T" in origens:
        hipoteses.append("estado superaquecido inferido porque T > Tsat + 1 °C")
    if "assumido_x_1" in origens:
        hipoteses.append("sem estado/T do vapor em parte das leituras: x = 1 assumido")
    if eta > 1:
        hipoteses.append("razão acima de 100%: verificar base calorífica, fronteira e medições")
    return BalancoFluxos(
        energia_vapor_gj=ev,
        energia_combustivel_gj=ef,
        eficiencia=eta,
        horas_cobertas=horas,
        horas_totais=total_h,
        cobertura=cobertura,
        intervalos_usados=usados,
        intervalos_pulados=pulados,
        hipoteses=tuple(hipoteses),
        nota=(
            "Estimativa nos intervalos comuns explicitamente estáveis, com interpolação linear "
            "entre extremos válidos. Não atravessa paradas, transientes ou lacunas grandes e "
            "não representa os trechos excluídos. A origem/base da potência de combustível "
            "fornecida deve ser confirmada. Sem orçamento de incerteza instrumental completo."
        ),
        motivos_exclusao=tuple(f"{n} leitura(s): {m}" for m, n in motivos.items()),
    )
