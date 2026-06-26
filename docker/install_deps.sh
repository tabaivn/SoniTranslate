#!/usr/bin/env bash
set -euxo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${SONITR_APP_DIR:-$(dirname "$SCRIPT_DIR")}"
cd "${APP_DIR}"

export PIP_CACHE_DIR="${PIP_CACHE_DIR:-/root/.cache/pip}"
export PIP_PREFER_BINARY="${PIP_PREFER_BINARY:-1}"
export PIP_DISABLE_PIP_VERSION_CHECK=1
mkdir -p "${PIP_CACHE_DIR}"

DEPS_DIR="/tmp/sonitr_deps"
bash "${SCRIPT_DIR}/prepare_requirements.sh" "${DEPS_DIR}"

PIP_INSTALL=(python3 -m pip install --prefer-binary)

"${PIP_INSTALL[@]}" --upgrade pip==23.1.2 setuptools==80.6.0 wheel

# Same cleanup as SoniTranslate_Colab.ipynb to avoid dependency conflicts.
python3 -m pip uninstall -y chex pandas-stubs ibis-framework albumentations albucore jax || true

"${PIP_INSTALL[@]}" \
  torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
  --index-url https://download.pytorch.org/whl/cu124

"${PIP_INSTALL[@]}" -r "${DEPS_DIR}/requirements_base.docker.txt"
"${PIP_INSTALL[@]}" -r "${DEPS_DIR}/requirements_extra.docker.txt"
"${PIP_INSTALL[@]}" onnxruntime-gpu==1.22.0 piper-tts==1.2.0
"${PIP_INSTALL[@]}" -r "${DEPS_DIR}/requirements_xtts.docker.txt"
"${PIP_INSTALL[@]}" TTS==0.21.1 --no-deps
"${PIP_INSTALL[@]}" 'sea-g2p>=0.7.6' 'perth>=0.2.0' || true

# whisperX + pyannote require transformers 4.39.x and tokenizers < 0.19.
"${PIP_INSTALL[@]}" \
  'transformers==4.39.3' \
  'tokenizers==0.15.2' \
  'huggingface-hub>=0.19.3,<1.0'

# Gradio last so nothing overrides gradio-client (must stay 1.3.0 for gradio 4.44.1).
"${PIP_INSTALL[@]}" -r "${DEPS_DIR}/requirements_gradio.txt"
# Re-pin pydantic after gradio in case another package upgraded it.
"${PIP_INSTALL[@]}" 'pydantic==2.10.6'

python3 - <<'PY'
from importlib.metadata import version, PackageNotFoundError

gradio_v = version("gradio")
try:
    client_v = version("gradio-client")
except PackageNotFoundError:
    client_v = version("gradio_client")
pydantic_v = version("pydantic")

if gradio_v != "4.44.1" or client_v != "1.3.0":
    raise SystemExit(
        f"Gradio version check failed: gradio=={gradio_v}, gradio-client=={client_v} "
        "(expected gradio==4.44.1, gradio-client==1.3.0)"
    )
if pydantic_v != "2.10.6":
    raise SystemExit(
        f"Pydantic version check failed: pydantic=={pydantic_v} "
        "(expected pydantic==2.10.6 for gradio_client schema compatibility)"
    )
print(f"Gradio OK: gradio=={gradio_v}, gradio-client=={client_v}, pydantic=={pydantic_v}")
PY

if [[ "${SONITR_SKIP_THEME_CHECK:-0}" != "1" ]]; then
  python3 - <<'PY'
from soni_translate.gradio_theme import get_gradio_builtin_theme_names, resolve_gradio_theme

names = get_gradio_builtin_theme_names()
if not names:
    raise SystemExit("No built-in Gradio themes available")

resolve_gradio_theme("soft")
resolve_gradio_theme("origin")
resolve_gradio_theme("Taithrah/Minimal")
print("Gradio themes OK:", ", ".join(names))
PY
fi

python3 - <<'PY'
import shutil
import subprocess
import sys

ffmpeg = shutil.which("ffmpeg")
if not ffmpeg:
    raise SystemExit("ffmpeg not found on PATH")

subprocess.run(
    [sys.executable, "-m", "yt_dlp", "--version"],
    check=True,
    capture_output=True,
)
subprocess.run([ffmpeg, "-version"], check=True, capture_output=True)
print(f"CLI OK: python={sys.executable}, ffmpeg={ffmpeg}")
PY

bash "${SCRIPT_DIR}/verify_cuda.sh"

echo "SoniTranslate dependencies installed successfully."
