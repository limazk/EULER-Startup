"""Entalpia de gases ideais por polinômios NASA de 7 coeficientes (Fase R, experimental).

Fonte dos coeficientes: B. J. McBride, S. Gordon, M. A. Reno, "Coefficients for
Calculating Thermodynamic and Transport Properties of Individual Species", NASA
Technical Memorandum 4513, outubro de 1993 (https://ntrs.nasa.gov/citations/19940013151),
na transcrição `nasa_gas.yaml` distribuída com o Cantera 3.2.0 (data/nasa_gas.yaml).
Os valores abaixo foram copiados desse arquivo; o teste
`tests/test_validacao_combustao.py::test_coeficientes_nasa_iguais_ao_arquivo_de_origem`
confere a cópia quando o Cantera está instalado.

Forma (gás ideal): H/(R·T) = a1 + a2·T/2 + a3·T²/3 + a4·T³/4 + a5·T⁴/5 + a6/T,
com T em K e R = 8,314462618 kJ/(kmol·K). Faixas de validade por espécie em FAIXAS.
Uso na EULER: só **diferenças** de entalpia sensível entre T_ar e T_gases (kJ/kmol).
Situação: experimental, pendente de aprovação do revisor como fonte de cp(T) (D40).
"""

from __future__ import annotations

from euler.tipos import AnaliseBloqueada

R_KJ_KMOL_K = 8.314462618

# espécie: (T_min, T_meio, T_max) K, coeficientes faixa baixa, coeficientes faixa alta
NASA7: dict[str, tuple[tuple[float, float, float], tuple[float, ...], tuple[float, ...]]] = {
    "N2": (
        (200.0, 1000.0, 6000.0),
        (3.53100528, -1.23660987e-04, -5.02999437e-07, 2.43530612e-09, -1.40881235e-12, -1046.97628, 2.96747468),
        (2.95257626, 1.39690057e-03, -4.92631691e-07, 7.86010367e-11, -4.60755321e-15, -923.948645, 5.87189252),
    ),
    "O2": (
        (200.0, 1000.0, 6000.0),
        (3.78245636, -2.99673415e-03, 9.847302e-06, -9.68129508e-09, 3.24372836e-12, -1063.94356, 3.65767573),
        (3.66096083, 6.56365523e-04, -1.41149485e-07, 2.05797658e-11, -1.29913248e-15, -1215.97725, 3.41536184),
    ),
    "CO2": (
        (200.0, 1000.0, 6000.0),
        (2.35677352, 8.98459677e-03, -7.12356269e-06, 2.45919022e-09, -1.43699548e-13, -4.83719697e04, 9.90105222),
        (4.63659493, 2.74131991e-03, -9.95828531e-07, 1.60373011e-10, -9.16103468e-15, -4.90249341e04, -1.93534855),
    ),
    "H2O": (
        (200.0, 1000.0, 6000.0),
        (4.19864056, -2.0364341e-03, 6.52040211e-06, -5.48797062e-09, 1.77197817e-12, -3.02937267e04, -0.849032208),
        (2.67703787, 2.97318329e-03, -7.7376969e-07, 9.44336689e-11, -4.26900959e-15, -2.98858938e04, 6.88255571),
    ),
    "SO2": (
        (300.0, 1000.0, 5000.0),
        (3.2665338, 5.3237902e-03, 6.8437552e-07, -5.2810047e-09, 2.5590454e-12, -3.6908148e04, 9.66465108),
        (5.2451364, 1.9704204e-03, -8.0375769e-07, 1.5149969e-10, -1.0558004e-14, -3.7558227e04, -1.07404892),
    ),
    "CO": (
        (200.0, 1000.0, 6000.0),
        (3.57953347, -6.1035368e-04, 1.01681433e-06, 9.07005884e-10, -9.04424499e-13, -1.4344086e04, 3.50840928),
        (3.04848583, 1.35172818e-03, -4.85794075e-07, 7.88536486e-11, -4.69807489e-15, -1.42661171e04, 6.0170979),
    ),
}  # fmt: skip

TOLERANCIA_EXTRAPOLACAO_K = 40.0
"""Abaixo do limite inferior da faixa (ex.: SO₂ começa em 300 K), aceita-se extrapolar até
40 K, com aviso: cobre ar de combustão a partir de −13 °C para o SO₂ (fração mássica ínfima)."""


def entalpia_kj_kmol(especie: str, t_k: float) -> float:
    """Entalpia molar (base NASA, inclui formação) em kJ/kmol a T (K)."""
    (t_min, t_meio, t_max), baixo, alto = NASA7[especie]
    if not t_min - TOLERANCIA_EXTRAPOLACAO_K <= t_k <= t_max:
        raise AnaliseBloqueada(
            f"Temperatura de {t_k - 273.15:.0f} °C fora da faixa dos polinômios NASA para {especie} "
            f"({t_min - 273.15:.0f} a {t_max - 273.15:.0f} °C)."
        )
    a = baixo if t_k <= t_meio else alto
    h_rt = (
        a[0]
        + a[1] * t_k / 2
        + a[2] * t_k**2 / 3
        + a[3] * t_k**3 / 4
        + a[4] * t_k**4 / 5
        + a[5] / t_k
    )
    return R_KJ_KMOL_K * t_k * h_rt


def entalpia_sensivel_kj_kmol(especie: str, t1_c: float, t2_c: float) -> float:
    """H(T2) − H(T1) em kJ/kmol (temperaturas em °C)."""
    return entalpia_kj_kmol(especie, t2_c + 273.15) - entalpia_kj_kmol(especie, t1_c + 273.15)


def entalpia_combustao_co_kj_kmol() -> float:
    """Calor liberado por CO + ½O₂ → CO₂ a 25 °C (kJ/kmol de CO, valor positivo)."""
    t = 298.15
    return -(
        entalpia_kj_kmol("CO2", t) - entalpia_kj_kmol("CO", t) - 0.5 * entalpia_kj_kmol("O2", t)
    )
