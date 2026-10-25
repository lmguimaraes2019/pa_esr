"""Fase 0: extrai a tabela mestra e o orçado 2026 das planilhas da ESR.

Uso: python3 -I scripts/extract_master.py
Saídas em data/: protheus_2026.csv, master_*.csv, orcado_2026.csv, relatorio_resumo.json
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd

UP = Path("/mnt/user-data/uploads")
OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)

F_PROTHEUS = UP / "2026_-_Base_Protheus_-_ESR.xlsx"
F_TEMPLATE = UP / "Template_Planejamento_Anual_-_2027.xlsx"
F_PA = UP / "projetos_pa_2026.xlsx"

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def load_protheus() -> pd.DataFrame:
    raw = pd.read_excel(F_PROTHEUS, sheet_name="BASE ESR", header=None, dtype=object)
    hdr = next(i for i in range(10) if "Tipo de Lançamento" in [str(v) for v in raw.iloc[i]])
    df = raw.iloc[hdr + 1:].copy()
    df.columns = [str(c) for c in raw.iloc[hdr]]
    df = df.loc[:, [c for c in df.columns if c != "nan"]].reset_index(drop=True)
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce")
    df["Mês"] = df["Mês"].astype(str).str.strip().str.lower().str[:3]
    df["Ano"] = pd.to_numeric(df["Ano"], errors="coerce")
    # chaves como texto simples; vazio vira "" para o groupby não descartar linhas
    for c in ["Nº do Orçamento", "Nº do Projeto", "Conta Contábil", "Centro de Custo"]:
        df[c] = df[c].where(df[c].notna(), "").astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    # Nº do Projeto ausente nos orçamentos novos: tenta recuperar do início da descrição ("2882 - ...")
    from_desc = df["Descrição do Projeto"].astype(str).str.extract(r"^\s*0*(\d+)\s*-", expand=False).fillna("")
    df["Nº do Projeto"] = df["Nº do Projeto"].where(df["Nº do Projeto"] != "", from_desc)
    for c in ["Descrição do Projeto", "Origem de Recurso", "Gerente do Projeto", "EDT", "Tarefa",
              "Grupo de Despesa", "Descrição Conta Contábil"]:
        df[c] = df[c].where(df[c].notna(), "").astype(str).str.strip()
    return df


def split_code(txt):
    """'01.01-PRODUCAO ...' -> ('01.01', 'PRODUCAO ...')"""
    if txt is None or (isinstance(txt, float) and pd.isna(txt)):
        return None, None
    m = re.match(r"^\s*([0-9OoXx.,]+)\s*-\s*(.*)$", str(txt))
    return (m.group(1), m.group(2).strip()) if m else (None, str(txt).strip())


def main() -> int:
    df = load_protheus()
    df.to_csv(OUT / "protheus_2026.csv", index=False)

    # ---- projetos
    proj = (df.groupby(["Nº do Orçamento", "Nº do Projeto", "Centro de Custo", "Origem de Recurso",
                        "Gerente do Projeto"], dropna=False)
              .agg(descricoes=("Descrição do Projeto", lambda s: sorted(set(map(str, s)))),
                   linhas=("Valor", "size")).reset_index())
    proj.to_csv(OUT / "master_projetos.csv", index=False)

    # ---- tarefas (EDT + tarefa)
    t = df[["Nº do Projeto", "EDT", "Tarefa"]].drop_duplicates().copy()
    t["edt_cod"], t["edt_nome"] = zip(*t["EDT"].map(split_code))
    t["tarefa_cod"], t["tarefa_nome"] = zip(*t["Tarefa"].map(split_code))
    t.to_csv(OUT / "master_tarefas.csv", index=False)

    # ---- contas contábeis (Protheus + lista oculta do template)
    ct = pd.read_excel(F_TEMPLATE, sheet_name="Conta Contábil", dtype=object)
    ct = ct.iloc[:, :4]
    ct.columns = ["conta", "descricao_conta", "descricao_grupo", "grupo_despesa"]
    ct["conta"] = ct["conta"].astype(str).str.replace(r"\.0$", "", regex=True)
    ct = ct.dropna(subset=["conta"])
    ct.to_csv(OUT / "master_contas_template.csv", index=False)

    contas_prot = df[["Conta Contábil", "Descrição Conta Contábil", "Grupo de Despesa"]].drop_duplicates()
    contas_prot.to_csv(OUT / "master_contas_protheus.csv", index=False)

    # ---- gerentes / origens do template
    g = pd.read_excel(F_TEMPLATE, sheet_name="Diretoria, Gerente, Origem", dtype=object, header=None)
    g.to_csv(OUT / "master_template_listas_brutas.csv", index=False)

    # ---- orçado 2026 no grão do template
    orc = df[df["Tipo de Lançamento"] == "Orçado"].copy()
    orc["mes_idx"] = orc["Mês"].map({m: i + 1 for i, m in enumerate(MESES)})
    grp = (orc.groupby(["Nº do Orçamento", "Nº do Projeto", "Descrição do Projeto", "Origem de Recurso",
                        "Gerente do Projeto", "EDT", "Tarefa", "Grupo de Despesa", "Conta Contábil",
                        "Descrição Conta Contábil", "Mês"], dropna=False)["Valor"].sum().reset_index())
    pv = grp.pivot_table(index=["Nº do Orçamento", "Nº do Projeto", "Descrição do Projeto",
                                "Origem de Recurso", "Gerente do Projeto", "EDT", "Tarefa",
                                "Grupo de Despesa", "Conta Contábil", "Descrição Conta Contábil"],
                         columns="Mês", values="Valor", aggfunc="sum", fill_value=0).reset_index()
    for m in MESES:
        if m not in pv.columns:
            pv[m] = 0.0
    pv["total"] = pv[MESES].sum(axis=1)
    pv.to_csv(OUT / "orcado_2026.csv", index=False)

    # ---- resumo e conferências
    res = {}
    res["linhas_protheus"] = int(len(df))
    res["linhas_por_tipo"] = df["Tipo de Lançamento"].value_counts().to_dict()
    res["soma_por_tipo"] = df.groupby("Tipo de Lançamento")["Valor"].sum().round(2).to_dict()
    res["anos"] = df["Ano"].value_counts(dropna=False).to_dict()
    orc_proj = orc.groupby(["Nº do Orçamento", "Nº do Projeto", "Origem de Recurso"])["Valor"].sum().round(2)
    res["orcado_por_projeto"] = {f"orc {a} / proj {b or '(vazio)'} / {c}": float(v) for (a, b, c), v in orc_proj.items()}
    res["orcado_total_conferencia"] = round(float(orc["Valor"].sum()), 2)
    res["orcado_total_soma_projetos"] = round(float(orc_proj.sum()), 2)

    # aprovado (projetos_pa, aba consolidado_as-is)
    pa = pd.read_excel(F_PA, sheet_name="consolidado_as-is", header=None, dtype=object)
    hdr = next(i for i in range(10) if "ID Projeto" in [str(v) for v in pa.iloc[i]])
    pa2 = pa.iloc[hdr + 1:].copy()
    pa2.columns = [str(c) for c in pa.iloc[hdr]]
    pa2 = pa2[pd.to_numeric(pa2["Valor Final Aprovado"], errors="coerce").notna()]
    pa2 = pa2[pa2["Projeto"].notna()]
    pa2.to_csv(OUT / "aprovado_pa_2026.csv", index=False)

    # contas do Protheus que não existem na lista do template
    set_t = set(ct["conta"])
    faltam = sorted(set(df["Conta Contábil"].dropna()) - set_t - {"nan"})
    res["contas_protheus_fora_do_template"] = faltam

    # tarefas com código irregular
    irregulares = t[~t["tarefa_cod"].fillna("").str.match(r"^\d{2}\.\d{2}$|^\d{1,2}\.\d{1,2}$")]
    res["tarefas_codigo_irregular"] = irregulares[["Nº do Projeto", "Tarefa"]].astype(str).values.tolist()[:50]

    # projetos com mais de um identificador de descrição
    multi = proj[proj["descricoes"].map(len) > 1]
    res["projetos_com_mais_de_uma_descricao"] = multi[["Nº do Projeto", "descricoes"]].astype(str).values.tolist()

    # linhas de orçado sem conta ou grupo
    res["orcado_sem_conta"] = int((orc["Conta Contábil"] == "").sum())
    res["orcado_sem_grupo"] = int((orc["Grupo de Despesa"] == "").sum())
    sem_conta = df[df["Conta Contábil"] == ""]
    res["linhas_sem_conta_por_tipo"] = sem_conta["Tipo de Lançamento"].value_counts().to_dict()
    res["valor_sem_conta_por_tipo"] = sem_conta.groupby("Tipo de Lançamento")["Valor"].sum().round(2).to_dict()
    # orçamentos sem Nº do Projeto mesmo após a tentativa de recuperação
    res["orcamentos_sem_n_projeto"] = sorted(df.loc[df["Nº do Projeto"] == "", "Nº do Orçamento"].unique().tolist())

    (OUT / "relatorio_resumo.json").write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    print(json.dumps({k: v for k, v in res.items() if k != "orcado_por_projeto"},
                     ensure_ascii=False, indent=2, default=str)[:6000])
    print("\nOrçado por projeto|origem:")
    for k, v in res["orcado_por_projeto"].items():
        print(f"  {k:28s} {v:>16,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
