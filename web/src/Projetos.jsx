import React, { useEffect, useState } from "react";
import { api, fmt } from "./api.js";
import { Delta, pct, Selo } from "./ui.jsx";

export default function Projetos({ abrir }) {
  const [ps, setPs] = useState(null);
  const [erro, setErro] = useState("");
  useEffect(() => { api("/projetos").then(setPs).catch((e) => setErro(e.message)); }, []);
  if (erro) return <p className="erro">{erro}</p>;
  if (!ps) return <p>Carregando…</p>;
  if (!ps.length) return <p className="mudo">Nenhum projeto associado ao seu usuário.</p>;
  const soma = (k) => ps.reduce((a, p) => a + p[k], 0);
  return (
    <>
      <h2>Orçamento 2027 por projeto</h2>
      <p className="mudo">Abra um projeto para ver o que foi aprovado e executado em 2026 e ajustar o plano de 2027.</p>
      <table className="tab clic">
        <thead>
          <tr className="grupos"><th colSpan={4} style={{ background: "#fff" }} /><th colSpan={3} className="g26"><Selo ano={2026} /></th><th colSpan={2} className="g27"><Selo ano={2027} /></th></tr>
          <tr><th>Orçamento</th><th>Projeto</th><th>Origem</th><th>Gerente</th><th className="n g26">Aprovado</th><th className="n g26">Executado</th><th className="n g26">% exec.</th><th className="n g27">Plano 2027</th><th className="n g27">Δ vs aprovado</th></tr>
        </thead>
        <tbody>{ps.map((p) => (
          <tr key={p.orcamento} onClick={() => abrir(p.orcamento)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && abrir(p.orcamento)}>
            <td>{p.orcamento}</td>
            <td>{p.descricao} {p.pendencias.length > 0 && <span className="tag aviso">sem Nº do Projeto</span>}</td>
            <td>{p.origem}</td><td>{p.gerente}</td>
            <td className="n">{fmt(p.total_2026)}</td><td className="n">{fmt(p.realizado_2026 + p.empenhado_2026)}</td><td className="n">{pct(p.realizado_2026 + p.empenhado_2026, p.total_2026)}</td>
            <td className="n"><strong>{fmt(p.total_2027)}</strong></td><td className="n"><Delta de={p.total_2026} para={p.total_2027} /></td>
          </tr>))}</tbody>
        <tfoot><tr><td colSpan={4}>Total</td><td className="n">{fmt(soma("total_2026"))}</td><td className="n">{fmt(soma("realizado_2026") + soma("empenhado_2026"))}</td><td className="n">{pct(soma("realizado_2026") + soma("empenhado_2026"), soma("total_2026"))}</td><td className="n">{fmt(soma("total_2027"))}</td><td className="n"><Delta de={soma("total_2026")} para={soma("total_2027")} /></td></tr></tfoot>
      </table>
    </>
  );
}
