"""Montagem de relatórios em Word a partir do modelo .dotx (capa, sumário, cabeçalho, estilos e página divisória do modelo).

O corpo é escrito como XML de parágrafos e tabelas que usam os estilos do próprio modelo (Título 1/2/3, TEXTO CORRIDO,
INTRODUÇÃO, Legenda); a capa, o cabeçalho e a página divisória são os do modelo, só com o texto trocado."""
from __future__ import annotations

import copy
import io
import math
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree

MODELO = Path(__file__).parent / "assets" / "relatorio_modelo.dotx"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}
NAVY, CIANO, VERDE, CINZA, ROXO, LARANJA, AZUL = "000A8C", "00AAE6", "46C832", "BFBFBF", "3C0064", "FF872D", "001EFF"
LARGURA = 9638          # largura útil da página em dxa (17 cm)
LINHAS_PAGINA = 50      # estimativa de linhas de texto por página, para os números do sumário

_PGSZ = '<w:pgSz w:w="11906" w:h="16838" w:code="9"/><w:pgMar w:top="1418" w:right="1134" w:bottom="1134" w:left="1134" w:header="709" w:footer="709" w:gutter="0"/>'


def sect(num_inicial: int | None = None, titulo_pg: bool = False, tipo: str = "nextPage") -> str:
    return (f'<w:sectPr><w:type w:val="{tipo}"/>' + _PGSZ + (f'<w:pgNumType w:start="{num_inicial}"/>' if num_inicial is not None else "")
            + '<w:cols w:space="340"/>' + ("<w:titlePg/>" if titulo_pg else "") + '<w:docGrid w:linePitch="360"/></w:sectPr>')


def esc(t) -> str:
    return escape(str(t), {'"': "&quot;"})


def _runs(texto: str, base: str = "") -> str:
    """Texto com **negrito** em linha."""
    out = []
    for i, parte in enumerate(re.split(r"\*\*", str(texto))):
        if not parte:
            continue
        rpr = base + ("<w:b/><w:bCs/>" if i % 2 else "")
        out.append(f'<w:r>{"<w:rPr>" + rpr + "</w:rPr>" if rpr else ""}<w:t xml:space="preserve">{esc(parte)}</w:t></w:r>')
    return "".join(out)


class Doc:
    """Acumula o corpo do relatório e estima a página de cada título (o Word recalcula o sumário ao abrir)."""

    def __init__(self) -> None:
        self.x: list[str] = []
        self.toc: list[dict] = []
        self.imgs: list[bytes] = []
        self.pagina, self.alt = 0, 0.0
        self.bm = 0
        self.fig = 0
        self.tab = 0
        self.nd = 0

    # ---- paginação estimada
    def _gasta(self, linhas: float) -> None:
        if self.alt + linhas > LINHAS_PAGINA:
            self.pagina += 1
            self.alt = linhas
        else:
            self.alt += linhas

    def nova_pagina(self, xml: bool = True) -> None:
        if xml:
            self.x.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        self.pagina += 1
        self.alt = 0

    # ---- parágrafos
    def p(self, texto: str = "", estilo: str = "TEXTOCORRIDO", jc: str | None = None, negrito: bool = False, cor: str | None = None,
          tam: int | None = None, keep: bool = False, antes: int | None = None, depois: int | None = None, outline: int | None = None,
          italico: bool = False) -> None:
        ppr = f'<w:pStyle w:val="{estilo}"/>' + ("<w:keepNext/>" if keep else "")
        if antes is not None or depois is not None:
            ppr += "<w:spacing" + (f' w:before="{antes}"' if antes is not None else "") + (f' w:after="{depois}"' if depois is not None else "") + "/>"
        if jc:
            ppr += f'<w:jc w:val="{jc}"/>'
        if outline is not None:
            ppr += f'<w:outlineLvl w:val="{outline}"/>'
        rpr = ("<w:b/><w:bCs/>" if negrito else "") + ("<w:i/><w:iCs/>" if italico else "") + (f'<w:color w:val="{cor}"/>' if cor else "") \
            + (f'<w:sz w:val="{tam}"/><w:szCs w:val="{tam}"/>' if tam else "")
        self.x.append(f"<w:p><w:pPr>{ppr}</w:pPr>{_runs(texto, rpr)}</w:p>")
        if texto:
            chars = 100 if estilo == "TEXTOCORRIDO" else 70 if estilo == "INTRODUO" else 90
            self._gasta(math.ceil(len(texto) / chars) * (1.5 if estilo == "INTRODUO" else 1.0) + 0.6)

    def lead(self, texto: str) -> None:
        self.p(texto, "INTRODUO")

    def titulo(self, nivel: int, texto: str, toc: bool | None = None, quebra: bool = False) -> None:
        """nivel 1 = Título 1 (entra no sumário), 2 = Título 2, 3 = Título 3 (não entram no sumário)."""
        if quebra:
            self.nova_pagina()
        elif self.alt + 5 > LINHAS_PAGINA:
            self.pagina += 1
            self.alt = 0
        toc = (nivel == 1) if toc is None else toc
        estilo = f"Ttulo{nivel}"
        ppr = f'<w:pStyle w:val="{estilo}"/><w:keepNext/>'
        ppr += f'<w:outlineLvl w:val="{1 if toc else 9}"/>'
        cor = '<w:color w:val="00AAE6"/>' if nivel == 1 else ""
        nome = None
        if toc:
            self.bm += 1
            nome = f"_Toc9{self.bm:05d}"
            self.toc.append({"nivel": 1, "texto": texto, "bm": nome, "pagina": self.pagina})
            self.x.append(f'<w:p><w:pPr>{ppr}</w:pPr><w:bookmarkStart w:id="{self.bm}" w:name="{nome}"/>{_runs(texto, cor)}<w:bookmarkEnd w:id="{self.bm}"/></w:p>')
        else:
            self.x.append(f"<w:p><w:pPr>{ppr}</w:pPr>{_runs(texto, cor)}</w:p>")
        self._gasta(2.6 if nivel == 1 else 1.8)

    # ---- tabelas
    def tabela(self, cab: list[str], linhas: list[list], larg: list[int], alin: list[str] | None = None, total: list | None = None,
               tam: int = 16, legenda: str | None = None, destaque: set[int] | None = None) -> None:
        """larg em dxa (soma = LARGURA). alin: 'left'/'right'/'center' por coluna. total: linha final em negrito."""
        k = len(cab)
        alin = alin or ["left"] + ["right"] * (k - 1)
        esc_ = sum(larg)
        larg = [round(x * LARGURA / esc_) for x in larg]
        larg[-1] += LARGURA - sum(larg)

        def cel(txt, i, fundo=None, cor=None, neg=False, topo=False):
            borda = f'<w:tcBorders><w:top w:val="single" w:sz="8" w:space="0" w:color="{CIANO}"/></w:tcBorders>' if topo else ""
            shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{fundo}"/>' if fundo else ""
            rpr = ("<w:b/><w:bCs/>" if neg else "") + (f'<w:color w:val="{cor}"/>' if cor else "") + f'<w:sz w:val="{tam}"/><w:szCs w:val="{tam}"/>'
            return (f'<w:tc><w:tcPr><w:tcW w:w="{larg[i]}" w:type="dxa"/>{borda}{shd}<w:vAlign w:val="center"/></w:tcPr>'
                    f'<w:p><w:pPr><w:pStyle w:val="TEXTOCORRIDO"/><w:shd w:val="clear" w:color="auto" w:fill="auto"/><w:spacing w:before="30" w:after="30"/>'
                    f'<w:jc w:val="{alin[i]}"/></w:pPr>{_runs(txt, rpr)}</w:p></w:tc>')

        grade = "".join(f'<w:gridCol w:w="{x}"/>' for x in larg)
        linhas_xml = ['<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>' + "".join(cel(h, i, NAVY, "FFFFFF", True) for i, h in enumerate(cab)) + "</w:tr>"]
        for n, lin in enumerate(linhas):
            zebra = "EEF6FB" if n % 2 else None
            neg = n in (destaque or set())
            linhas_xml.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>' + "".join(cel(v, i, zebra, None, neg) for i, v in enumerate(lin)) + "</w:tr>")
        if total:
            linhas_xml.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>' + "".join(cel(v, i, "DDEFF8", NAVY, True, True) for i, v in enumerate(total)) + "</w:tr>")
        self.x.append(
            f'<w:tbl><w:tblPr><w:tblW w:w="{LARGURA}" w:type="dxa"/><w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="{CINZA}"/>'
            f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="{CINZA}"/><w:insideH w:val="single" w:sz="2" w:space="0" w:color="{CINZA}"/></w:tblBorders>'
            f'<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="70" w:type="dxa"/><w:right w:w="70" w:type="dxa"/></w:tblCellMar></w:tblPr>'
            f'<w:tblGrid>{grade}</w:tblGrid>{"".join(linhas_xml)}</w:tbl>')
        # estimativa de altura: uma linha por linha da tabela, mais as quebras de texto da coluna mais apertada
        for lin in [cab] + linhas + ([total] if total else []):
            quebras = max((math.ceil(len(re.sub(r"\*\*", "", str(v))) * (tam / 16) / max(larg[i] / 100 * 1.15, 1)) for i, v in enumerate(lin)), default=1)
            self._gasta(0.80 * max(quebras, 1) + 0.12)
        if legenda:
            self.tab += 1
            self.p(f"Tabela {self.tab}. {legenda}", "Legenda", depois=160)
        else:
            self.p("", "TEXTOCORRIDO", depois=60)
            self.alt += 0.4

    def ficha(self, pares: list[tuple[str, str]], colunas: int = 2) -> None:
        """Quadro de identificação: rótulo e valor lado a lado, em `colunas` blocos por linha."""
        col = LARGURA // colunas
        rot_w = int(col * 0.30)
        val_w = col - rot_w
        grade = "".join(f'<w:gridCol w:w="{x}"/>' for _ in range(colunas) for x in (rot_w, val_w))
        linhas = []
        for ini in range(0, len(pares), colunas):
            bloco = pares[ini:ini + colunas]
            cels = []
            for i in range(colunas):
                rot, val = bloco[i] if i < len(bloco) else ("", "")
                cels.append(f'<w:tc><w:tcPr><w:tcW w:w="{rot_w}" w:type="dxa"/><w:shd w:val="clear" w:color="auto" w:fill="EEF6FB"/></w:tcPr>'
                            f'<w:p><w:pPr><w:pStyle w:val="TEXTOCORRIDO"/><w:shd w:val="clear" w:color="auto" w:fill="auto"/><w:spacing w:before="30" w:after="30"/></w:pPr>'
                            f'{_runs(rot, "<w:b/><w:bCs/><w:color w:val=" + chr(34) + NAVY + chr(34) + "/><w:sz w:val=" + chr(34) + "16" + chr(34) + "/>")}</w:p></w:tc>'
                            f'<w:tc><w:tcPr><w:tcW w:w="{val_w}" w:type="dxa"/></w:tcPr>'
                            f'<w:p><w:pPr><w:pStyle w:val="TEXTOCORRIDO"/><w:shd w:val="clear" w:color="auto" w:fill="auto"/><w:spacing w:before="30" w:after="30"/></w:pPr>'
                            f'{_runs(val, "<w:sz w:val=" + chr(34) + "16" + chr(34) + "/>")}</w:p></w:tc>')
            linhas.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>' + "".join(cels) + "</w:tr>")
            self._gasta(1.3 * max(1, max(math.ceil(len(v) / (val_w / 85)) for _, v in bloco)))
        self.x.append(f'<w:tbl><w:tblPr><w:tblW w:w="{LARGURA}" w:type="dxa"/><w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="{CINZA}"/>'
                      f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="{CINZA}"/><w:insideH w:val="single" w:sz="2" w:space="0" w:color="{CINZA}"/></w:tblBorders>'
                      f'<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="70" w:type="dxa"/><w:right w:w="70" w:type="dxa"/></w:tblCellMar></w:tblPr>'
                      f'<w:tblGrid>{grade}</w:tblGrid>{"".join(linhas)}</w:tbl>')
        self.p("", depois=60)

    def indicadores(self, itens: list[tuple[str, str, str]]) -> None:
        """Faixa de indicadores: rótulo, valor grande e uma nota curta, até 4 por linha."""
        for ini in range(0, len(itens), 4):
            grupo = itens[ini:ini + 4]
            n = len(grupo)
            larg = (LARGURA - 120 * (n - 1)) // n
            celulas = []
            rp = lambda cor, sz, neg=False: ("<w:b/><w:bCs/>" if neg else "") + f'<w:color w:val="{cor}"/><w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
            par = lambda txt, rpr, antes, depois: (f'<w:p><w:pPr><w:pStyle w:val="TEXTOCORRIDO"/><w:shd w:val="clear" w:color="auto" w:fill="auto"/>'
                                                   f'<w:spacing w:before="{antes}" w:after="{depois}"/></w:pPr>{_runs(txt, rpr)}</w:p>')
            for rot, val, nota in grupo:
                celulas.append(
                    f'<w:tc><w:tcPr><w:tcW w:w="{larg}" w:type="dxa"/><w:tcBorders><w:top w:val="single" w:sz="18" w:space="0" w:color="{CIANO}"/></w:tcBorders>'
                    f'<w:shd w:val="clear" w:color="auto" w:fill="F3F8FC"/></w:tcPr>'
                    + par(rot, rp("595959", 15), 60, 0) + par(val, rp(NAVY, 32, True), 0, 0) + par(nota, rp("595959", 15), 0, 60) + "</w:tc>")
                if len(celulas) < n * 2 - 1:
                    celulas.append('<w:tc><w:tcPr><w:tcW w:w="120" w:type="dxa"/></w:tcPr><w:p><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr></w:p></w:tc>')
            grade = "".join(f'<w:gridCol w:w="{larg if i % 2 == 0 else 120}"/>' for i in range(len(celulas)))
            self.x.append(f'<w:tbl><w:tblPr><w:tblW w:w="{LARGURA}" w:type="dxa"/><w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="100" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr>'
                          f'<w:tblGrid>{grade}</w:tblGrid><w:tr><w:trPr><w:cantSplit/></w:trPr>{"".join(celulas)}</w:tr></w:tbl>')
            self.p("", depois=80)
            self._gasta(3.2)

    def imagem(self, png: bytes, legenda: str, largura_cm: float = 16.0, proporcao: float = 0.5) -> None:
        self.imgs.append(png)
        rid = f"rIdImg{len(self.imgs)}"
        cx = int(largura_cm * 360000)
        cy = int(cx * proporcao)
        self._gasta(cy / 360000 / 0.52 + 1.5)       # ~0,52 cm por linha
        self.fig += 1
        self.x.append(
            '<w:p><w:pPr><w:pStyle w:val="TEXTOCORRIDO"/><w:keepNext/><w:spacing w:before="60" w:after="0"/><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
            f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{9000 + len(self.imgs)}" name="Gráfico {len(self.imgs)}" descr="{esc(legenda)}"/>'
            '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:nvPicPr><pic:cNvPr id="{9000 + len(self.imgs)}" name="grafico{len(self.imgs)}.png"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')
        self.p(f"Figura {self.fig}. {legenda}", "Legenda", jc="center", depois=160)

    def divisoria(self, numero: str, linha1: str, linha2: str = "") -> None:
        """Página divisória do modelo (fecha a seção anterior, se houver) e abre uma nova seção de conteúdo."""
        if self.nd:
            self.x.append(("SECAO",))
        self.nd += 1
        self.x.append(("DIVISORIA", numero, linha1, linha2))
        self.pagina += 1
        self.toc.append({"nivel": 0, "texto": f"{numero}. {linha1} {linha2}".strip(), "bm": None, "pagina": self.pagina})
        self.pagina += 1
        self.alt = 0


def _set(t: etree._Element, v: str) -> None:
    t.text = v
    if v.startswith(" ") or v.endswith(" "):
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")


def _troca_cabecalho(xml: bytes, titulo: str, rodape: str) -> bytes:
    raiz = etree.fromstring(xml)
    pulando = False
    for t in raiz.iter(f"{{{W}}}t"):
        tx = t.text or ""
        if tx.startswith("RELATÓRIO"):
            _set(t, titulo)
            pulando = True
        elif pulando and "GERÊNCIA" in tx:
            _set(t, f" | {rodape}")
            pulando = False
        elif pulando:
            _set(t, "")
    return etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True)


def montar(doc: Doc, titulo: str, subtitulo: str, cab_titulo: str, cab_rodape: str) -> bytes:
    zin = zipfile.ZipFile(MODELO)
    raiz = etree.fromstring(zin.read("word/document.xml"))
    corpo = raiz.find("w:body", NS)
    filhos = list(corpo)
    capa = filhos[0:5]
    divisoria_modelo = filhos[65]
    retangulo_modelo = filhos[61]       # retângulo azul de página inteira

    # capa: troca os textos nas caixas de título e subtítulo (cada texto aparece duas vezes: Choice e Fallback)
    for el in (filhos[0], filhos[3]):
        for t in el.iter(f"{{{W}}}t"):
            tx = t.text or ""
            if tx == "Digitar subtítulo do documento":
                _set(t, subtitulo)
            elif tx == "Digitar título do documento":
                _set(t, titulo)
            elif tx in ("CAPA ", "CAPA - ", "–", " "):
                _set(t, "")

    def serializa(el) -> str:
        return etree.tostring(el, encoding="unicode")

    def limpa_ids(s: str) -> str:
        return re.sub(r' w14:(paraId|textId)="[0-9A-Fa-f]+"', "", s)

    def divisoria(num: str, l1: str, l2: str, n: int) -> str:
        el = copy.deepcopy(divisoria_modelo)
        ts = list(el.iter(f"{{{W}}}t"))
        for i in (0, 2):
            _set(ts[i], num)
        for i in (1, 3):
            _set(ts[i], "")
        for i in (4, 6):
            _set(ts[i], l1)
        for i in (5, 7):
            _set(ts[i], l2)
        for k, d in enumerate(el.iter("{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr")):
            d.set("id", str(8000 + n * 10 + k))
        for k, a in enumerate(el.iter()):
            if a.get("{http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing}anchorId"):
                a.set("{http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing}anchorId", f"{0x6A000000 + n * 256 + k:08X}")
        WPD = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
        for r_ in [x for x in el if x.tag == f"{{{W}}}r"]:
            d_ = r_.find(f".//{{{WPD}}}docPr")
            if d_ is not None and (d_.get("name") == "Imagem 23" or d_.get("name", "").startswith("Conector")):
                # a imagem cinza de fundo e os filetes do modelo ficam de fora: o fundo é o retângulo azul (os filetes, na borda da página, geram página em branco)
                el.remove(r_)
        ret = copy.deepcopy(retangulo_modelo).find(f"{{{W}}}r")
        for tag, rel_ in (("positionH", "page"), ("positionV", "page")):
            for pos in ret.iter(f"{{{WPD}}}{tag}"):
                pos.set("relativeFrom", rel_)
                pos.find(f"{{{WPD}}}posOffset").text = "0"
        for ext in ret.iter(f"{{{WPD}}}extent"):
            ext.set("cx", "7560000"); ext.set("cy", "10692000")
        for ext in ret.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}ext"):
            ext.set("cx", "7560000"); ext.set("cy", "10692000")
        for d_ in ret.iter(f"{{{WPD}}}docPr"):
            d_.set("id", str(7000 + n))
        for a_ in ret.iter():
            if a_.get("{http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing}anchorId"):
                a_.set("{http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing}anchorId", f"{0x5A000000 + n:08X}")
        for lr in ret.iter(f"{{{W}}}lastRenderedPageBreak"):
            lr.getparent().remove(lr)
        rect_p = etree.fromstring(f'<w:p xmlns:w="{W}"><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr></w:p>')
        rect_p.append(ret)
        # título da divisória no sumário: texto minúsculo e branco sobre a página azul, com nível 1 de estrutura
        ppr = el.find("w:pPr", NS)
        rpr_el = ppr.find("w:rPr", NS)
        ppr.insert(list(ppr).index(rpr_el) if rpr_el is not None else len(ppr), etree.fromstring(f'<w:outlineLvl xmlns:w="{W}" w:val="0"/>'))
        ppr.append(etree.fromstring(sect().replace("<w:sectPr>", f'<w:sectPr xmlns:w="{W}">', 1)))
        bm = f"_Toc8{n:05d}"
        marcador = etree.fromstring(
            f'<w:r xmlns:w="{W}"><w:rPr><w:color w:val="00AAE6"/><w:sz w:val="2"/><w:szCs w:val="2"/></w:rPr><w:t>{esc(num + ". " + (l1 + " " + l2).strip())}</w:t></w:r>')
        ini = etree.fromstring(f'<w:bookmarkStart xmlns:w="{W}" w:id="{900 + n}" w:name="{bm}"/>')
        fim = etree.fromstring(f'<w:bookmarkEnd xmlns:w="{W}" w:id="{900 + n}"/>')
        pos = list(el).index(ppr) + 1
        el.insert(pos, fim)
        el.insert(pos, marcador)
        el.insert(pos, ini)
        return limpa_ids(serializa(rect_p) + serializa(el))

    # sumário: estimativa de páginas (capa = 1; sumário a partir da 2)
    entradas = doc.toc
    pag_sumario = max(1, math.ceil(sum(2.3 if e["nivel"] == 0 else 1.5 for e in entradas) / 56))
    deslocamento = 1 + pag_sumario       # a página 1 da estimativa do corpo é a primeira divisória
    corpo_xml: list[str] = []
    n_div = 0
    quebra_depois = False
    for item in doc.x:
        if isinstance(item, tuple) and item[0] == "DIVISORIA":
            n_div += 1
            corpo_xml.append(divisoria(item[1], item[2], item[3], n_div))
            for e in entradas:
                if e["nivel"] == 0 and e["bm"] is None:
                    e["bm"] = f"_Toc8{n_div:05d}"
                    break
            quebra_depois = False
        elif isinstance(item, tuple) and item[0] == "SECAO":
            corpo_xml.append(f"<w:p><w:pPr>{sect()}</w:pPr></w:p>")
        else:
            if quebra_depois:      # o conteúdo começa em página nova, depois da divisória
                item = re.sub(r'(<w:pStyle w:val="[^"]+"/>)', r'\1<w:pageBreakBefore/>', item, count=1)
                quebra_depois = False
            corpo_xml.append(item)

    def entrada_toc(e: dict, primeira: bool, ultima: bool) -> str:
        estilo = "Sumrio1" if e["nivel"] == 0 else "Sumrio2"
        pag = e["pagina"] + deslocamento
        ini = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \\h \\z \\u </w:instrText></w:r>'
               '<w:r><w:fldChar w:fldCharType="separate"/></w:r>') if primeira else ""
        fim = '<w:r><w:fldChar w:fldCharType="end"/></w:r>' if ultima else ""
        return (f'<w:p><w:pPr><w:pStyle w:val="{estilo}"/><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="9638"/></w:tabs></w:pPr>{ini}'
                f'<w:hyperlink w:anchor="{e["bm"]}" w:history="1"><w:r><w:t xml:space="preserve">{esc(e["texto"])}</w:t></w:r><w:r><w:tab/></w:r>'
                f'<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGEREF {e["bm"]} \\h </w:instrText></w:r>'
                f'<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>{pag}</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:hyperlink>{fim}</w:p>')

    toc_xml = "".join(entrada_toc(e, i == 0, i == len(entradas) - 1) for i, e in enumerate(entradas))
    sumario = ('<w:p><w:pPr><w:pStyle w:val="CabealhodoSumrio"/></w:pPr><w:r><w:rPr><w:b/><w:bCs w:val="0"/></w:rPr><w:t>SUMÁRIO</w:t></w:r></w:p>'
               + toc_xml + f"<w:p><w:pPr>{sect(2, False, 'continuous')}</w:pPr></w:p>")

    abre = re.match(r"<\?xml[^>]*\?>\s*(<w:document[^>]*>)", etree.tostring(raiz, xml_declaration=True, encoding="UTF-8", standalone=True).decode())
    cabeca = abre.group(1)
    final_sect = sect()
    doc_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + cabeca + "<w:body>" + "".join(limpa_ids(serializa(e)) for e in capa)
               + sumario + "".join(corpo_xml) + final_sect + "</w:body></w:document>")
    etree.fromstring(doc_xml.encode("utf-8"))      # garante XML bem formado antes de gravar

    # pacote: sem os gráficos e planilhas embutidos do modelo; com as imagens novas
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        for info in zin.infolist():
            nome = info.filename
            if nome.startswith(("word/charts/", "word/embeddings/")) or info.is_dir():
                continue
            dados = zin.read(nome)
            if nome == "word/document.xml":
                dados = doc_xml.encode("utf-8")
            elif nome == "[Content_Types].xml":
                s = dados.decode("utf-8")
                s = s.replace("wordprocessingml.template.main+xml", "wordprocessingml.document.main+xml")
                s = re.sub(r'<Override PartName="/word/(charts|embeddings)/[^"]*"[^>]*/>', "", s)
                dados = s.encode("utf-8")
            elif nome == "word/_rels/document.xml.rels":
                s = dados.decode("utf-8")
                s = re.sub(r'<Relationship [^>]*Target="(charts|embeddings)/[^"]*"[^>]*/>', "", s)
                extra = "".join(f'<Relationship Id="rIdImg{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/grafico{i + 1}.png"/>'
                                for i in range(len(doc.imgs)))
                dados = s.replace("</Relationships>", extra + "</Relationships>").encode("utf-8")
            elif nome in ("word/header2.xml", "word/header3.xml", "word/header4.xml"):
                dados = _troca_cabecalho(dados, cab_titulo, cab_rodape)
            elif nome == "word/settings.xml":
                s = dados.decode("utf-8")
                if "<w:updateFields" not in s:
                    s = re.sub(r"(<w:(?:hdrShapeDefaults|footnotePr|endnotePr|compat)[ >/])", r'<w:updateFields w:val="true"/>\1', s, count=1)
                dados = s.encode("utf-8")
            z.writestr(nome, dados)
        for i, png in enumerate(doc.imgs):
            z.writestr(f"word/media/grafico{i + 1}.png", png)
    return saida.getvalue()
