#!/usr/bin/env bash
# Backup diário consistente do banco (rode via cron). Guarda 30 dias em ./backups
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
docker compose exec -T app python -c "
import sqlite3
s=sqlite3.connect('/data/orcamento.db'); d=sqlite3.connect('/data/backup.db'); s.backup(d); d.close()"
docker compose cp app:/data/backup.db "backups/orcamento_$(date +%Y%m%d_%H%M).db"
docker compose exec -T app rm -f /data/backup.db
find backups -name 'orcamento_*.db' -mtime +30 -delete
