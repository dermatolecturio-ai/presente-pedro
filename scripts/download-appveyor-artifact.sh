#!/usr/bin/env bash
# Baixa PresentePedro-windows.zip do ultimo build AppVeyor com sucesso.
#
# Uma vez:
#   1) Conta em https://ci.appveyor.com (login com GitHub)
#   2) New Project → dermatolecturio-ai/presente-pedro
#   3) Account → API Token → copie
#   4) export APPVEYOR_TOKEN=...
#   5) ./scripts/download-appveyor-artifact.sh
#
# Opcionais:
#   APPVEYOR_ACCOUNT  (default: dermatolecturio-ai)
#   APPVEYOR_PROJECT  (default: presente-pedro)
set -euo pipefail
cd "$(dirname "$0")/.."

ACCOUNT="${APPVEYOR_ACCOUNT:-dermatolecturio-ai}"
PROJECT="${APPVEYOR_PROJECT:-presente-pedro}"
OUT_DIR="${PWD}/dist"
ZIP_NAME="PresentePedro-windows.zip"

if [[ -z "${APPVEYOR_TOKEN:-}" ]]; then
  echo "Defina APPVEYOR_TOKEN (Account → API Token no AppVeyor)." >&2
  echo "Abra: https://ci.appveyor.com/api-token" >&2
  open "https://ci.appveyor.com/api-token" 2>/dev/null || true
  exit 1
fi

API="https://ci.appveyor.com/api"
AUTH=(-H "Authorization: Bearer ${APPVEYOR_TOKEN}" -H "Content-Type: application/json")

echo "==> Ultimo build de ${ACCOUNT}/${PROJECT}"
BUILD_JSON="$(curl -fsSL "${AUTH[@]}" \
  "${API}/projects/${ACCOUNT}/${PROJECT}/branch/main")"

STATUS="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["build"]["status"])' <<<"$BUILD_JSON")"
BUILD_ID="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["build"]["buildId"])' <<<"$BUILD_JSON")"
VERSION="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["build"]["version"])' <<<"$BUILD_JSON")"
JOB_ID="$(python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["build"]["jobs"][0]["jobId"])' <<<"$BUILD_JSON")"

echo "  version=$VERSION buildId=$BUILD_ID status=$STATUS job=$JOB_ID"

if [[ "$STATUS" != "success" ]]; then
  echo "Build ainda nao esta success (status=$STATUS)." >&2
  echo "Acompanhe: https://ci.appveyor.com/project/${ACCOUNT}/${PROJECT}" >&2
  open "https://ci.appveyor.com/project/${ACCOUNT}/${PROJECT}" 2>/dev/null || true
  exit 1
fi

mkdir -p "$OUT_DIR"
TMP="$(mktemp -d)"
echo "==> Baixando artifacts do job..."
curl -fsSL "${AUTH[@]}" \
  -o "${TMP}/artifacts.zip" \
  "${API}/buildjobs/${JOB_ID}/artifacts"

# AppVeyor devolve um zip com os artifacts dentro, ou o arquivo direto
if unzip -l "${TMP}/artifacts.zip" 2>/dev/null | grep -q '\.zip'; then
  unzip -o "${TMP}/artifacts.zip" -d "$TMP"
  FOUND="$(find "$TMP" -name "$ZIP_NAME" | head -n 1)"
  if [[ -z "$FOUND" ]]; then
    FOUND="$(find "$TMP" -name '*.zip' ! -name 'artifacts.zip' | head -n 1)"
  fi
  cp -f "$FOUND" "${OUT_DIR}/${ZIP_NAME}"
else
  cp -f "${TMP}/artifacts.zip" "${OUT_DIR}/${ZIP_NAME}"
fi

cp -f GUIA-PARA-O-PEDRO.md "${OUT_DIR}/GUIA-PARA-O-PEDRO.md"
echo ""
echo "PRONTO para mandar ao Pedro:"
echo "  ZIP:  ${OUT_DIR}/${ZIP_NAME}"
echo "  GUIA: ${OUT_DIR}/GUIA-PARA-O-PEDRO.md"
open "$OUT_DIR" 2>/dev/null || true
