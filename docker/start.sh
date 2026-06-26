#!/usr/bin/env bash
set -euo pipefail

cd /app

export GRADIO_SERVER_NAME="${GRADIO_SERVER_NAME:-0.0.0.0}"
export GRADIO_SERVER_PORT="${GRADIO_SERVER_PORT:-7860}"
export NO_PROXY="${NO_PROXY:-localhost,127.0.0.1,::1}"
export no_proxy="${no_proxy:-localhost,127.0.0.1,::1}"
export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}"
export SONITR_VIENEU_PYTHON="${SONITR_VIENEU_PYTHON:-/opt/vieneu-venv/bin/python}"
export SONITR_DEVICE="${SONITR_DEVICE:-cuda}"
export HF_HOME="${HF_HOME:-/workspace/.cache/huggingface}"
export HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-${HF_HOME}/hub}"
export TORCH_HOME="${TORCH_HOME:-/workspace/.cache/torch}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-/workspace/.cache/pip}"
export SONITR_DEPS_VERSION="${SONITR_DEPS_VERSION:-4}"

DEPS_MARKER="${SONITR_DEPS_MARKER:-/workspace/.sonitr_deps_installed_v${SONITR_DEPS_VERSION}}"

mkdir -p "${HF_HOME}" "${TORCH_HOME}" "${PIP_CACHE_DIR}" /workspace

needs_runtime_install() {
  if [[ "${SONITR_RUNTIME_INSTALL:-0}" == "1" ]]; then
    return 0
  fi
  if [[ -f /app/.sonitr_deps_baked ]]; then
    return 1
  fi
  if [[ -f "${DEPS_MARKER}" ]]; then
    return 1
  fi
  return 0
}

if [[ "${SONITR_FORCE_REINSTALL:-0}" == "1" ]]; then
  echo "SONITR_FORCE_REINSTALL=1 — reinstalling Python dependencies..."
  rm -f "${DEPS_MARKER}"
  bash /app/docker/install_deps.sh
  touch "${DEPS_MARKER}"
elif needs_runtime_install; then
  echo "============================================================"
  echo "Installing SoniTranslate dependencies at runtime..."
  echo "Tip: rebuild the Docker image to bake deps and skip this step."
  echo "Cache: ${PIP_CACHE_DIR}"
  echo "============================================================"
  bash /app/docker/install_deps.sh
  touch "${DEPS_MARKER}"
  echo "Dependency install complete. Marker: ${DEPS_MARKER}"
elif [[ -f /app/.sonitr_deps_baked ]]; then
  echo "Dependencies pre-installed in image — starting immediately."
else
  echo "Dependencies already installed (${DEPS_MARKER}). Skipping pip install."
fi

echo "============================================================"
if [[ -f /app/.sonitr_build_stamp ]]; then
  echo "SoniTranslate build stamp: $(tr '\n' ' ' < /app/.sonitr_build_stamp)"
else
  echo "WARNING: missing /app/.sonitr_build_stamp — image may be outdated."
fi
bash /app/docker/verify_app.sh /app
bash /app/docker/verify_cuda.sh
echo "============================================================"

if [[ -z "${YOUR_HF_TOKEN:-}" ]]; then
  echo "WARNING: YOUR_HF_TOKEN is not set."
  echo "Pyannote diarization requires a Hugging Face token with access to:"
  echo "  https://huggingface.co/pyannote/speaker-diarization"
  echo "  https://huggingface.co/pyannote/segmentation"
fi

THEME="${SONITR_THEME:-soft}"
LANGUAGE="${SONITR_LANGUAGE:-english}"
VERBOSITY="${SONITR_VERBOSITY:-info}"

ARGS=(
  --theme "${THEME}"
  --language "${LANGUAGE}"
  --verbosity_level "${VERBOSITY}"
)

if [[ "${SONITR_CPU_MODE:-0}" == "1" ]]; then
  ARGS+=(--cpu_mode)
fi

if [[ "${SONITR_PUBLIC_URL:-0}" == "1" ]]; then
  ARGS+=(--public_url)
fi

exec python3 app_rvc.py "${ARGS[@]}"
