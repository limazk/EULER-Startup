"""Verificações de qualidade dos registros importados (T03, T05).

Nada aqui altera dados: cada função só devolve avisos com linha e motivo
(AGENTS.md, regra 2). Os limites são propostas registradas em docs/gestao/decisoes.md.
"""

from __future__ import annotations

import pandas as pd

from euler.formato import num
from euler.io.esquemas import rotulo_coluna
from euler.io.leitura import Aviso, descrever_linhas

LACUNA_FATOR = 2.0
"""Lacuna = intervalo entre leituras maior que LACUNA_FATOR × intervalo típico (D13)."""
ATRASO_REGISTRO_MIN = 60
"""Registro tardio = anotado mais de 60 min depois da observação (D14)."""
ELEMENTOS = ("C", "H", "O", "N", "S")


def _hora(ts: pd.Timestamp) -> str:
    return ts.strftime("%d/%m/%Y %H:%M")


def _valor(v) -> str:
    return _hora(v) if isinstance(v, pd.Timestamp) else str(v)


# ---------------------------------------------------------------- genéricas


def duplicatas(dados: pd.DataFrame, tabela: str, chave: tuple[str, ...]) -> list[Aviso]:
    """Linhas com a mesma chave: idênticas (lançamento repetido) ou conflitantes."""
    avisos = []
    validas = dados.dropna(subset=list(chave))
    comparar = [c for c in validas.columns if c not in ("linha", "instante_registrado")]
    for _, grupo in validas.groupby(list(chave), sort=False):
        if len(grupo) < 2:
            continue
        linhas = descrever_linhas(grupo["linha"])
        diferentes = [
            c for c in comparar if grupo[c].astype("string").fillna("<vazio>").nunique() > 1
        ]
        rotulo = ", ".join(f"{rotulo_coluna(c)} = {_valor(grupo.iloc[0][c])}" for c in chave)
        if diferentes:
            msg = (
                f"As {linhas} têm a mesma chave ({rotulo}) mas valores diferentes em: "
                f"{', '.join(rotulo_coluna(c) for c in diferentes)}. Nenhuma foi apagada; confira qual vale."
            )
            tipo = "duplicata_conflitante"
        else:
            msg = (
                f"As {linhas} são idênticas ({rotulo}): provável lançamento repetido. "
                "Nenhuma foi apagada."
            )
            tipo = "duplicata"
        avisos.append(Aviso(tabela, int(grupo["linha"].iloc[1]), None, tipo, msg))
    return avisos


# ---------------------------------------------------------------- diário


def _sequencias(linhas: list[int]) -> list[list[int]]:
    """Agrupa números de linha consecutivos: [2,3,4,9] → [[2,3,4],[9]]."""
    grupos: list[list[int]] = []
    for n in linhas:
        if grupos and n == grupos[-1][-1] + 1:
            grupos[-1].append(n)
        else:
            grupos.append([n])
    return grupos


def _trecho(sequencia: list[int]) -> str:
    if len(sequencia) == 1:
        return f"linha {sequencia[0]}"
    return f"linhas {sequencia[0]} a {sequencia[-1]}"


def lacunas(grupo: pd.DataFrame, intervalo_esperado_h: float | None = None) -> list[Aviso]:
    """Intervalos sem leitura maiores que LACUNA_FATOR × intervalo típico (mediana)."""
    g = grupo.dropna(subset=["instante_observado"]).drop_duplicates("instante_observado")
    if len(g) < 3:
        return []
    instantes = g["instante_observado"].reset_index(drop=True)
    passos_h = instantes.diff().dt.total_seconds().div(3600)
    tipico = intervalo_esperado_h or float(passos_h[passos_h > 0].median())
    avisos = []
    for i in passos_h.index[1:]:
        if passos_h[i] > LACUNA_FATOR * tipico:
            avisos.append(
                Aviso(
                    "diario",
                    int(g["linha"].iloc[i]),
                    "instante_observado",
                    "lacuna",
                    f"Sem leituras entre {_hora(instantes[i - 1])} e {_hora(instantes[i])} "
                    f"({num(passos_h[i], 0)} h; o intervalo típico é {num(tipico, 1)} h). "
                    "Nada foi preenchido.",
                )
            )
    return avisos


def totalizador_reiniciado(grupo: pd.DataFrame) -> list[Aviso]:
    """Totalizador de vapor que volta para trás (reinício ou troca do medidor)."""
    g = grupo.dropna(subset=["totalizador_vapor_t"])
    avisos = []
    anterior = None
    for _, linha in g.iterrows():
        if anterior is not None and linha["totalizador_vapor_t"] < anterior["totalizador_vapor_t"]:
            avisos.append(
                Aviso(
                    "diario",
                    int(linha["linha"]),
                    "totalizador_vapor_t",
                    "totalizador_reiniciado",
                    f"Totalizador voltou de {num(anterior['totalizador_vapor_t'], 1)} t para "
                    f"{num(linha['totalizador_vapor_t'], 1)} t (linhas {int(anterior['linha'])} e "
                    f"{int(linha['linha'])}): reinício ou troca do medidor. O vapor produzido "
                    "nesse intervalo não é conhecido.",
                )
            )
        anterior = linha
    return avisos


def registro_tardio(
    dados: pd.DataFrame, atraso_maximo_min: float = ATRASO_REGISTRO_MIN
) -> list[Aviso]:
    """Leituras anotadas muito depois de observadas, ou antes de observadas."""
    avisos = []
    validas = dados.dropna(subset=["instante_observado", "instante_registrado"])
    atrasos_min = (
        validas["instante_registrado"] - validas["instante_observado"]
    ).dt.total_seconds() / 60
    for (_, linha), atraso in zip(validas.iterrows(), atrasos_min, strict=True):
        if atraso > atraso_maximo_min:
            avisos.append(
                Aviso(
                    "diario",
                    int(linha["linha"]),
                    "instante_registrado",
                    "registro_tardio",
                    f"Leitura de {_hora(linha['instante_observado'])} anotada "
                    f"{num(atraso / 60, 1)} h depois: pode ter sido escrita de memória.",
                )
            )
        elif atraso < 0:
            avisos.append(
                Aviso(
                    "diario",
                    int(linha["linha"]),
                    "instante_registrado",
                    "registro_antes_da_observacao",
                    "Leitura anotada antes de ser observada: confira os horários.",
                )
            )
    return avisos


def verificar_diario(
    dados: pd.DataFrame,
    intervalo_esperado_h: float | None = None,
    atraso_maximo_min: float = ATRASO_REGISTRO_MIN,
) -> list[Aviso]:
    """Todas as verificações do diário: duplicatas, lacunas, totalizador, registro tardio."""
    avisos = duplicatas(dados, "diario", ("caldeira_id", "instante_observado"))
    ordenado = dados.dropna(subset=["instante_observado"]).sort_values(
        ["instante_observado", "linha"]
    )
    for _, grupo in ordenado.groupby("caldeira_id", sort=False):
        avisos += lacunas(grupo, intervalo_esperado_h)
        avisos += totalizador_reiniciado(grupo)
    avisos += registro_tardio(dados, atraso_maximo_min)
    marcadas = dados.sort_values("linha")
    marcadas = marcadas[marcadas["flag_instrumento_indisponivel"].fillna(False).astype(bool)]
    for sequencia in _sequencias(list(marcadas["linha"])):
        avisos.append(
            Aviso(
                "diario",
                int(sequencia[0]),
                "flag_instrumento_indisponivel",
                "instrumento_indisponivel",
                f"Instrumento marcado como indisponível ({_trecho(sequencia)}): as leituras "
                "afetadas podem não ser confiáveis.",
                "info",
            )
        )
    return avisos


# ---------------------------------------------------------------- combustível e amostras


def verificar_combustivel(dados: pd.DataFrame) -> list[Aviso]:
    """Recebimentos sem fornecedor, sem lote, sem massa ou sem preço; lotes repetidos."""
    avisos = []
    receb = dados[dados["tipo"] == "recebimento"]
    for _, r in receb.iterrows():
        n = int(r["linha"])
        if pd.isna(r["fornecedor_id"]):
            avisos.append(
                Aviso(
                    "combustivel",
                    n,
                    "fornecedor_id",
                    "sem_fornecedor",
                    "Recebimento sem fornecedor: não entra no extrato por fornecedor.",
                )
            )
        if pd.isna(r["lote_id"]):
            avisos.append(
                Aviso(
                    "combustivel",
                    n,
                    "lote_id",
                    "sem_lote",
                    "Recebimento sem lote: não dá para ligar às amostras de umidade.",
                )
            )
        if pd.isna(r["preco_brl"]):
            avisos.append(
                Aviso(
                    "combustivel",
                    n,
                    "preco_brl",
                    "sem_preco",
                    "Recebimento sem preço: não entra no custo por energia.",
                    "info",
                )
            )
    avisos += duplicatas(receb, "combustivel", ("lote_id",))
    return avisos


def verificar_amostras(dados: pd.DataFrame) -> list[Aviso]:
    """Composição que soma mais de 1, composição incompleta, amostra sem umidade."""
    avisos = duplicatas(dados, "amostras", ("amostra_id",))
    for _, a in dados.iterrows():
        n = int(a["linha"])
        presentes = [e for e in ELEMENTOS if not pd.isna(a[e])]
        soma = sum(float(a[c]) for c in (*ELEMENTOS, "cinzas") if not pd.isna(a[c]))
        if soma > 1.0001:
            avisos.append(
                Aviso(
                    "amostras",
                    n,
                    None,
                    "composicao_invalida",
                    f"Composição soma {num(soma, 3)} (mais que 1): confira as frações.",
                )
            )
        if 0 < len(presentes) < len(ELEMENTOS):
            avisos.append(
                Aviso(
                    "amostras",
                    n,
                    None,
                    "composicao_incompleta",
                    "Composição incompleta (falta algum de C, H, O, N, S): esta "
                    "amostra não serve para a perda nos gases.",
                    "info",
                )
            )
        medidas = ("umidade_bu_frac", "pci_seco_mj_kg", *ELEMENTOS, "cinzas")
        if all(pd.isna(a[c]) for c in medidas):
            avisos.append(
                Aviso("amostras", n, None, "amostra_sem_medicao", "Amostra sem nenhuma medição.")
            )
    return avisos
