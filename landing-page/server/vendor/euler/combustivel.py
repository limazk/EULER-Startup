"""Combustível: PCI úmido, queimado no período, energia e extrato por fornecedor (E5, E9–E11).

Convenções (docs/fisica/fisica_para_revisao.md): umidade `w` em base úmida (kg de água
por kg de combustível úmido, fração de 0 a 1); PCI em MJ/kg; massas em kg.
"""

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from euler.formato import num, pct
from euler.tipos import AnaliseBloqueada

H_VAP_25C_MJ_KG = 2.442
"""Calor de vaporização da água a 25 °C usado no PCI (E5, pendente de revisão)."""


def _checar_umidade(umidade_bu_frac: float) -> None:
    if 1 < umidade_bu_frac <= 100:
        raise AnaliseBloqueada(
            f"Umidade {umidade_bu_frac:g} parece estar em %; o contrato pede fração "
            f"(ex.: 0,40 para 40%)."
        )
    if not 0 <= umidade_bu_frac < 1:
        raise AnaliseBloqueada(f"Umidade {umidade_bu_frac:g} fora da faixa (0 a 1, base úmida).")


def pci_umido(pci_seco_mj_kg: float, umidade_bu_frac: float) -> float:
    """PCI do combustível como recebido (MJ/kg úmido), E5.

    PCI_u = (1 − w)·PCI_seco − 2,442·w

    Entradas: PCI em base seca (MJ/kg seco) e umidade em base úmida (fração).
    Hipótese (pergunta aberta no E5): PCI_seco já desconta a água formada pelo H.
    """
    _checar_umidade(umidade_bu_frac)
    if pci_seco_mj_kg <= 0:
        raise AnaliseBloqueada(f"PCI seco de {pci_seco_mj_kg:g} MJ/kg não é positivo.")
    pci = (1 - umidade_bu_frac) * pci_seco_mj_kg - H_VAP_25C_MJ_KG * umidade_bu_frac
    if pci <= 0:
        raise AnaliseBloqueada(
            f"Com umidade {umidade_bu_frac:.0%} o PCI úmido fica sem energia líquida "
            f"({pci:.2f} MJ/kg). Confira a umidade."
        )
    return pci


def combustivel_queimado_kg(
    estoque_inicial_kg: float | None,
    recebimentos_kg: Sequence[float | None],
    estoque_final_kg: float | None,
) -> float:
    """Combustível queimado no período (kg), E9.

    M_f = estoque_inicial + Σ recebimentos − estoque_final

    Todas as massas na mesma base de umidade (como recebido). Sem estoque medido
    no início ou no fim, a análise é bloqueada: nunca se assume estoque.
    """
    if estoque_inicial_kg is None:
        raise AnaliseBloqueada(
            "Sem estoque inicial medido, não dá para saber quanto combustível foi queimado.",
            falta=["medição de estoque no início do período"],
        )
    if estoque_final_kg is None:
        raise AnaliseBloqueada(
            "Sem estoque final medido, não dá para saber quanto combustível foi queimado.",
            falta=["medição de estoque no fim do período"],
        )
    if any(m is None for m in recebimentos_kg):
        raise AnaliseBloqueada(
            "Há recebimento sem massa conhecida no período; o total recebido não é conhecido.",
            falta=["massa de todos os recebimentos (ou volume com densidade declarada)"],
        )
    queimado = estoque_inicial_kg + sum(recebimentos_kg) - estoque_final_kg
    if queimado < 0:
        raise AnaliseBloqueada(
            "Estoque final maior que estoque inicial mais recebimentos: os registros estão "
            "inconsistentes (recebimento faltando ou medição de estoque errada)."
        )
    return queimado


def energia_combustivel_mj(
    massas_kg: Sequence[float | None], pcis_umidos_mj_kg: Sequence[float | None]
) -> float:
    """Energia do combustível queimado: E_f = Σ M_f,i · PCI_u,i (MJ), parte de E10.

    Cada parcela i é uma porção de combustível com PCI úmido próprio (ex.: lote).
    Bloqueia se alguma parcela não tiver massa ou PCI conhecidos.
    """
    if len(massas_kg) != len(pcis_umidos_mj_kg):
        raise ValueError("massas e PCIs precisam ter o mesmo tamanho")
    if any(m is None for m in massas_kg) or any(p is None for p in pcis_umidos_mj_kg):
        raise AnaliseBloqueada(
            "Há combustível sem massa ou sem PCI conhecido; a energia total não é conhecida.",
            falta=["umidade medida de cada lote queimado"],
        )
    return sum(m * p for m, p in zip(massas_kg, pcis_umidos_mj_kg, strict=True))


# ---------------------------------------------------------------- extrato por fornecedor (M1)

LOTES_REFERENCIA = 10
"""Faixa de referência de umidade = primeiros 10 lotes medidos do fornecedor (D20)."""
REFERENCIA_MIN_LOTES = 5
"""Com menos de 5 lotes na referência, não há faixa (D20)."""
FAIXA_DESVIOS = 3.0
"""Alerta fora de média ± 3 desvios-padrão da referência (limites de controle, D20)."""


@dataclass
class Extrato:
    """Extrato de energia por fornecedor (E11).

    lotes: uma linha por recebimento, com energia, R$/GJ, umidade e origem dos dados.
    fornecedores: uma linha por fornecedor, com totais e posição no ranking por R$/GJ.
    """

    lotes: pd.DataFrame
    fornecedores: pd.DataFrame

    @property
    def lotes_nao_determinados(self) -> pd.DataFrame:
        return self.lotes[self.lotes["situacao"] != "determinada"]

    @property
    def alertas_umidade(self) -> pd.DataFrame:
        return self.lotes[self.lotes["alerta_umidade"].notna()]


def _amostras_por_lote(amostras: pd.DataFrame | None) -> tuple[dict, dict, set]:
    """Umidade média (só valores válidos) e nº de amostras por lote; PCI seco por lote."""
    if amostras is None or amostras.empty:
        return {}, {}, set()
    a = amostras.dropna(subset=["lote_id"])
    validas = a[a["umidade_bu_frac"].between(0, 1, inclusive="left")]
    invalidas = set(a.loc[a["umidade_bu_frac"].notna(), "lote_id"]) - set(validas["lote_id"])
    umid = validas.groupby("lote_id")["umidade_bu_frac"].agg(["mean", "count"])
    pci = a.dropna(subset=["pci_seco_mj_kg"]).groupby("lote_id")["pci_seco_mj_kg"].mean()
    return (
        {k: (float(r["mean"]), int(r["count"])) for k, r in umid.iterrows()},
        {k: float(v) for k, v in pci.items()},
        invalidas,
    )


def _pci_mais_proximo(
    amostras: pd.DataFrame | None, lotes_do_fornecedor: set, data: pd.Timestamp
) -> float | None:
    """PCI seco da amostra do mesmo fornecedor mais próxima no tempo (D19)."""
    if amostras is None or amostras.empty:
        return None
    a = amostras[amostras["lote_id"].isin(lotes_do_fornecedor)].dropna(subset=["pci_seco_mj_kg"])
    if a.empty:
        return None
    distancia = (a["data"] - data).abs()
    return float(a.loc[distancia.idxmin(), "pci_seco_mj_kg"])


def _alerta_umidade(referencia: list[float], w: float) -> tuple[str | None, str | None]:
    """Compara a umidade do lote com a faixa de referência do fornecedor (texto neutro).

    Referência: primeiros lotes medidos do fornecedor nos dados (até LOTES_REFERENCIA).
    Faixa: média ± FAIXA_DESVIOS desvios-padrão (limites de controle de Shewhart).
    """
    if len(referencia) < REFERENCIA_MIN_LOTES:
        return None, f"referência insuficiente ({len(referencia)} lotes medidos antes)"
    serie = pd.Series(referencia)
    media, desvio = serie.mean(), serie.std(ddof=1)
    lo = media - FAIXA_DESVIOS * desvio
    hi = media + FAIXA_DESVIOS * desvio
    faixa = f"{pct(lo)} a {pct(hi)}, pelos primeiros {len(referencia)} lotes"
    if w > hi:
        return f"Umidade de {pct(w)} acima da faixa histórica do fornecedor ({faixa}).", faixa
    if w < lo:
        return f"Umidade de {pct(w)} abaixo da faixa histórica do fornecedor ({faixa}).", faixa
    return None, faixa


def extrato_por_fornecedor(
    combustivel: pd.DataFrame,
    amostras: pd.DataFrame | None,
    inicio: pd.Timestamp | None = None,
    fim: pd.Timestamp | None = None,
) -> Extrato:
    """Energia entregue e custo por energia de cada lote e fornecedor (E11, T09).

    Para cada recebimento:
        E_lote = M_lote · PCI_u(w_lote)   (MJ; exibido em GJ)
        R$/GJ  = preço_total_lote / (E_lote / 1000)

    Origem dos dados:
        massa: `medido` (balança) ou `estimado` (volume × densidade declarada);
        umidade: `medido` (média das amostras do lote). Lote sem umidade medida fica
        com energia **não determinada**: a umidade nunca é assumida;
        PCI seco: `medido` (amostra do lote) ou `assumido` (amostra do mesmo
        fornecedor mais próxima no tempo, D19). Sem nenhuma, energia não determinada.

    Entradas: tabelas normalizadas `combustivel` e `amostras` (euler.io); período
    opcional pelas datas de recebimento (inclusivo).
    """
    receb = combustivel[combustivel["tipo"] == "recebimento"].copy()
    if inicio is not None:
        receb = receb[receb["data"] >= inicio]
    if fim is not None:
        receb = receb[receb["data"] <= fim]
    receb = receb.sort_values(["data", "linha"])

    umidade_lote, pci_lote, umidade_invalida = _amostras_por_lote(amostras)
    lotes_por_fornecedor = (
        combustivel.dropna(subset=["fornecedor_id", "lote_id"])
        .groupby("fornecedor_id")["lote_id"]
        .agg(set)
        .to_dict()
    )
    historico: dict[str, list[float]] = {}

    linhas = []
    for _, r in receb.iterrows():
        forn, lote = r["fornecedor_id"], r["lote_id"]
        massa = None if pd.isna(r["massa_kg_calc"]) else float(r["massa_kg_calc"])
        preco = None if pd.isna(r["preco_brl"]) else float(r["preco_brl"])
        item = {
            "data": r["data"],
            "fornecedor_id": forn,
            "lote_id": lote,
            "massa_kg": massa,
            "massa_origem": r["massa_origem"] if not pd.isna(r["massa_origem"]) else None,
            "preco_brl": preco,
            "preco_brl_t": preco / (massa / 1000) if preco is not None and massa else None,
            "umidade_bu_frac": None,
            "umidade_origem": None,
            "pci_seco_mj_kg": None,
            "pci_seco_origem": None,
            "pci_umido_mj_kg": None,
            "energia_gj": None,
            "brl_gj": None,
            "situacao": "não determinada",
            "motivo": None,
            "alerta_umidade": None,
            "alerta_direcao": None,
            "faixa_historica": None,
        }
        motivos = []
        if massa is None:
            motivos.append("massa desconhecida (sem balança e sem densidade declarada)")
        if lote in umidade_lote:
            w, n = umidade_lote[lote]
            item["umidade_bu_frac"] = w
            item["umidade_origem"] = f"medido ({n} amostra{'s' if n > 1 else ''})"
            if not pd.isna(forn):
                referencia = historico.setdefault(forn, [])
                alerta, faixa = _alerta_umidade(referencia[:LOTES_REFERENCIA], w)
                item["alerta_umidade"], item["faixa_historica"] = alerta, faixa
                if alerta:
                    item["alerta_direcao"] = "acima" if " acima " in alerta else "abaixo"
                referencia.append(w)
        elif lote in umidade_invalida:
            motivos.append("umidade da amostra fora de 0 a 1 (unidade a conferir)")
        else:
            motivos.append("umidade do lote não medida")

        if lote in pci_lote:
            item["pci_seco_mj_kg"], item["pci_seco_origem"] = pci_lote[lote], "medido"
        else:
            pci = _pci_mais_proximo(amostras, lotes_por_fornecedor.get(forn, set()), r["data"])
            if pci is None:
                motivos.append("PCI seco não medido para este fornecedor")
            else:
                item["pci_seco_mj_kg"] = pci
                item["pci_seco_origem"] = "assumido (amostra mais próxima do fornecedor)"

        if not motivos:
            try:
                pci_u = pci_umido(item["pci_seco_mj_kg"], item["umidade_bu_frac"])
            except AnaliseBloqueada as bloqueio:
                motivos.append(bloqueio.motivo)
            else:
                item["pci_umido_mj_kg"] = pci_u
                item["energia_gj"] = massa * pci_u / 1000
                item["situacao"] = "determinada"
                if preco is not None:
                    item["brl_gj"] = preco / item["energia_gj"]
                else:
                    item["motivo"] = "sem preço: custo por energia não calculado"
        if motivos:
            item["motivo"] = "; ".join(motivos)
        linhas.append(item)

    lotes = pd.DataFrame(linhas, columns=list(_COLUNAS_LOTE))
    return Extrato(lotes=lotes, fornecedores=_resumo_fornecedores(lotes))


_COLUNAS_LOTE = (
    "data", "fornecedor_id", "lote_id", "massa_kg", "massa_origem", "preco_brl", "preco_brl_t",
    "umidade_bu_frac", "umidade_origem", "pci_seco_mj_kg", "pci_seco_origem", "pci_umido_mj_kg",
    "energia_gj", "brl_gj", "situacao", "motivo", "alerta_umidade", "alerta_direcao",
    "faixa_historica",
)  # fmt: skip


def _media_umidade(lotes_forn: pd.DataFrame, primeiros: bool) -> float | None:
    """Umidade média dos primeiros (ou dos últimos) LOTES_REFERENCIA lotes medidos."""
    medidos = lotes_forn.dropna(subset=["umidade_bu_frac"]).sort_values("data")["umidade_bu_frac"]
    if len(medidos) < REFERENCIA_MIN_LOTES:
        return None
    parte = medidos.head(LOTES_REFERENCIA) if primeiros else medidos.tail(LOTES_REFERENCIA)
    return float(parte.mean())


def _resumo_fornecedores(lotes: pd.DataFrame) -> pd.DataFrame:
    """Totais por fornecedor e ranking por custo de energia (R$/GJ, menor = 1º)."""
    linhas = []
    for forn, g in lotes.dropna(subset=["fornecedor_id"]).groupby("fornecedor_id"):
        det = g[g["situacao"] == "determinada"]
        det_preco = det.dropna(subset=["brl_gj"])
        com_preco = g.dropna(subset=["preco_brl", "massa_kg"])
        energia_preco = det_preco["energia_gj"].sum()
        massa_det = det["massa_kg"].sum()
        linhas.append(
            {
                "fornecedor_id": forn,
                "lotes": len(g),
                "lotes_determinados": len(det),
                "massa_t": g["massa_kg"].sum() / 1000,
                "brl_t": (
                    com_preco["preco_brl"].sum() / (com_preco["massa_kg"].sum() / 1000)
                    if len(com_preco)
                    else None
                ),
                "umidade_referencia": _media_umidade(g, primeiros=True),
                "umidade_recente": _media_umidade(g, primeiros=False),
                "umidade_media": (
                    (det["umidade_bu_frac"] * det["massa_kg"]).sum() / massa_det
                    if massa_det
                    else None
                ),
                "energia_gj": det["energia_gj"].sum() if len(det) else None,
                "brl_gj": det_preco["preco_brl"].sum() / energia_preco if energia_preco else None,
                "alertas_umidade": int(g["alerta_umidade"].notna().sum()),
            }
        )
    resumo = pd.DataFrame(linhas)
    if resumo.empty:
        return resumo
    resumo["posicao_energia"] = resumo["brl_gj"].rank(method="min").astype("Int64")
    resumo["posicao_tonelada"] = resumo["brl_t"].rank(method="min").astype("Int64")
    return resumo.sort_values(["posicao_energia", "fornecedor_id"], na_position="last").reset_index(
        drop=True
    )


def frase_tonelada_vs_energia(fornecedores: pd.DataFrame) -> str | None:
    """Frase neutra quando o mais barato por tonelada não é o mais barato por energia."""
    f = fornecedores.dropna(subset=["brl_t", "brl_gj"])
    if len(f) < 2:
        return None
    por_t = f.loc[f["brl_t"].idxmin()]
    por_gj = f.loc[f["brl_gj"].idxmin()]
    if por_t["fornecedor_id"] == por_gj["fornecedor_id"]:
        return None
    return (
        f"{por_t['fornecedor_id']} tem o menor preço por tonelada "
        f"(R$ {num(por_t['brl_t'])}/t), mas custa R$ {num(por_t['brl_gj'])} por GJ de energia. "
        f"O menor custo por energia é de {por_gj['fornecedor_id']}: "
        f"R$ {num(por_gj['brl_gj'])}/GJ (a R$ {num(por_gj['brl_t'])}/t)."
    )


def extrato_semanal(lotes: pd.DataFrame) -> pd.DataFrame:
    """Por semana (segunda-feira) e fornecedor: umidade média, energia e R$/GJ.

    Usa só lotes com energia determinada; umidade e R$/GJ ponderados pela massa e
    pela energia. Serve para ver tendências (ex.: umidade subindo).
    """
    det = lotes[lotes["situacao"] == "determinada"].dropna(subset=["fornecedor_id"]).copy()
    if det.empty:
        return pd.DataFrame(
            columns=["semana", "fornecedor_id", "lotes", "umidade_media", "energia_gj", "brl_gj"]
        )
    datas = det["data"].dt.tz_localize(None).dt.normalize()
    det["semana"] = datas - pd.to_timedelta(datas.dt.weekday, unit="D")
    det["_w_m"] = det["umidade_bu_frac"] * det["massa_kg"]
    linhas = []
    for (semana, forn), g in det.groupby(["semana", "fornecedor_id"]):
        com_preco = g.dropna(subset=["brl_gj"])
        linhas.append(
            {
                "semana": semana,
                "fornecedor_id": forn,
                "lotes": len(g),
                "umidade_media": g["_w_m"].sum() / g["massa_kg"].sum(),
                "energia_gj": g["energia_gj"].sum(),
                "brl_gj": (
                    com_preco["preco_brl"].sum() / com_preco["energia_gj"].sum()
                    if len(com_preco)
                    else None
                ),
            }
        )
    return pd.DataFrame(linhas)
