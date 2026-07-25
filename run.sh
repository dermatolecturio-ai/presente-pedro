#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  echo "Criando ambiente virtual…"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [[ ! -f .venv/.deps-ok ]]; then
  echo "Instalando dependências (pode demorar na 1ª vez)…"
  pip install --upgrade pip
  pip install -r requirements.txt
  touch .venv/.deps-ok
fi

export PYTORCH_ENABLE_MPS_FALLBACK=1
export TOKENIZERS_PARALLELISM=false

echo "Presente do Victor Prudencio para O Pedro → http://127.0.0.1:8787"
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8787 --reload
