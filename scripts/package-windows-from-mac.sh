#!/usr/bin/env bash
# Empacota no Mac um zip Windows usavel SEM GitHub Actions / PyInstaller.
# Pedro abre packaging\windows\Abrir-PresentePedro.bat (primeira vez instala deps).
set -euo pipefail
cd "$(dirname "$0")/.."

ROOT="$(pwd)"
STAGE="${ROOT}/dist/PresentePedro-bootstrap"
OUT_ZIP="${ROOT}/dist/PresentePedro-windows-bootstrap.zip"

rm -rf "$STAGE"
mkdir -p "$STAGE"

# Copia o necessario (sem .venv, caches, dist parcial)
rsync -a \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude 'venv' \
  --exclude 'dist' \
  --exclude 'build' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  --exclude 'data/tmp' \
  --exclude 'runtime' \
  --exclude 'agent-transcripts' \
  ./ "$STAGE/"

# Atalho na raiz do zip
cat > "$STAGE/Abrir-PresentePedro.bat" <<'EOF'
@echo off
cd /d "%~dp0"
call packaging\windows\Abrir-PresentePedro.bat
EOF

cp -f GUIA-PARA-O-PEDRO.md "$STAGE/GUIA-PARA-O-PEDRO.md"
cat > "$STAGE/LEIA-ME.txt" <<'EOF'
Presente do Victor Prudencio para O Pedro
========================================

1) Extraia este zip no Windows
2) Duplo clique em Abrir-PresentePedro.bat
3) Na primeira vez: precisa internet (instala Python deps + modelo)
4) Leia GUIA-PARA-O-PEDRO.md

Tudo roda LOCAL no PC.
EOF

rm -f "$OUT_ZIP"
(
  cd "$(dirname "$STAGE")"
  ditto -c -k --sequesterRsrc --keepParent "$(basename "$STAGE")" "$(basename "$OUT_ZIP")"
)

cp -f GUIA-PARA-O-PEDRO.md "${ROOT}/dist/GUIA-PARA-O-PEDRO.md"

echo ""
echo "PRONTO (sem precisar do GitHub Actions):"
echo "  ZIP:  $OUT_ZIP"
echo "  GUIA: ${ROOT}/dist/GUIA-PARA-O-PEDRO.md"
echo ""
open "${ROOT}/dist" 2>/dev/null || true
