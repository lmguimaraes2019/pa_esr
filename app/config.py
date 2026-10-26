"""Configuração do app. Tudo que muda entre máquina local e VPS vem de variáveis de ambiente."""
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("ORC_DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.environ.get("ORC_DB", DATA_DIR / "orcamento.db"))
ASSETS_DIR = ROOT / "app" / "assets"
TEMPLATE_PATH = Path(os.environ.get("ORC_TEMPLATE", ROOT / "app" / "assets" / "template_2027.xlsx"))
WEB_DIST = Path(os.environ.get("ORC_WEB_DIST", ROOT / "web" / "dist"))

CICLO_BASE = 2026      # orçamento aprovado, usado como referência
CICLO_PLANO = 2027     # orçamento em elaboração

SESSION_MAX_AGE = int(os.environ.get("ORC_SESSION_HORAS", "12")) * 3600
COOKIE_SECURE = os.environ.get("ORC_COOKIE_SECURE", "0") == "1"
COOKIE_NAME = "orc_session"

LOGIN_MAX_FALHAS = 5
LOGIN_BLOQUEIO_SEG = 300


def secret_key() -> str:
    """Chave de assinatura da sessão: variável de ambiente ou arquivo local gerado uma única vez."""
    env = os.environ.get("ORC_SECRET")
    if env:
        return env
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    f = DATA_DIR / ".secret"
    if not f.exists():
        f.write_text(secrets.token_urlsafe(48))
        f.chmod(0o600)
    return f.read_text().strip()
