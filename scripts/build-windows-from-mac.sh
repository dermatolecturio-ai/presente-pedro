#!/usr/bin/env bash
# Automatiza: push → GitHub Actions (Windows exe) → download do zip
set -euo pipefail
cd "$(dirname "$0")/.."

ROOT="$(pwd)"
OUT_DIR="${ROOT}/dist"
ZIP_NAME="PresentePedro-windows.zip"

echo "==> Repo: $ROOT"

if ! command -v gh >/dev/null; then
  echo "Erro: instale o GitHub CLI (brew install gh)" >&2
  exit 1
fi

if ! gh auth status -h github.com >/dev/null 2>&1; then
  echo "GitHub CLI nao autenticado. Rodando login interativo..."
  gh auth login -h github.com -p https -w
fi

# Garante remote
if ! git remote get-url origin >/dev/null 2>&1; then
  echo "==> Criando repositorio privado no GitHub..."
  gh repo create presente-pedro --private --source=. --remote=origin --push
else
  echo "==> Remote origin: $(git remote get-url origin)"
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  echo "==> Push $BRANCH..."
  git push -u origin HEAD
fi

echo "==> Disparando workflow Build Windows exe..."
gh workflow run "Build Windows exe" --ref "$(git rev-parse --abbrev-ref HEAD)"

echo "==> Aguardando job (pode levar 20-60+ min por causa do PyTorch)..."
# Espera o run mais recente deste workflow
for i in $(seq 1 90); do
  RUN_ID="$(gh run list --workflow="Build Windows exe" --limit 1 --json databaseId,status,conclusion,url --jq '.[0].databaseId')"
  STATUS="$(gh run list --workflow="Build Windows exe" --limit 1 --json status,conclusion --jq '.[0] | "\(.status)|\(.conclusion // "")"')"
  echo "  [$i] run=$RUN_ID status=$STATUS"
  STATE="${STATUS%%|*}"
  CONCL="${STATUS##*|}"
  if [[ "$STATE" == "completed" ]]; then
    if [[ "$CONCL" != "success" ]]; then
      echo "Build falhou ($CONCL). Veja: $(gh run view "$RUN_ID" --json url --jq .url)" >&2
      gh run view "$RUN_ID" --log-failed | tail -n 80 || true
      exit 1
    fi
    break
  fi
  sleep 30
done

mkdir -p "$OUT_DIR"
echo "==> Baixando artifact..."
gh run download "$RUN_ID" -n PresentePedro-windows -D "$OUT_DIR"

# Normaliza nome
if [[ -f "$OUT_DIR/$ZIP_NAME" ]]; then
  FINAL="$OUT_DIR/$ZIP_NAME"
elif [[ -f "$OUT_DIR/PresentePedro-windows.zip" ]]; then
  FINAL="$OUT_DIR/PresentePedro-windows.zip"
else
  FINAL="$(find "$OUT_DIR" -name '*.zip' | head -n 1)"
fi

cp -f "GUIA-PARA-O-PEDRO.md" "$OUT_DIR/GUIA-PARA-O-PEDRO.md"

echo ""
echo "PRONTO para mandar ao Pedro:"
echo "  ZIP:  $FINAL"
echo "  GUIA: $OUT_DIR/GUIA-PARA-O-PEDRO.md"
echo ""
open "$OUT_DIR" 2>/dev/null || true
