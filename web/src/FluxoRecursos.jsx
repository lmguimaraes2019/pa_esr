import React, { useEffect, useState } from "react";
import { api, fmt } from "./api.js";

const CORES = ["#1f6feb", "#e8710a", "#2f9e6f", "#8e5bd4", "#c2417a", "#0b9aa8", "#a68a1f", "#6b7a90"];
const W = 1040, PAD = 8, GAP = 10, NODE_W = 14, COL = [0, 0.5, 1], ALTURA = 380;

// Layout simples de Sankey de 3 colunas: receitas -> origem dos recursos -> custos por gerência
function monta(d) {
  const cols = [[], [], []];
  const nos = {};
  const no = (col, nome) => { const k = col + "|" + nome; if (!nos[k]) { nos[k] = { col, nome, entra: 0, sai: 0, k }; cols[col].push(nos[k]); } return nos[k]; };
  const ligs = [];
  d.entra.forEach((l) => { const a = no(0, l.de), b = no(1, l.para); a.sai += l.valor; b.entra += l.valor; ligs.push({ a, b, v: l.valor }); });
  d.sai.forEach((l) => { const a = no(1, l.de), b = no(2, l.para); a.sai += l.valor; b.entra += l.valor; ligs.push({ a, b, v: l.valor }); });
  const H = Math.max(ALTURA, Math.max(...cols.map((c) => c.length)) * 46);
  const esc = Math.min(...cols.map((c) => (H - 2 * PAD - GAP * Math.max(c.length - 1, 0)) / Math.max(c.reduce((t, n) => t + Math.max(n.entra, n.sai), 0), 1)));
  let fundo = 0;
  cols.forEach((c) => { c.sort((x, y) => Math.max(y.entra, y.sai) - Math.max(x.entra, x.sai)); let y = PAD;
    c.forEach((n) => { n.h = Math.max(Math.max(n.entra, n.sai) * esc, 28); n.y = y; n.yIn = n.y; n.yOut = n.y; y += n.h + GAP; }); fundo = Math.max(fundo, y); });
  cols.forEach((c, i) => c.forEach((n) => { n.x = [0, 1, 2][i] * ((W - 2 * 190 - NODE_W) / 2) + 190; }));
  cols[1].forEach((n, i) => { n.cor = CORES[i % CORES.length]; });
  ligs.sort((p, q) => p.a.y - q.a.y || p.b.y - q.b.y);
  ligs.forEach((l) => {
    l.w = Math.max(l.v * esc, 1);
    l.y0 = l.a.yOut + l.w / 2; l.a.yOut += l.w;
    l.y1 = l.b.yIn + l.w / 2; l.b.yIn += l.w;
    l.cor = (l.a.col === 1 ? l.a : l.b).cor;
  });
  cols[0].forEach((n) => { const l = ligs.find((x) => x.a === n); n.cor = l ? l.b.cor : undefined; cols[2].forEach(() => {}); });
  cols[2].forEach((n) => { const l = ligs.find((x) => x.b === n); n.cor = l ? l.a.cor : undefined; });
  return { cols, ligs, alt: fundo + PAD };
}

export default function FluxoRecursos() {
  const [d, setD] = useState(null);
  const [foco, setFoco] = useState(null);
  useEffect(() => { api("/fluxo").then(setD).catch(() => setD({ entra: [], sai: [], origens: [], total_receita: 0, total_custo: 0 })); }, []);
  if (!d) return null;
  if (!d.entra.length && !d.sai.length) return null;
  const { cols, ligs, alt } = monta(d);
  const ativo = (l) => !foco || l.a.k === foco || l.b.k === foco;
  return (
    <section className="cartao fluxo">
      <div className="cab"><div><h3 style={{ margin: 0 }}>Fluxo do dinheiro em 2027</h3>
        <p className="mudo">De onde vem o recurso, em qual origem ele entra e para onde vai como custo. Passe o mouse ou clique numa origem para destacar o caminho.</p></div>
        <div className="ic-total"><span>Receita x custo</span><strong>{fmt(d.total_receita)} / {fmt(d.total_custo)}</strong></div></div>
      <div className="rolagem">
        <svg viewBox={`0 0 ${W} ${alt}`} role="img" aria-label="Fluxo do dinheiro: receitas, origem dos recursos e custos" style={{ width: "100%", minWidth: 760, height: "auto" }}>
          <g>{ligs.map((l, i) => (
            <path key={i} d={`M${l.a.x + NODE_W},${l.y0} C${l.a.x + NODE_W + 110},${l.y0} ${l.b.x - 110},${l.y1} ${l.b.x},${l.y1}`} fill="none" stroke={l.cor}
              strokeWidth={l.w} strokeOpacity={ativo(l) ? 0.38 : 0.08}><title>{l.a.nome} para {l.b.nome}: {fmt(l.v)}</title></path>))}</g>
          {cols.map((c, ci) => c.map((n) => (
            <g key={n.k} onMouseEnter={() => setFoco(n.k)} onMouseLeave={() => setFoco(null)} onClick={() => setFoco(foco === n.k ? null : n.k)} style={{ cursor: "pointer" }}>
              <rect x={n.x} y={n.y} width={NODE_W} height={n.h} rx="3" fill={n.cor || "#44546a"} />
              <text x={ci === 2 ? n.x - 8 : n.x + NODE_W + 8} y={n.y + n.h / 2 - 2} textAnchor={ci === 2 ? "end" : "start"} fontSize="12" fontWeight="600" fill="currentColor">{n.nome}</text>
              <text x={ci === 2 ? n.x - 8 : n.x + NODE_W + 8} y={n.y + n.h / 2 + 12} textAnchor={ci === 2 ? "end" : "start"} fontSize="11" fill="currentColor" opacity="0.7">{fmt(Math.max(n.entra, n.sai))}</text>
            </g>)))}
          {["Receitas", "Origem dos recursos", "Custos por gerência"].map((t, i) => <text key={t} x={cols[i][0] ? cols[i][0].x + (i === 2 ? NODE_W : 0) : 0} y={alt - 2} fontSize="11" fill="currentColor" opacity="0.55" textAnchor={i === 2 ? "end" : "start"} style={{ display: "none" }}>{t}</text>)}
        </svg>
      </div>
      <div className="rolagem"><table className="tab">
        <thead><tr><th>Origem do recurso</th><th className="n">Receita lançada</th><th className="n">Custo planejado</th><th className="n">Saldo (receita menos custo)</th></tr></thead>
        <tbody>{d.origens.map((o) => <tr key={o.origem}><td>{o.origem}</td><td className="n">{fmt(o.receita)}</td><td className="n">{fmt(o.custo)}</td>
          <td className="n" style={{ color: o.saldo < 0 ? "#b42318" : undefined }}>{fmt(o.saldo)}</td></tr>)}</tbody>
        <tfoot><tr><td>Total</td><td className="n">{fmt(d.total_receita)}</td><td className="n">{fmt(d.total_custo)}</td><td className="n">{fmt(d.total_receita - d.total_custo)}</td></tr></tfoot>
      </table></div>
      <p className="mudo">Custo sem receita lançada aparece como "Fomento RNP (conta única)" quando a origem é de fomento, ou "Sem receita lançada" nos demais casos. Considera só os seus projetos, sem contingenciados.</p>
    </section>
  );
}
