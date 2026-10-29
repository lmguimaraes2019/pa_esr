import os
import shutil
from pathlib import Path

import pytest

from app import config, security

UP = Path(os.environ.get("ORC_TEST_UPLOADS", "/mnt/user-data/uploads"))
F_PROTHEUS = UP / "2026_-_Base_Protheus_-_ESR.xlsx"
F_TEMPLATE = UP / "Template_Planejamento_Anual_-_2027.xlsx"
F_PA = UP / "projetos_pa_2026.xlsx"
F_VIAGENS = UP / "VIAGENS_-_ORÇAMENTO_2026_ESR_VProtheus_16102025.xlsx"

precisa_dados = pytest.mark.skipif(
    not (F_PROTHEUS.exists() and F_TEMPLATE.exists() and F_PA.exists()),
    reason="planilhas de origem não encontradas (defina ORC_TEST_UPLOADS)")

ADMIN_SENHA = "SenhaAdmin2027x"


def _apontar(monkeypatch, pasta: Path):
    monkeypatch.setattr(config, "DATA_DIR", pasta)
    monkeypatch.setattr(config, "DB_PATH", pasta / "orcamento.db")
    monkeypatch.setattr(config, "SEMEAR_PO", False)
    monkeypatch.setattr(security, "_serializer", None)
    security._falhas.clear()
    monkeypatch.setenv("ORC_SECRET", "segredo-de-teste")


@pytest.fixture(scope="session")
def banco_semeado(tmp_path_factory):
    """Carga inicial feita uma única vez; cada teste trabalha numa cópia."""
    from _pytest.monkeypatch import MonkeyPatch
    from app.seed import seed
    pasta = tmp_path_factory.mktemp("seed")
    mp = MonkeyPatch()
    try:
        _apontar(mp, pasta)
        info = seed(F_PROTHEUS, F_TEMPLATE, F_PA, admin_senha=ADMIN_SENHA)
        if F_VIAGENS.exists():
            from app import db, viagens
            with db.tx() as c:
                info["viagens"] = viagens.importar(c, F_VIAGENS)
    finally:
        mp.undo()
    return pasta, info


@pytest.fixture()
def env(banco_semeado, tmp_path, monkeypatch):
    pasta, _ = banco_semeado
    for f in pasta.glob("orcamento.db*"):
        shutil.copy(f, tmp_path / f.name)
    shutil.copy(pasta / "senhas_iniciais.txt", tmp_path / "senhas_iniciais.txt")
    _apontar(monkeypatch, tmp_path)
    return tmp_path
