"""Exportação do orçamento completo em planilha (PMO e diretoria)."""
from __future__ import annotations

import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from . import export_orcamento
from .api import _conn, usuario_liberado
from .db import audit, tx

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/orcamento")
def exportar_orcamento(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    conteudo = export_orcamento.gerar(u, c)
    with tx() as cc:
        audit(cc, u["login"], "exportou orçamento", detalhe="planilha completa")
    nome = f"Orcamento_ESR_2027_{datetime.now():%Y%m%d}.xlsx"
    return Response(conteudo, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})
