import React, { useEffect, useState } from "react";
import { api, fmt } from "./api.js";
import { rotuloEst } from "./Entregas.jsx";

/** Botão e painel "Replicar para 2027": leva o plano 2027 para um orçamento novo, com outro nome e outra origem de recurso. */
export function ReplicarProjeto({ p, irProjeto }) {
  const [aberto, setAberto] = useState(false);
  const [pre, setPre] = useState(null);
  const [listas, setListas] = useState(null);
  const [nome, setNome] = useState("");
  const [origem, setOrigem] = useState("");
  const [erro, setErro] = useState("");
  const [fazendo, setFazendo] = useState(false);
  useEffect(() => { setAberto(false); }, [p.orcamento]);
  const abrir = async () => {
    setErro("");
    try {
      const [a, l] = await Promise.all([api(`/projetos/${p.orcamento}/replicar`), api("/listas")]);
      setPre(a); setListas(l); setNome(p.descricao); setOrigem(p.origem); setAberto(true);
    } catch (e) { setErro(e.message); }
  };
  const confirmar = async () => {
    setErro(""); setFazendo(true);
    try { const r = await api(`/projetos/${p.orcamento}/replicar`, { method: "POST", body: { descricao: nome, origem } }); irProjeto(r.orcamento); }
    catch (e) { setErro(e.message); setFazendo(false); }
  };
  if (p.novo || p.replicado_para) return null;
  const c = pre?.contagem;
  const itens = c ? [[c.linhas, "linha(s) do plano"], [c.viagens, "viagem(ns)"], [c.eventos, "evento(s)"], [c.headcount, "posição(ões) de headcount"], [c.receitas, "receita(s)"], [c.entregas, "entrega(s)"], [c.vinculos, "vínculo(s) estratégico(s)"]].filter(([n]) => n > 0) : [];
  return (
    <>
      {!aberto && <button className="replicar-btn" onClick={abrir} title="Cria um orçamento novo para 2027 com o plano deste projeto">Replicar para 2027</button>}
      {erro && !aberto && <span className="erro" role="alert">{erro}</span>}
      {aberto && (
        <section className="cartao replicar">
          <h3>Replicar «{p.descricao}» para 2027</h3>
          <p className="mudo">Um orçamento novo será criado com o plano de 2027 deste projeto. O plano sai daqui: este projeto continua com o 2026 (aprovado e executado) e fica marcado como migrado.</p>
          <div className="grade">
            <label>Nome do novo orçamento<input value={nome} onChange={(e) => setNome(e.target.value)} maxLength={200} /></label>
            <label>Origem de recursos do novo orçamento<select value={origem} onChange={(e) => setOrigem(e.target.value)}>{listas.origens.map((o) => <option key={o}>{o}</option>)}</select></label>
          </div>
          <div className="repl-leva">
            <strong>Vai para o novo orçamento ({fmt(c.valor)} em 2027)</strong>
            {itens.length ? <ul>{itens.map(([n, t]) => <li key={t}><b>{n}</b> {t}</li>)}</ul> : <p className="mudo">Este projeto ainda não tem nada lançado em 2027.</p>}
            <p className="mudo">Ficam aqui: o orçamento aprovado e o executado de 2026, o Nº do Projeto e o que você registrou como passado.</p>
          </div>
          {erro && <p className="erro" role="alert">{erro}</p>}
          <div className="acoes"><button className="primario" disabled={fazendo || nome.trim().length < 3} onClick={confirmar}>{fazendo ? "Replicando…" : "Replicar para 2027"}</button><button onClick={() => setAberto(false)} disabled={fazendo}>Cancelar</button></div>
        </section>)}
    </>
  );
}

/** Faixa que aparece no projeto de origem (migrado) e no projeto criado pela replicação. */
export function FaixaMigracao({ p, irProjeto }) {
  if (p.replicado_para) {
    return (
      <div className="faixa-migrado" role="status">
        <strong>Migrado para 2027</strong> em outro orçamento: <button className="link" onClick={() => irProjeto(p.replicado_para)}>{p.replicado_nome}</button>
        {" "}<span className="mudo">({p.replicado_para} | origem de recursos: {p.replicado_origem}{p.replicado_por && ` | por ${p.replicado_por}`})</span>
      </div>);
  }
  if (p.replicado_de) {
    return <div className="faixa-migrado de" role="status">Replicado do orçamento <button className="link" onClick={() => irProjeto(p.replicado_de)}>{p.replicado_de}</button> (plano de 2027 trazido de lá).</div>;
  }
  return null;
}

export { rotuloEst };
