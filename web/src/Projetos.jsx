import React, { useEffect, useState } from "react";
import { api, fmt } from "./api.js";
import { Delta, pct, Selo } from "./ui.jsx";

function NovoOrcamento({ listas, onCriar, onFechar }) {
  const [f, setF] = useState({ tipo: "despesa", descricao: "", origem: "", gerente: "" });
  const [erro, setErro] = useState("");
  const salvar = async (e) => {
    e.preventDefault(); setErro("");
    try { await onCriar(f); } catch (x) { setErro(x.message); }
  };
  return (
    <form className="cartao" onSubmit={salvar}>
      <h3>Novo orçamento 2027</h3>
      <div className="passos" role="tablist" style={{ marginTop: 0 }}>
        {[["despesa", "Orçamento de despesa"], ["receita", "Orçamento de receita"]].map(([k, t]) => <button type="button" key={k} role="tab" aria-selected={f.tipo === k} className={f.tipo === k ? "on" : ""} onClick={() => setF({ ...f, tipo: k })}>{t}</button>)}</div>
      <p className="mudo">{f.tipo === "receita" ? "O total deste orçamento entra como receita e gera resultado positivo. Ele não conta como despesa e não vai no Template de despesas do PMO." : "Orçamento de despesa: segue a jornada completa, com passado 2026, plano 2027, viagens, eventos e headcount."}</p>
      <p className="mudo">Não precisa de número agora: o orçamento nasce marcado como <span className="tag ok">novo</span>. O Nº do Projeto, exigido na exportação ao PMO, pode ser informado depois pelo administrador.</p>
      <div className="grade">
        <label>Nome do orçamento<input value={f.descricao} onChange={(e) => setF({ ...f, descricao: e.target.value })} required minLength={3} placeholder="ex.: DSS-ESR-ASSOCIACAO-NOVO PROGRAMA" /></label>
        <label>Origem de recursos<select value={f.origem} onChange={(e) => setF({ ...f, origem: e.target.value })} required>
          <option value="">Selecione…</option>{listas.origens.map((o) => <option key={o}>{o}</option>)}</select></label>
        <label>Gerente do projeto<select value={f.gerente} onChange={(e) => setF({ ...f, gerente: e.target.value })} required>
          <option value="">Selecione…</option>{listas.gerentes.map((g) => <option key={g}>{g}</option>)}</select></label>
      </div>
      {erro && <p className="erro" role="alert">{erro}</p>}
      <div className="acoes"><button className="primario">Criar orçamento</button><button type="button" onClick={onFechar}>Cancelar</button></div>
    </form>
  );
}

export default function Projetos({ abrir }) {
  const [ps, setPs] = useState(null);
  const [erro, setErro] = useState("");
  const [novo, setNovo] = useState(false);
  const [listas, setListas] = useState(null);
  useEffect(() => { api("/projetos").then(setPs).catch((e) => setErro(e.message)); api("/listas").then(setListas).catch(() => {}); }, []);
  if (erro) return <p className="erro">{erro}</p>;
  if (!ps) return <p>Carregando…</p>;
  const soma = (k) => ps.filter((p) => p.tipo !== "receita").reduce((a, p) => a + p[k], 0);
  const somaT = (k) => ps.reduce((a, p) => a + p[k], 0);
  return (
    <>
      <div className="cab"><div><h2>PA 2027 por projeto</h2>
        <p className="mudo">Abra um projeto para ver o que foi aprovado e executado em 2026 e ajustar o plano de 2027. As receitas lançadas na página Receitas entram no projeto de destino.</p></div>
        {listas && <button className="destaque" onClick={() => setNovo(true)}>+ Novo orçamento</button>}</div>
      {novo && listas && <NovoOrcamento listas={listas} onFechar={() => setNovo(false)} onCriar={async (b) => { const r = await api("/projetos", { method: "POST", body: b }); abrir(r.orcamento); }} />}
      {!ps.length && <p className="mudo">Nenhum projeto associado ao seu usuário. Crie um novo orçamento acima.</p>}
      <div className="rolagem"><table className="tab clic">
        <thead>
          <tr className="grupos"><th colSpan={4} style={{ background: "#fff" }} /><th colSpan={3} className="g26"><Selo ano={2026} /></th><th colSpan={4} className="g27"><Selo ano={2027} /></th></tr>
          <tr><th>Orçamento</th><th>Projeto</th><th>Origem</th><th>Gerente</th><th className="n g26">Aprovado</th><th className="n g26" title="Valor realizado em 2026, sem o empenhado">Executado</th><th className="n g26" title="Executado dividido pelo aprovado, sem o empenhado">% exec.</th><th className="n g27">Plano 2027</th><th className="n g27">Δ vs aprovado</th><th className="n g27" title="Receitas lançadas no projeto (previsão, transferências intercompany e orçamentos de receita)">Receitas 2027</th><th className="n g27" title="Receitas menos despesas do plano 2027">Resultado</th></tr>
        </thead>
        <tbody>{ps.map((p) => (
          <tr key={p.orcamento} onClick={() => abrir(p.orcamento)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && abrir(p.orcamento)}>
            <td>{p.novo ? <span className="tag ok">novo</span> : p.orcamento}</td>
            <td>{p.descricao} {p.tipo === "receita" && <span className="tag ok">receita</span>} {p.pendencias.length > 0 && <span className="tag aviso">sem Nº do Projeto</span>}</td>
            <td>{p.origem}</td><td>{p.gerente}</td>
            <td className="n">{fmt(p.total_2026)}</td><td className="n">{fmt(p.realizado_2026)}</td><td className="n">{pct(p.realizado_2026, p.total_2026)}</td>
            {p.tipo === "receita"
              ? <><td className="n mudo">-</td><td className="n mudo">receita</td></>
              : <><td className="n"><strong>{fmt(p.total_2027)}</strong></td><td className="n"><Delta de={p.total_2026} para={p.total_2027} /></td></>}
            <td className="n">{p.receitas_2027 ? <span className="res-pos">+{fmt(p.receitas_2027)}</span> : <span className="mudo">-</span>}</td>
            <td className="n"><strong className={p.resultado_2027 > 0 ? "res-pos" : p.resultado_2027 < 0 ? "res-neg" : ""}>{fmt(p.resultado_2027)}</strong></td>
          </tr>))}</tbody>
        <tfoot><tr><td colSpan={4}>Total</td><td className="n">{fmt(soma("total_2026"))}</td><td className="n">{fmt(soma("realizado_2026"))}</td><td className="n">{pct(soma("realizado_2026"), soma("total_2026"))}</td><td className="n">{fmt(soma("total_2027"))}</td><td className="n"><Delta de={soma("total_2026")} para={soma("total_2027")} /></td><td className="n"><span className="res-pos">+{fmt(somaT("receitas_2027"))}</span></td><td className="n"><strong className={somaT("resultado_2027") < 0 ? "res-neg" : "res-pos"}>{fmt(somaT("resultado_2027"))}</strong></td></tr></tfoot>
      </table></div>
    </>
  );
}
