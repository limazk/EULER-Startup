"""Importador do diário do operador, `diario.csv` (T03)."""

import pandas as pd

from euler import qualidade
from euler.io.leitura import FUSO_PADRAO, Aviso, Fonte, Importacao, importar_tabela


def importar_diario(
    fonte: Fonte,
    p_atm_bar: float | None = None,
    fuso: str = FUSO_PADRAO,
    intervalo_esperado_h: float | None = None,
    atraso_maximo_min: float = qualidade.ATRASO_REGISTRO_MIN,
) -> Importacao:
    """Lê, normaliza e verifica o diário.

    Converte as pressões manométricas do vapor, da purga, da água de referência e do economizador para absolutas
    (`p_vapor_bar_abs`, `p_purga_bar_abs`, `p_agua_referencia_bar_abs` e `p_agua_eco_bar_abs`, regra 3)
    quando a pressão atmosférica do local é conhecida; sem ela, a coluna fica vazia
    e um aviso explica por quê.
    """
    imp = importar_tabela("diario", fonte, fuso)
    if imp.bloqueada:
        return imp
    dados = imp.dados
    alias = dados["titulo_vapor"]
    canonico = dados["titulo_vapor_frac"]
    conflito = alias.notna() & canonico.notna() & (alias != canonico)
    if conflito.any():
        imp.avisos.append(
            Aviso(
                "diario",
                None,
                "titulo_vapor",
                "alias_titulo_conflitante",
                "Título do vapor informado com valores diferentes em duas colunas "
                "equivalentes. Corrija a divergência antes de usar o diário.",
                "erro",
            )
        )
        return imp
    usar_alias = alias.notna() & canonico.isna()
    if usar_alias.any():
        dados.loc[usar_alias, "titulo_vapor_frac"] = alias[usar_alias]
        imp.avisos.append(
            Aviso(
                "diario",
                None,
                "titulo_vapor",
                "alias_titulo_vapor",
                "A coluna alternativa de título do vapor foi reconhecida (mesma fração, "
                "sem mudança de valor). O arquivo original foi preservado.",
                "info",
            )
        )
    if p_atm_bar is not None:
        dados["p_vapor_bar_abs"] = dados["p_vapor_bar_man"] + p_atm_bar
        dados["p_purga_bar_abs"] = dados["p_purga_bar_man"] + p_atm_bar
        dados["p_agua_referencia_bar_abs"] = dados["p_agua_referencia_bar_man"] + p_atm_bar
        dados["p_agua_eco_bar_abs"] = dados["p_agua_eco_bar_man"] + p_atm_bar
    else:
        dados["p_vapor_bar_abs"] = pd.Series([pd.NA] * len(dados), dtype="Float64")
        dados["p_purga_bar_abs"] = pd.Series([pd.NA] * len(dados), dtype="Float64")
        dados["p_agua_referencia_bar_abs"] = pd.Series([pd.NA] * len(dados), dtype="Float64")
        dados["p_agua_eco_bar_abs"] = pd.Series([pd.NA] * len(dados), dtype="Float64")
        if dados["p_vapor_bar_man"].notna().any():
            imp.avisos.append(
                Aviso(
                    "diario",
                    None,
                    "p_vapor_bar_man",
                    "sem_pressao_atmosferica",
                    "Pressão absoluta não calculada: falta a pressão atmosférica do local "
                    "(informe a altitude ou a leitura de um barômetro).",
                    "info",
                )
            )
    imp.avisos += qualidade.verificar_diario(dados, intervalo_esperado_h, atraso_maximo_min)
    return imp
