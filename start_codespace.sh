#!/usr/bin/env bash
set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "${REPO_ROOT}"

export TF_USE_LEGACY_KERAS=1
export TF_CPP_MIN_LOG_LEVEL=2
export PYTHONUNBUFFERED=1

# 1. Self-healing dependency check: auto-install if any required Python package is missing
if ! python3 -c '
import importlib.util, sys
pkgs = [
    "dotenv", "fastapi", "uvicorn", "multipart", "cv2", "numpy",
    "torch", "torchvision", "ultralytics", "tensorflow", "tf_keras",
    "bcrypt", "jose", "sqlalchemy", "requests", "firebase_admin",
    "twilio", "sendgrid", "yt_dlp", "ftfy", "regex", "clip",
]
if any(importlib.util.find_spec(p) is None for p in pkgs):
    sys.exit(1)
import dotenv, cv2
' >/dev/null 2>&1; then
  echo "📦 Installing AlertX + Sentinel Python dependencies (one-time setup, ~2-3 mins)..."

  if command -v sudo >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
    sudo rm -f /etc/apt/sources.list.d/yarn.list 2>/dev/null || true
    sudo apt-get update -y >/dev/null 2>&1 || true
    sudo apt-get install -y --no-install-recommends libgl1 libglib2.0-0t64 >/dev/null 2>&1 \
      || sudo apt-get install -y --no-install-recommends libgl1 libglib2.0-0 >/dev/null 2>&1 \
      || true
  fi

  python3 -m pip install --upgrade "setuptools<81" wheel "numpy>=1.24.0,<2.0.0"
  python3 -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
  python3 -m pip install "tensorflow-cpu>=2.16.0,<2.19.0"
  python3 -m pip install --no-deps "tf-keras>=2.16.0,<2.19.0"
  grep -Ev "^(tensorflow|tf-keras|torch|torchvision)" "${REPO_ROOT}/backend/requirements.txt" > /tmp/alertx_reqs_cpu.txt
  python3 -m pip install --no-build-isolation -r /tmp/alertx_reqs_cpu.txt
  # Replace non-headless opencv-python (pulled by ultralytics) with pure headless OpenCV
  python3 -m pip uninstall -y opencv-python opencv-python-headless >/dev/null 2>&1 || true
  python3 -m pip install --no-deps opencv-python-headless==4.10.0.84

  echo "✅ All dependencies installed successfully!"
fi

# 2. Ensure persistent SECRET_KEY exists in backend/.env
if [ -z "${SECRET_KEY}" ]; then
  if [ -f "${REPO_ROOT}/backend/.env" ] && grep -q "^SECRET_KEY=" "${REPO_ROOT}/backend/.env"; then
    true
  else
    GEN_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "SECRET_KEY=${GEN_KEY}" >> "${REPO_ROOT}/backend/.env"
    echo "🔑 Generated persistent SECRET_KEY in backend/.env"
  fi
fi

# 3. Print public Codespace URL banner
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

# 4. Launch from backend/ so relative paths (local_users.db, uploads/, logs/) resolve cleanly
cd "${REPO_ROOT}/backend"
exec python3 run.py
