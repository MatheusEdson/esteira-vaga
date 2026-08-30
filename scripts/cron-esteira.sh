#!/bin/bash
# Um ciclo da esteira: busca o que mudou, classifica, avisa se precisar.
#
# LOG FICA JUNTO DO PROJETO, nunca em /var/log. O log tem assunto de e-mail de candidatura,
# e /var/log costuma ser 644, legivel por qualquer usuario da maquina. Token trancado com
# log aberto nao protege nada.
#
# Uso no crontab (veja deploy/crontab.example):
#   */15 * * * * flock -n /tmp/esteira.lock /caminho/do/repo/scripts/cron-esteira.sh

set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ" || exit 1

# .env e' opcional: as variaveis podem vir do ambiente do cron
[ -f .env ] && set -a && . ./.env && set +a

PY="./venv/bin/python"
[ -x "$PY" ] || PY="python3"

mkdir -p log
chmod 700 log 2>/dev/null
LOG="log/cron.log"

{
  echo "=== $(date '+%F %T %Z') ==="
  "$PY" tools/esteira/esteira.py cron
  "$PY" tools/esteira/avisar.py
  echo
} >> "$LOG" 2>&1

# rotacao simples: nao deixa o log crescer sem fim
TAM=$(stat -c%s "$LOG" 2>/dev/null || echo 0)
if [ "$TAM" -gt 5000000 ]; then
  tail -c 1000000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
