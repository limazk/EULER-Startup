"""Formatação de números para o usuário final (padrão brasileiro: 1.234,56)."""

import pandas as pd


def num(valor: float | None, casas: int = 2, vazio: str = "—") -> str:
    """Número com vírgula decimal e ponto de milhar; `vazio` quando não há valor.

    Ausente nunca vira zero (AGENTS.md, regra 2).
    """
    if pd.isna(valor):
        return vazio
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def plural(n: int, singular: str, plural_: str) -> str:
    """'1 lote', '3 lotes', '0 lotes' — sem "lote(s)" no texto para o usuário."""
    return f"{n} {singular if n == 1 else plural_}"


def pct(fracao: float | None, casas: int = 1, vazio: str = "—") -> str:
    """Fração como porcentagem brasileira: 0.4215 → '42,2%'."""
    if pd.isna(fracao):
        return vazio
    return f"{num(fracao * 100, casas)}%"
