"""Tipos comuns do motor EULER."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from euler.incerteza import Orcamento

Origem = Literal["medido", "estimado", "assumido"]
"""Origem de um número mostrado ao usuário (AGENTS.md, estilo de texto)."""


class AnaliseBloqueada(Exception):
    """A análise não pode ser feita com os dados disponíveis (AGENTS.md, regra 4).

    Atributos:
        motivo: frase legível para o usuário final explicando o bloqueio.
        falta: o que precisaria ser medido ou informado para desbloquear.
    """

    def __init__(self, motivo: str, falta: list[str] | None = None):
        super().__init__(motivo)
        self.motivo = motivo
        self.falta = list(falta or [])


@dataclass(frozen=True)
class Grandeza:
    """Um número mostrado ao usuário, sempre com unidade e origem.

    incerteza: incerteza expandida U = 2u (k = 2) na mesma unidade, ou None se não há
        incerteza declarada suficiente (o que falta fica em `orcamento.nao_incluidos`).
    nota: de onde veio o número, em linguagem simples.
    orcamento: componentes da incerteza (euler.incerteza), quando conhecidos.
    """

    valor: float
    unidade: str
    origem: Origem
    incerteza: float | None = None
    nota: str = ""
    orcamento: Orcamento | None = field(default=None, compare=False, repr=False)
