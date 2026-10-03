"""Adaptadores de entrada: arquivos do cliente → tabelas normalizadas (preserva o original)."""

from euler.io.leitura import Aviso, Importacao
from euler.io.pacote import Pacote, fontes_de_arquivos, importar_pacote, importar_pasta

__all__ = [
    "Aviso",
    "Importacao",
    "Pacote",
    "fontes_de_arquivos",
    "importar_pacote",
    "importar_pasta",
]
