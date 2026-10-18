#!/usr/bin/env bash
# Создаёт .env из .env.example, заменяя <generated> на случайные секреты.
# Существующий .env не перезаписывается.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  echo ".env уже существует — ничего не меняю"
  exit 0
fi

hex() { openssl rand -hex "$1"; }

while IFS= read -r line; do
  if [[ "$line" == *"=<generated>" ]]; then
    key="${line%%=*}"
    case "$key" in
      LANGFUSE_PUBLIC_KEY) value="pk-lf-$(hex 16)" ;;
      LANGFUSE_SECRET_KEY) value="sk-lf-$(hex 16)" ;;
      LANGFUSE_ENCRYPTION_KEY) value="$(hex 32)" ;;  # ровно 64 hex-символа
      *) value="$(hex 24)" ;;
    esac
    echo "${key}=${value}"
  else
    echo "$line"
  fi
done < .env.example > .env

chmod 600 .env
echo ".env создан. Пароль Langfuse UI: см. LANGFUSE_INIT_USER_PASSWORD в .env"
