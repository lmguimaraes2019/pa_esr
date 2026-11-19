import React, { useEffect, useState } from "react";
import { api, fmt } from "./api.js";

// Quadro à parte: projetos da Diretoria onde o gestor lançou viagens, eventos ou headcount.
// Os valores daqui não entram nos totais dos projetos do próprio gestor.
export default function OutrosProjetos({ abrir }) {
  const [d, setD] = useState(null);
  useEffect(() => { api("/outros-projetos").then(setD).catch(() => setD({ projetos: [], total: 0 })); }, []);
  if (!d || !d.projetos.length) return null;
  return (
    <section className="cartao outros" style={{ borderLeft: "4px solid #8a94a6" }}>
      <h3>Outros projetos onde você lançou despesas</h3>
      <p className="mudo" style={{ marginTop: 0 }}>Projetos da Diretoria Adjunta ou da Diretoria Executiva. Você pode lançar viagens, eventos e headcount neles,
        mas o orçamento é da Diretoria: estes valores <strong>não entram</strong> nos totais dos seus projetos acima.</p>
      <div className="rolagem">
        <table className="tab">
          <thead><tr><th>Orçamento</th><th>Projeto</th><th>Gerência</th><th className="n">Viagens</th><th className="n">Eventos</th><th className="n">Headcount</th><th className="n">Lançado por você em 2027</th><th className="n" title="Informativo: execução do projeto inteiro">Realizado 2026 do projeto</th></tr></thead>
          <tbody>{d.projetos.map((p) => (
            <tr key={p.orcamento} className={abrir ? "proj" : ""} onClick={abrir ? () => abrir(p.orcamento) : undefined}>
              <td>{p.orcamento}</td><td>{p.projeto}</td><td>{p.gerencia}</td>
              <td className="n">{p.viagens_n ? fmt(p.viagens) : <span className="mudo">-</span>}</td>
              <td className="n">{p.eventos_n ? fmt(p.eventos) : <span className="mudo">-</span>}</td>
              <td className="n">{p.posicoes_n ? fmt(p.headcount) : <span className="mudo">-</span>}</td>
              <td className="n"><strong>{fmt(p.total)}</strong></td>
              <td className="n mudo">{fmt(p.realizado_2026)}</td>
            </tr>))}</tbody>
          <tfoot><tr><td colSpan="6">Total lançado por você nesses projetos</td><td className="n">{fmt(d.total)}</td><td /></tr></tfoot>
        </table>
      </div>
    </section>
  );
}
