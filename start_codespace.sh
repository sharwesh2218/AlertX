#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

export TF_USE_LEGACY_KERAS=1
export TF_CPP_MIN_LOG_LEVEL=2

if [ -z "${SECRET_KEY}" ]; then
  if [ -f backend/.env ] && grep -q "^SECRET_KEY=" backend/.env; then
    true
  else
    GEN_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "SECRET_KEY=${GEN_KEY}" >> backend/.env
    echo "🔑 Generated persistent SECRET_KEY in backend/.env"
  fi
fi

if [ -n "${CODESPACE_NAME}" ]; then
  DOMAIN="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
  PUBLIC_LINK="https://${CODESPACE_NAME}-8000.${DOMAIN}"
  echo ""
  echo "=================================================================="
  echo " 🌐 AlertX + Sentinel Public Codespace URL:"
  echo "    ${PUBLIC_LINK}"
  echo " ⚠️  In the bottom PORTS tab, right-click Port 8000 ->"
  echo "    Port Visibility -> Public so anyone can open this link!"
  echo "=================================================================="
  echo ""
fi

python3 backend/run.py

