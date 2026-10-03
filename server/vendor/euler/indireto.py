"""Perda sensível nos gases de chaminé, base PCI, por kg de combustível seco (E1–E7).

Referência das equações: docs/fisica/fisica_para_revisao.md, Bloco A.
Convenções: composição em fração mássica base seca (C, H, O, N, S); umidade `w`
em base úmida (fração); temperaturas em °C; PCI em MJ/kg; cp em MJ/(kg·K).
Hipóteses: combustão completa; ar seco com 21% O₂ / 79% N₂; umidade do ar de
combustão desprezada por padrão (pergunta aberta no E4; opcional na Fase R).

Modos de cp (E6):
- "constante" — referência dos testes golden (1,05 e 1,90 kJ/kg·K); não muda.
- "variavel" — **experimental** (Fase R, D40): entalpia sensível de cada espécie pelos
  polinômios NASA (TM-4513, ver euler.propriedades_gases). Dá 0,30–0,41 p.p. a menos que
  o modo constante nos casos G01–G12. Pendente de aprovação do revisor como fonte de cp(T).

Este módulo não compartilha código com o benchmark `euler-bench` (AGENTS.md, regra 7).
"""

from collections.abc import Mapping
from dataclasses import dataclass

from iapws import IAPWS97

from euler.combustivel import H_VAP_25C_MJ_KG, pci_umido
from euler.propriedades_gases import (
    NASA7,
    TOLERANCIA_EXTRAPOLACAO_K,
    entalpia_combustao_co_kj_kmol,
    entalpia_sensivel_kj_kmol,
)
from euler.tipos import AnaliseBloqueada
from euler.vapor import P_ATM_NIVEL_DO_MAR_BAR, t_sat_c

CP_GASES_SECOS_MJ_KG_K = 1.05e-3
"""cp constante dos gases secos, modo referência (E6, só para teste)."""
CP_VAPOR_AGUA_MJ_KG_K = 1.90e-3
"""cp constante do vapor d'água, modo referência (E6, só para teste)."""
RAZAO_N2_O2_AR = 79 / 21
MASSA_MOLAR_H2O = 18.015  # kg/kmol
CO_LIMITE_AVISO_PPM = 200
"""Acima disso, ignorar CO no cálculo de λ pode errar (pergunta aberta no E2)."""
MODELOS_CP = ("constante", "variavel")
ELEMENTOS = ("C", "H", "O", "N", "S")

COMPOSICAO_REFERENCIA = {"C": 0.50, "H": 0.06, "O": 0.43, "N": 0.003, "S": 0.0005}
"""Cavaco de referência do documento de revisão (base seca). Origem: assumido."""


@dataclass(frozen=True)
class ResultadoPerdaGases:
    """Resultado da perda nos gases e grandezas intermediárias.

    perda_pct: perda sensível nos gases, % do PCI (E6).
    lambda_ar: razão de ar (E2).
    o2_esteq_kmol_kg: O₂ estequiométrico, kmol/kg seco (E1).
    m_gases_secos_kg_kg: massa de gases secos, kg/kg seco (E3).
    m_h2o_kg_kg: água nos gases, kg/kg seco (E4).
    t_orvalho_c: orvalho da água nos gases, °C (E7).
    avisos: alertas que não impedem o cálculo.
    """

    perda_pct: float
    lambda_ar: float
    o2_esteq_kmol_kg: float
    m_gases_secos_kg_kg: float
    m_h2o_kg_kg: float
    t_orvalho_c: float
    modelo_cp: str
    avisos: tuple[str, ...] = ()
    n_gases_secos_kmol_kg: float | None = None
    """Gases secos, kmol por kg de combustível seco (usado na perda por CO)."""


def _checar_composicao(comp: Mapping[str, float]) -> tuple[float, ...]:
    faltando = [e for e in ELEMENTOS if comp.get(e) is None]
    if faltando:
        raise AnaliseBloqueada(
            f"Composição do combustível incompleta: falta {', '.join(faltando)}.",
            falta=["análise elementar do combustível (C, H, O, N, S em base seca)"],
        )
    valores = tuple(float(comp[e]) for e in ELEMENTOS)
    if any(v < 0 or v > 1 for v in valores) or sum(valores) > 1.0001:
        raise AnaliseBloqueada(
            "Composição do combustível inválida: frações devem ficar entre 0 e 1 "
            "e somar no máximo 1 (o resto são cinzas)."
        )
    return valores


def oxigenio_estequiometrico(comp: Mapping[str, float]) -> float:
    """O₂ estequiométrico, kmol de O₂ por kg de combustível seco (E1).

    a = C/12 + H/4 + S/32 − O/32
    """
    c, h, o, _n, s = _checar_composicao(comp)
    a = c / 12 + h / 4 + s / 32 - o / 32
    if a <= 0:
        raise AnaliseBloqueada("Composição sem demanda de oxigênio: confira a análise elementar.")
    return a


def razao_ar(o2_seco_pct: float, comp: Mapping[str, float]) -> float:
    """Razão de ar λ a partir do O₂ medido nos gases secos (E2).

    Gases secos por kg seco: n_CO2 = C/12, n_SO2 = S/32, n_O2 = (λ−1)a,
    n_N2 = (79/21)λa + N/28. Resolvendo y_O2 = n_O2/Σn para X = λa:
    X·(1 − y − y·79/21) = a + y·(C/12 + S/32 + N/28) − y·a
    """
    if not 0 <= o2_seco_pct < 21:
        raise AnaliseBloqueada(
            f"O₂ de {o2_seco_pct:g}% fora da faixa de combustão (0 a 21%). "
            "Leitura de 21% indica ar ambiente ou analisador fora do ponto."
        )
    c, _h, _o, n, s = _checar_composicao(comp)
    a = oxigenio_estequiometrico(comp)
    y = o2_seco_pct / 100
    x = (a + y * (c / 12 + s / 32 + n / 28) - y * a) / (1 - y - y * RAZAO_N2_O2_AR)
    return x / a


def _t_orvalho_agua_c(n_h2o: float, n_secos: float, p_gases_bar_abs: float) -> float:
    """Orvalho da água nos gases (°C): T_sat na pressão parcial do vapor (E7).

    Não inclui orvalho ácido (SO₃) nem a umidade do ar de combustão.
    """
    p_h2o_bar = n_h2o / (n_h2o + n_secos) * p_gases_bar_abs
    return IAPWS97(P=p_h2o_bar / 10, x=0).T - 273.15


def perda_gases(
    t_gases_c: float,
    o2_seco_pct: float,
    umidade_bu_frac: float,
    t_ar_c: float,
    composicao_seca: Mapping[str, float],
    pci_seco_mj_kg: float,
    modelo_cp: str = "constante",
    p_gases_bar_abs: float = P_ATM_NIVEL_DO_MAR_BAR,
    co_ppm: float | None = None,
    umidade_ar_kg_kg: float | None = None,
) -> ResultadoPerdaGases:
    """Perda sensível nos gases de chaminé, % do PCI (E1–E7).

    q_g = [m_gs·cp_gs + m_H2O·cp_H2O] · (T_g − T_ar) / (PCI_seco − 2,442·w/(1−w))

    com m_gs = 44·n_CO2 + 64·n_SO2 + 32·n_O2 + 28·n_N2 (E3) e
    m_H2O = 9H + w/(1−w) (E4), tudo por kg de combustível seco.

    Entradas:
        t_gases_c, t_ar_c: temperaturas dos gases na chaminé e do ar de combustão, °C.
        o2_seco_pct: O₂ medido nos gases secos, %.
        umidade_bu_frac: umidade do combustível, base úmida, fração.
        composicao_seca: frações C, H, O, N, S em base seca.
        pci_seco_mj_kg: PCI em base seca, MJ/kg.
        modelo_cp: "constante" (referência, reproduz o golden) ou "variavel"
            (bloqueado até o revisor definir a fonte de cp(T), E6).
        p_gases_bar_abs: pressão dos gases para o orvalho (padrão: nível do mar).
        co_ppm: CO medido; acima de 200 ppm gera aviso (E2). A perda por CO é calculada à
            parte (`perda_co_pct`), não entra aqui.
        umidade_ar_kg_kg: umidade absoluta do ar de combustão (kg de água por kg de ar
            seco). None (padrão) = desprezada, como no golden. Experimental (D41).

    Bloqueia (E7) se os gases estiverem abaixo do orvalho da água ou não estiverem
    mais quentes que o ar de combustão.
    """
    if modelo_cp not in MODELOS_CP:
        raise ValueError(f"modelo_cp desconhecido: {modelo_cp!r} (use {MODELOS_CP})")
    c, h, _o, n, s = _checar_composicao(composicao_seca)
    pci_umido(pci_seco_mj_kg, umidade_bu_frac)  # valida umidade e PCI
    if t_gases_c <= t_ar_c:
        raise AnaliseBloqueada(
            f"Gases a {t_gases_c:g} °C não estão mais quentes que o ar de combustão "
            f"({t_ar_c:g} °C): a perda sensível não se aplica. Confira as leituras."
        )

    a = oxigenio_estequiometrico(composicao_seca)
    lam = razao_ar(o2_seco_pct, composicao_seca)
    n_co2, n_so2 = c / 12, s / 32
    n_o2 = (lam - 1) * a
    n_n2 = RAZAO_N2_O2_AR * lam * a + n / 28
    m_gs = 44 * n_co2 + 64 * n_so2 + 32 * n_o2 + 28 * n_n2
    agua_por_seco = umidade_bu_frac / (1 - umidade_bu_frac)
    m_h2o = 9 * h + agua_por_seco
    if umidade_ar_kg_kg is not None:
        if not 0 <= umidade_ar_kg_kg < 0.1:
            raise AnaliseBloqueada(
                f"Umidade do ar de {umidade_ar_kg_kg:g} kg/kg fora da faixa (0 a 0,1)."
            )
        ar_seco_kg = lam * a / 0.21 * (0.21 * 32 + 0.79 * 28)  # mesmas massas molares de E3
        m_h2o += umidade_ar_kg_kg * ar_seco_kg

    t_orvalho = _t_orvalho_agua_c(
        m_h2o / MASSA_MOLAR_H2O, n_co2 + n_so2 + n_o2 + n_n2, p_gases_bar_abs
    )
    if t_gases_c < t_orvalho:
        raise AnaliseBloqueada(
            f"Gases a {t_gases_c:g} °C estão abaixo do orvalho estimado ({t_orvalho:.0f} °C): "
            "há condensação e a fórmula de perda sensível não vale (E7)."
        )

    avisos = []
    if modelo_cp == "constante":
        calor = (m_gs * CP_GASES_SECOS_MJ_KG_K + m_h2o * CP_VAPOR_AGUA_MJ_KG_K) * (
            t_gases_c - t_ar_c
        )
    else:
        moles = {
            "CO2": n_co2,
            "SO2": n_so2,
            "O2": n_o2,
            "N2": n_n2,
            "H2O": m_h2o / MASSA_MOLAR_H2O,
        }
        calor = (
            sum(
                n_i * entalpia_sensivel_kj_kmol(esp, t_ar_c, t_gases_c)
                for esp, n_i in moles.items()
            )
            / 1000
        )
        avisos.append(
            "cp(T) experimental (polinômios NASA TM-4513): ainda não aprovado pelo revisor (D40)."
        )
        extrapoladas = [
            esp for esp, n_i in moles.items() if n_i > 0 and t_ar_c + 273.15 < NASA7[esp][0][0]
        ]
        if extrapoladas:
            avisos.append(
                f"Polinômio NASA extrapolado abaixo da faixa para {', '.join(extrapoladas)} "
                f"(ar a {t_ar_c:g} °C; até {TOLERANCIA_EXTRAPOLACAO_K:g} K abaixo do limite)."
            )
    pci_por_kg_seco = pci_seco_mj_kg - H_VAP_25C_MJ_KG * agua_por_seco

    if co_ppm is not None and co_ppm > CO_LIMITE_AVISO_PPM:
        avisos.append(
            f"CO de {co_ppm:g} ppm: acima de {CO_LIMITE_AVISO_PPM} ppm, o λ calculado sem "
            "considerar CO pode ter erro (E2, em revisão)."
        )

    return ResultadoPerdaGases(
        perda_pct=100 * calor / pci_por_kg_seco,
        lambda_ar=lam,
        o2_esteq_kmol_kg=a,
        m_gases_secos_kg_kg=m_gs,
        m_h2o_kg_kg=m_h2o,
        t_orvalho_c=t_orvalho,
        modelo_cp=modelo_cp,
        avisos=tuple(avisos),
        n_gases_secos_kmol_kg=n_co2 + n_so2 + n_o2 + n_n2,
    )


def alerta_temperatura_implausivel(
    t_gases_c: float,
    p_vapor_bar_abs: float,
    aproximacao_minima_c: float | None,
    tem_recuperador: bool = False,
) -> str | None:
    """Alerta de plausibilidade da temperatura dos gases (E7).

    Sem economizador ou pré-aquecedor, os gases devem sair acima de
    T_sat(p) + aproximação mínima. O valor da aproximação ainda não foi definido
    pelo revisor: sem ele (None), nenhum alerta é emitido (nunca inventar número).
    Retorna a mensagem do alerta ou None.
    """
    if aproximacao_minima_c is None or tem_recuperador:
        return None
    limite = t_sat_c(p_vapor_bar_abs) + aproximacao_minima_c
    if t_gases_c < limite:
        return (
            f"Gases a {t_gases_c:g} °C abaixo de saturação + aproximação mínima "
            f"({limite:.0f} °C) sem recuperador de calor: confira o ponto de medição "
            "e o instrumento."
        )
    return None


def perda_co_pct(
    co_ppm: float, resultado: ResultadoPerdaGases, pci_seco_mj_kg: float, umidade_bu_frac: float
) -> float:
    """Perda por CO não queimado, % do PCI (Fase R, experimental, D42).

    q_CO = y_CO · n_gases_secos · ΔH_c(CO) / (PCI_seco − 2,442·w/(1−w))
    com y_CO em base seca (ppm × 10⁻⁶) e ΔH_c(CO) = 282,98 MJ/kmol (polinômios NASA; confere
    com os valores CODATA de formação publicados no NIST WebBook). Não corrige o λ (o CO
    consome menos O₂ que o CO₂).
    """
    if co_ppm < 0:
        raise AnaliseBloqueada(f"CO de {co_ppm:g} ppm não pode ser negativo.")
    if resultado.n_gases_secos_kmol_kg is None:
        raise ValueError("resultado sem quantidade de gases secos")
    pci_por_kg_seco = pci_seco_mj_kg - H_VAP_25C_MJ_KG * umidade_bu_frac / (1 - umidade_bu_frac)
    calor = co_ppm * 1e-6 * resultado.n_gases_secos_kmol_kg * entalpia_combustao_co_kj_kmol() / 1000
    return 100 * calor / pci_por_kg_seco


def umidade_absoluta_ar(
    t_ar_c: float, umidade_relativa: float, p_bar_abs: float = P_ATM_NIVEL_DO_MAR_BAR
) -> float:
    """Umidade absoluta do ar (kg de água / kg de ar seco), Fase R, experimental (D41).

    W = 0,622 · φ·p_sat / (p − φ·p_sat), com p_sat(T) da IAPWS-IF97. 0,622 é a razão das
    massas molares água/ar (18,015/28,96).
    """
    if not 0 <= umidade_relativa <= 1:
        raise AnaliseBloqueada(f"Umidade relativa {umidade_relativa:g} fora de 0 a 1 (fração).")
    p_sat = IAPWS97(T=t_ar_c + 273.15, x=0).P * 10
    return 0.622 * umidade_relativa * p_sat / (p_bar_abs - umidade_relativa * p_sat)


LAMBDA_MAXIMO_CONVERSAO = 50.0
"""Limite da busca de λ na conversão úmido → seco. λ = 50 já corresponde a O₂ seco de
~20,6% com a composição de referência; acima disso a leitura não descreve combustão."""


def o2_seco_equivalente(
    o2_umido_pct: float, composicao_seca: Mapping[str, float], umidade_bu_frac: float
) -> float:
    """O₂ em base seca correspondente a uma leitura em base **úmida** (Fase R, D43).

    Analisadores in situ (zircônia na chaminé) medem O₂ nos gases úmidos. Resolve λ tal
    que n_O2 / (gases secos + água) = O₂ úmido, e devolve n_O2 / gases secos.
    Água: só a do combustível (E4, sem umidade do ar).
    """
    if not 0 <= o2_umido_pct < 21:
        raise AnaliseBloqueada(f"O₂ úmido de {o2_umido_pct:g}% fora da faixa (0 a 21%).")
    c, h, _o, n, s = _checar_composicao(composicao_seca)
    a = oxigenio_estequiometrico(composicao_seca)
    n_h2o = (9 * h + umidade_bu_frac / (1 - umidade_bu_frac)) / MASSA_MOLAR_H2O
    alvo = o2_umido_pct / 100

    def secos(lam: float) -> tuple[float, float]:
        n_o2 = (lam - 1) * a
        return n_o2, c / 12 + s / 32 + n_o2 + RAZAO_N2_O2_AR * lam * a + n / 28

    lo, hi = 1.0, LAMBDA_MAXIMO_CONVERSAO
    n_o2_hi, n_s_hi = secos(hi)
    if alvo >= n_o2_hi / (n_s_hi + n_h2o):
        # a solução está fora do intervalo de busca: recusar, nunca devolver a borda (A5)
        raise AnaliseBloqueada(
            f"O₂ úmido de {o2_umido_pct:g}% exigiria excesso de ar acima de λ = "
            f"{LAMBDA_MAXIMO_CONVERSAO:g} (O₂ úmido máximo nesse limite: "
            f"{100 * n_o2_hi / (n_s_hi + n_h2o):.2f}%). Leitura perto de 21% indica ar sem "
            "combustão (queimador apagado, entrada falsa de ar ou sonda fora dos gases)."
        )
    for _ in range(200):  # bissecção: y_O2 úmido cresce com λ
        meio = (lo + hi) / 2
        n_o2, n_s = secos(meio)
        if n_o2 / (n_s + n_h2o) < alvo:
            lo = meio
        else:
            hi = meio
    n_o2, n_s = secos((lo + hi) / 2)
    return 100 * n_o2 / n_s
