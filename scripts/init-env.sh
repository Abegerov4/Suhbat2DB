#!/usr/bin/env bash
# Создаёт .env из .env.example, заменяя <generated> на случайные секреты.
# Если .env уже есть, дописывает только переменные, которых в нём нет;
# существующие значения не меняются.
set -euo pipefail

cd "$(dirname "$0")/.."

hex() { openssl rand -hex "$1"; }

render() {
  local line="$1" key value
  if [[ "$line" == *"=<generated>" ]]; then
    key="${line%%=*}"
    case "$key" in
      LANGFUSE_LOCAL_PUBLIC_KEY) value="pk-lf-$(hex 16)" ;;
      LANGFUSE_LOCAL_SECRET_KEY) value="sk-lf-$(hex 16)" ;;
      LANGFUSE_ENCRYPTION_KEY) value="$(hex 32)" ;;  # ровно 64 hex-символа
      APP_ENCRYPTION_KEY) value="$(openssl rand -base64 32 | tr '+/' '-_')" ;;  # формат Fernet
      *) value="$(hex 24)" ;;
    esac
    echo "${key}=${value}"
  else
    echo "$line"
  fi
}

if [[ ! -f .env ]]; then
  while IFS= read -r line; do render "$line"; done < .env.example > .env
  chmod 600 .env
  echo ".env создан. Пароль Langfuse UI: см. LANGFUSE_INIT_USER_PASSWORD в .env"
  exit 0
fi

# файл мог быть отредактирован вручную без перевода строки в конце
[[ -s .env && "$(tail -c1 .env)" != "" ]] && echo >> .env

added=()
while IFS= read -r line; do
  [[ "$line" =~ ^([A-Z_][A-Z0-9_]*)= ]] || continue
  key="${BASH_REMATCH[1]}"
  if ! grep -q "^${key}=" .env; then
    render "$line" >> .env
    added+=("$key")
  fi
done < .env.example

if (( ${#added[@]} )); then
  echo "В .env добавлены: ${added[*]}"
fi
