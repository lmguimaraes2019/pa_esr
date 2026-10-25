# Orçamento ESR 2027

App de planejamento anual (FastAPI + SQLite + React). Endereço: https://orcamento.lmguimaraes.com.br

## Deploy na VPS (Ubuntu com Docker)

1. No DNS de lmguimaraes.com.br, crie um registro A: `orcamento` apontando para o IP da VPS.
2. Na VPS:
   ```bash
   git clone https://github.com/lmguimaraes2019/pa_esr.git && cd pa_esr
   mkdir dados      # copie para cá as 3 planilhas (veja abaixo)
   docker compose up -d --build
   ```
3. Planilhas em `dados/` (nomes exatos):
   `2026_-_Base_Protheus_-_ESR.xlsx`, `Template_Planejamento_Anual_-_2027.xlsx`, `projetos_pa_2026.xlsx`
4. Carga inicial (uma vez só; cria usuários e imprime onde estão as senhas provisórias):
   ```bash
   docker compose run --rm app python -m app.seed --protheus /dados/2026_-_Base_Protheus_-_ESR.xlsx \
     --template /dados/Template_Planejamento_Anual_-_2027.xlsx --pa /dados/projetos_pa_2026.xlsx
   docker compose exec app cat /data/senhas_iniciais.txt   # repasse as senhas e depois apague o arquivo
   docker compose exec app rm /data/senhas_iniciais.txt
   ```
5. Backup diário: `crontab -e` e adicione `15 2 * * * /caminho/pa_esr/backup.sh`

## Atualizar
`git pull && docker compose up -d --build` (o banco fica no volume e não é afetado).

## Desenvolvimento
`pip install -r requirements.txt`, `python -m pytest tests` (precisa das planilhas em ORC_TEST_UPLOADS) e `cd web && npm i && npm run dev`.
