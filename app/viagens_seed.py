"""Carga das viagens a partir da planilha VIAGENS - ORÇAMENTO.

Uso: python -m app.viagens_seed --viagens planilha.xlsx [--reset]
"""
import argparse
from pathlib import Path

from .db import init_db, tx
from . import viagens


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--viagens", required=True, type=Path)
    ap.add_argument("--reset", action="store_true")
    a = ap.parse_args()
    init_db()
    with tx() as c:
        print("Carga de viagens concluída:", viagens.importar(c, a.viagens, a.reset))


if __name__ == "__main__":
    main()
