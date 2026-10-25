import React, { useEffect, useState } from "react";
import { api, fmt } from "./api.js";

export default function Projetos({ abrir }) {
  const [ps, setPs] = useState(null);
  const [erro, setErro] = useState("");
  useEffect(() => { api("/projetos").then(setPs).catch((e) => setErro(e.message)); }, []);
  if (erro) return <p className="erro">{erro}</p>;
  if (!ps) return <p>Carregando…</p>;
  if (!ps.length) return <p className="mudo">Nenhum projeto associado ao seu usuário.</p>;
  return (
    <>
      <h2>Projetos</h2>
      <table className="tab clic">
        <thead><tr><th>Orçamento</th><th>Projeto</th><th>Origem</th><th>Gerente</th><th className="n">2026 aprovado</th><th className="n">2027 plano</th><th className="n">Δ</th></tr></thead>
        <tbody>{ps.map((p) => (
          <tr key={p.orcamento} onClick={() => abrir(p.orcamento)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && abrir(p.orcamento)}>
            <td>{p.orcamento}</td>
            <td>{p.descricao} {p.pendencias.length > 0 && <span className="tag aviso">sem Nº do Projeto</span>}</td>
            <td>{p.origem}</td><td>{p.gerente}</td>
            <td className="n">{fmt(p.total_2026)}</td><td className="n">{fmt(p.total_2027)}</td>
            <td className={"n " + (p.total_2027 - p.total_2026 > 0.005 ? "up" : p.total_2027 - p.total_2026 < -0.005 ? "down" : "")}>{fmt(p.total_2027 - p.total_2026)}</td>
          </tr>))}</tbody>
        <tfoot><tr><td colSpan={4}>Total</td><td className="n">{fmt(ps.reduce((a, p) => a + p.total_2026, 0))}</td><td className="n">{fmt(ps.reduce((a, p) => a + p.total_2027, 0))}</td><td /></tr></tfoot>
      </table>
    </>
  );
}
