# syntax=docker/dockerfile:1
# SoniTranslate — CUDA 12.4 (PyTorch cu124) + apt libcudnn8 (whisperX/ctranslate2).
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/local/cuda/lib64 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    SONITR_DEVICE=cuda \
    HF_HOME=/workspace/.cache/huggingface \
    HUGGINGFACE_HUB_CACHE=/workspace/.cache/huggingface/hub \
    TORCH_HOME=/workspace/.cache/torch \
    PIP_CACHE_DIR=/root/.cache/pip \
    PIP_PREFER_BINARY=1 \
    NO_PROXY=localhost,127.0.0.1,::1 \
    no_proxy=localhost,127.0.0.1,::1 \
    SONITR_DEPS_VERSION=4 \
    SONITR_THEME=soft

COPY docker/setup_cudnn8.sh docker/

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    python-is-python3 \
    ffmpeg \
    git \
    git-lfs \
    perl \
    build-essential \
    curl \
    ca-certificates \
    wget \
    && chmod +x docker/setup_cudnn8.sh \
    && bash docker/setup_cudnn8.sh \
    && rm -rf /var/lib/apt/lists/* \
    && git lfs install \
    && ln -sf /usr/bin/python3 /usr/bin/python

WORKDIR /app

# Layer 1: requirements only — Docker reuses this layer until requirements change.
COPY requirements_base.txt requirements_extra.txt requirements_xtts.txt requirements_gradio.txt requirements_vieneu.txt ./
COPY docker/install_deps.sh docker/prepare_requirements.sh docker/verify_cuda.sh docker/setup_vieneu_venv.sh docker/
COPY soni_translate/gradio_theme.py soni_translate/

RUN chmod +x docker/install_deps.sh docker/prepare_requirements.sh docker/verify_cuda.sh docker/setup_vieneu_venv.sh

RUN --mount=type=cache,target=/root/.cache/pip \
    SONITR_SKIP_THEME_CHECK=1 bash docker/install_deps.sh

RUN --mount=type=cache,target=/root/.cache/pip \
  bash docker/setup_vieneu_venv.sh

# Layer 2: application code (does not invalidate the dependency layer above).
COPY . .

RUN find /app -type d -name __pycache__ -prune -exec rm -rf {} + \
    && chmod +x /app/docker/verify_app.sh /app/docker/verify_cuda.sh \
    && bash /app/docker/verify_app.sh /app \
    && bash /app/docker/verify_cuda.sh \
    && sha256sum /app/soni_translate/preprocessor.py | awk '{print $1}' > /app/.sonitr_build_stamp

RUN python3 - <<'PY'
from soni_translate.gradio_theme import get_gradio_builtin_theme_names, resolve_gradio_theme
from soni_translate.utils import ffmpeg_command, yt_dlp_command
import subprocess
import torch

resolve_gradio_theme("soft")
subprocess.run(yt_dlp_command("--version"), check=True, capture_output=True)
subprocess.run(ffmpeg_command("-version"), check=True, capture_output=True)
print("Gradio themes OK:", ", ".join(get_gradio_builtin_theme_names()))
print(f"PyTorch OK: {torch.__version__} cuda={torch.version.cuda}")
PY

RUN chmod +x /app/docker/install_deps.sh /app/docker/start.sh /app/docker/prepare_requirements.sh \
    && mkdir -p /workspace/.cache/huggingface /workspace/.cache/torch /workspace/.cache/pip \
    && mkdir -p downloads logs weights audio audio2/audio outputs \
    && touch /app/.sonitr_deps_baked \
    && echo "preprocessor-subprocess-fix-v1" >> /app/.sonitr_build_stamp \
    && echo "cuda124-cudnn8-v2" >> /app/.sonitr_build_stamp \
    && echo "vieneu-venv-v1" >> /app/.sonitr_build_stamp

ENV SONITR_VIENEU_PYTHON=/opt/vieneu-venv/bin/python

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=15s --start-period=300s --retries=5 \
    CMD curl -fsS "http://127.0.0.1:7860/" >/dev/null || exit 1

ENTRYPOINT ["/app/docker/start.sh"]
