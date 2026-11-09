"""Exposição ao dólar (e ao euro) em 2027: compras previstas em moeda estrangeira, por projeto, no formato da planilha de exposição cambial."""
from __future__ import annotations

import io
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import config
from .api import _arred, _conn, exige_acesso, permitidos, usuario_liberado
from .db import audit, tx

router = APIRouter(prefix="/api/exposicao")

TIPOS = ["HW", "SW", "SV", "Licenças", "CAPACITAÇÕES E INSCRIÇÕES EM EVENTOS", "OA"]      # os usados na planilha histórica (SV = serviços, OA = outros)
TRIMESTRES = {1: "1º TRIMESTRE 2027", 2: "2º TRIMESTRE 2027", 3: "3º TRIMESTRE 2027", 4: "4º TRIMESTRE 2027"}
CABECALHO = ["SC em andamento?", "Diretoria", "Gerência", "Ponto Focal (Pessoa Responsável)", "Tipo", "Processo (ADC ou SC de referência)",
             "Descrição do produto ou serviço", "CC/Projeto", "Fabricante/Fornecedor", "Canal/Distribuidor", "Moeda", "Valor total USD",
             "Valor total EUR", "Pais de Origem", "TRIMESTRE", "Referente ao Programa CONECTA?", "Previsão de abertura de SC"]


class ExposicaoIn(BaseModel):
    orcamento: str = Field(min_length=1, max_length=20)
    sc_andamento: str = Field(default="", pattern="^(Sim|Não|)$")
    diretoria: str = Field(default="DSS", max_length=60)
    gerencia: str = Field(default="ESR", max_length=60)
    ponto_focal: str = Field(default="", max_length=120)
    tipo: str = Field(default="", max_length=40)
    processo: str = Field(default="", max_length=120)
    descricao: str = Field(default="", max_length=400)
    fabricante: str = Field(default="", max_length=120)
    canal: str = Field(default="", max_length=120)
    moeda: str = Field(default="USD", pattern="^(USD|EUR)$")
    valor: float = Field(default=0, ge=0, le=1e10)
    pais_origem: str = Field(default="", max_length=60)
    trimestre: int = Field(default=1, ge=1, le=4)
    conecta: str = Field(default="", pattern="^(Sim|Não|)$")
    previsao_sc: str = Field(default="", max_length=20)


def _cambio(c: sqlite3.Connection) -> dict:
    p = {r["chave"]: float(r["valor"]) for r in c.execute("SELECT chave, valor FROM premissas WHERE chave IN ('dolar','euro')")}
    return {"USD": p.get("dolar", 5.5), "EUR": p.get("euro", 0.0)}


def _item(r: sqlite3.Row, projetos: dict) -> dict:
    p = projetos.get(r["orcamento"])
    falta = [n for n, v in (("descrição", r["descricao"]), ("ponto focal", r["ponto_focal"]), ("tipo", r["tipo"]), ("país de origem", r["pais_origem"])) if not str(v).strip()]
    if r["valor"] <= 0:
        falta.append("valor")
    return {**{k: r[k] for k in ("id", "orcamento", "sc_andamento", "diretoria", "gerencia", "ponto_focal", "tipo", "processo", "descricao", "fabricante",
                                  "canal", "moeda", "valor", "pais_origem", "trimestre", "conecta", "previsao_sc", "atualizado_por")},
            "projeto": p["descricao"] if p else "", "faltando": falta, "completo": not falta}


def _dados(c: sqlite3.Connection, u: dict) -> tuple[list[dict], dict]:
    ids = sorted(permitidos(c, u))
    marks = ",".join("?" for _ in ids) or "''"
    projetos = {r["orcamento"]: r for r in c.execute(f"SELECT orcamento, descricao, gerente, finalidade FROM projetos WHERE orcamento IN ({marks}) ORDER BY orcamento", ids)}
    itens = [_item(r, projetos) for r in c.execute(f"SELECT * FROM exposicao_cambial WHERE orcamento IN ({marks}) ORDER BY trimestre, id", ids)]
    return itens, projetos


@router.get("")
def listar(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    itens, projetos = _dados(c, u)
    cam = _cambio(c)
    usd = sum(i["valor"] for i in itens if i["moeda"] == "USD")
    eur = sum(i["valor"] for i in itens if i["moeda"] == "EUR")
    por_tri = [{"trimestre": q, "nome": TRIMESTRES[q], "usd": _arred(sum(i["valor"] for i in itens if i["trimestre"] == q and i["moeda"] == "USD")),
                "eur": _arred(sum(i["valor"] for i in itens if i["trimestre"] == q and i["moeda"] == "EUR")), "itens": sum(1 for i in itens if i["trimestre"] == q)}
               for q in TRIMESTRES]
    return {"itens": itens, "cambio": cam, "tipos": TIPOS, "trimestres": [{"n": k, "nome": v} for k, v in TRIMESTRES.items()],
            "por_trimestre": por_tri,
            "totais": {"usd": _arred(usd), "eur": _arred(eur), "brl_usd": _arred(usd * cam["USD"]), "brl_eur": _arred(eur * cam["EUR"]),
                       "itens": len(itens), "incompletos": sum(1 for i in itens if not i["completo"])},
            "projetos": [{"orcamento": o, "descricao": p["descricao"], "gerente": p["gerente"], "finalidade": p["finalidade"]} for o, p in projetos.items()]}


def _valores(d: ExposicaoIn, u: dict):
    t = lambda x: x.strip()
    return (d.orcamento, d.sc_andamento, t(d.diretoria), t(d.gerencia), t(d.ponto_focal), t(d.tipo), t(d.processo), t(d.descricao), t(d.fabricante),
            t(d.canal), d.moeda, d.valor, t(d.pais_origem), d.trimestre, d.conecta, t(d.previsao_sc), u["login"])


COLS = "orcamento, sc_andamento, diretoria, gerencia, ponto_focal, tipo, processo, descricao, fabricante, canal, moeda, valor, pais_origem, trimestre, conecta, previsao_sc, atualizado_por"


def _uma(c: sqlite3.Connection, xid: int) -> dict:
    r = c.execute("SELECT * FROM exposicao_cambial WHERE id=?", (xid,)).fetchone()
    p = {x["orcamento"]: x for x in c.execute("SELECT orcamento, descricao FROM projetos WHERE orcamento=?", (r["orcamento"],))}
    return _item(r, p)


@router.post("", status_code=201)
def criar(d: ExposicaoIn, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        exige_acesso(c, u, d.orcamento)
        cur = c.execute(f"INSERT INTO exposicao_cambial ({COLS}) VALUES ({','.join('?' for _ in COLS.split(','))})", _valores(d, u))
        audit(c, u["login"], "incluiu exposição cambial", d.orcamento, detalhe=f"{d.moeda} {d.valor}: {d.descricao}"[:200])
        return _uma(c, cur.lastrowid)


@router.put("/{xid}")
def editar(xid: int, d: ExposicaoIn, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        atual = c.execute("SELECT * FROM exposicao_cambial WHERE id=?", (xid,)).fetchone()
        if not atual:
            raise HTTPException(404, "Lançamento não encontrado.")
        exige_acesso(c, u, atual["orcamento"]); exige_acesso(c, u, d.orcamento)
        c.execute("UPDATE exposicao_cambial SET " + ", ".join(k.strip() + "=?" for k in COLS.split(",")) + ", atualizado_em=datetime('now') WHERE id=?", (*_valores(d, u), xid))
        audit(c, u["login"], "editou exposição cambial", d.orcamento, detalhe=f"id {xid}")
        return _uma(c, xid)


@router.delete("/{xid}")
def excluir(xid: int, u: dict = Depends(usuario_liberado)):
    with tx() as c:
        atual = c.execute("SELECT * FROM exposicao_cambial WHERE id=?", (xid,)).fetchone()
        if not atual:
            raise HTTPException(404, "Lançamento não encontrado.")
        exige_acesso(c, u, atual["orcamento"])
        c.execute("DELETE FROM exposicao_cambial WHERE id=?", (xid,))
        audit(c, u["login"], "excluiu exposição cambial", atual["orcamento"], detalhe=f"id {xid}")
    return {"ok": True}


@router.get("/xlsx")
def planilha(u: dict = Depends(usuario_liberado), c: sqlite3.Connection = Depends(_conn)):
    """Planilha de exposição cambial no formato enviado à área responsável."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    itens, projetos = _dados(c, u)
    wb = Workbook(); ws = wb.active; ws.title = "Exposição cambial 2027"
    ws.append(CABECALHO)
    for col in ws[1]:
        col.font = Font(bold=True, color="FFFFFF"); col.fill = PatternFill("solid", fgColor="003057")
        col.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    for i in itens:
        ws.append([i["sc_andamento"].upper(), i["diretoria"], i["gerencia"], i["ponto_focal"], i["tipo"], i["processo"], i["descricao"],
                   f"{i['orcamento']} - {i['projeto']}", i["fabricante"], i["canal"], i["moeda"],
                   i["valor"] if i["moeda"] == "USD" else None, i["valor"] if i["moeda"] == "EUR" else None,
                   i["pais_origem"], TRIMESTRES[i["trimestre"]], i["conecta"].upper(), i["previsao_sc"]])
    for linha in ws.iter_rows(min_row=2):
        linha[11].number_format = linha[12].number_format = '#,##0.00'
    for letra, larg in zip("ABCDEFGHIJKLMNOPQ", (12, 10, 12, 24, 12, 24, 40, 44, 22, 22, 8, 16, 16, 14, 20, 16, 18)):
        ws.column_dimensions[letra].width = larg
    ws.row_dimensions[1].height = 42; ws.freeze_panes = "A2"
    buf = io.BytesIO(); wb.save(buf)
    return Response(buf.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="exposicao_cambial_2027.xlsx"'})
