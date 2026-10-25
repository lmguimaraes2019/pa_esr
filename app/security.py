"""Senhas (bcrypt), sessão assinada em cookie e limitação de tentativas de login."""
from __future__ import annotations

import secrets
import time

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import config

_serializer: URLSafeTimedSerializer | None = None
_falhas: dict[str, tuple[int, float]] = {}   # chave -> (nº de falhas, bloqueado até)


def hash_password(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8")[:72], bcrypt.gensalt()).decode("ascii")


def verify_password(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8")[:72], senha_hash.encode("ascii"))
    except ValueError:
        return False


def senha_temporaria() -> str:
    return secrets.token_urlsafe(9)


def senha_valida(senha: str) -> str | None:
    """Devolve a mensagem de erro, ou None se a senha é aceitável."""
    if len(senha) < 10:
        return "A senha deve ter pelo menos 10 caracteres."
    if senha.lower() == senha or senha.upper() == senha or not any(ch.isdigit() for ch in senha):
        return "Use letras maiúsculas, minúsculas e pelo menos um número."
    return None


def _ser() -> URLSafeTimedSerializer:
    global _serializer
    if _serializer is None:
        _serializer = URLSafeTimedSerializer(config.secret_key(), salt="orc-session")
    return _serializer


def make_session(user_id: int) -> str:
    return _ser().dumps({"uid": user_id})


def read_session(token: str | None) -> int | None:
    if not token:
        return None
    try:
        return int(_ser().loads(token, max_age=config.SESSION_MAX_AGE)["uid"])
    except (BadSignature, SignatureExpired, KeyError, ValueError):
        return None


def bloqueado(chave: str) -> int:
    """Segundos restantes de bloqueio para a chave (IP + login), 0 se livre."""
    n, ate = _falhas.get(chave, (0, 0.0))
    restante = int(ate - time.time())
    return restante if restante > 0 else 0


def registrar_falha(chave: str) -> None:
    n, ate = _falhas.get(chave, (0, 0.0))
    n += 1
    if n >= config.LOGIN_MAX_FALHAS:
        _falhas[chave] = (0, time.time() + config.LOGIN_BLOQUEIO_SEG)
    else:
        _falhas[chave] = (n, ate)


def limpar_falhas(chave: str) -> None:
    _falhas.pop(chave, None)
