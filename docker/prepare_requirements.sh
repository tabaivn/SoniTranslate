#!/usr/bin/env bash
# Generate Docker-specific requirement files (cuda_12_x whisperX, no unpinned transformers).
set -euo pipefail

OUT_DIR="${1:?output directory required}"
mkdir -p "${OUT_DIR}"

APP_DIR="${SONITR_APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

sed 's|git+https://github.com/R3gm/whisperX.git@cuda_11_8|git+https://github.com/R3gm/whisperX.git@cuda_12_x|' \
  "${APP_DIR}/requirements_base.txt" > "${OUT_DIR}/requirements_base.docker.txt"

grep -v '^transformers$' "${APP_DIR}/requirements_extra.txt" \
  > "${OUT_DIR}/requirements_extra.docker.txt"

grep -v '^transformers$' "${APP_DIR}/requirements_xtts.txt" \
  > "${OUT_DIR}/requirements_xtts.docker.txt"

cp "${APP_DIR}/requirements_gradio.txt" "${OUT_DIR}/requirements_gradio.txt"
