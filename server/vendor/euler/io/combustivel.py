"""Importador de recebimentos e estoques de combustível, `combustivel.csv` (T05)."""

import pandas as pd

from euler import qualidade
from euler.io.esquemas import rotulo_categoria
from euler.io.leitura import FUSO_PADRAO, Aviso, Fonte, Importacao, importar_tabela


def importar_combustivel(fonte: Fonte, fuso: str = FUSO_PADRAO) -> Importacao:
    """Lê, normaliza e verifica recebimentos e estoques.

    Massa: se `massa_kg` foi pesada, origem `medido`. Sem massa, com volume e
    densidade declarada, massa = volume × densidade, origem `estimado`. Volume sem
    densidade **não** vira massa: fica ausente com aviso (T05).
    Colunas criadas: `massa_kg_calc` e `massa_origem`.
    """
    imp = importar_tabela("combustivel", fonte, fuso)
    if imp.bloqueada:
        return imp
    d = imp.dados
    massa = d["massa_kg"].copy()
    origem = pd.Series([pd.NA] * len(d), dtype="string")
    origem[d["massa_kg"].notna()] = "medido"

    sem_massa = d["massa_kg"].isna()
    com_volume = d["volume_m3"].notna()
    com_densidade = d["densidade_kg_m3"].notna()
    estimar = sem_massa & com_volume & com_densidade
    massa[estimar] = d.loc[estimar, "volume_m3"] * d.loc[estimar, "densidade_kg_m3"]
    origem[estimar] = "estimado"

    for _, r in d[estimar].iterrows():
        fonte_dens = (
            rotulo_categoria(r["origem_densidade"])
            if not pd.isna(r["origem_densidade"])
            else "não informada"
        )
        imp.avisos.append(
            Aviso(
                "combustivel",
                int(r["linha"]),
                "massa_kg",
                "massa_estimada",
                f"Massa estimada = {r['volume_m3']:g} m³ × {r['densidade_kg_m3']:g} kg/m³ "
                f"(origem da densidade: {fonte_dens}).",
                "info",
            )
        )
    for _, r in d[sem_massa & com_volume & ~com_densidade].iterrows():
        imp.avisos.append(
            Aviso(
                "combustivel",
                int(r["linha"]),
                "densidade_kg_m3",
                "volume_sem_densidade",
                "Volume sem densidade declarada: a massa não foi calculada e este registro "
                "fica fora das contas de massa e energia.",
            )
        )
    for _, r in d[sem_massa & ~com_volume].iterrows():
        imp.avisos.append(
            Aviso(
                "combustivel",
                int(r["linha"]),
                "massa_kg",
                "sem_quantidade",
                "Registro sem massa e sem volume: quantidade desconhecida.",
            )
        )

    d["massa_kg_calc"] = massa
    d["massa_origem"] = origem
    imp.avisos += qualidade.verificar_combustivel(d)
    return imp
