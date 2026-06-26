#!/usr/bin/env bash
# Verify cuDNN 8 (whisperX) and PyTorch cu124 (CUDA 12.4) both load.
set -euo pipefail

export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}"

if ! ldconfig -p 2>/dev/null | grep -q 'libcudnn_ops_infer.so.8'; then
  echo "ERROR: libcudnn_ops_infer.so.8 missing — run docker/setup_cudnn8.sh"
  exit 1
fi

python3 - <<'PY'
import ctypes

ctypes.CDLL("libcudnn_ops_infer.so.8")
print("cuDNN8 libcudnn_ops_infer.so.8 OK")
PY

python3 - <<'PY'
import torch

print(f"torch={torch.__version__} cuda={torch.version.cuda}")
if torch.version.cuda and not torch.version.cuda.startswith("12.4"):
    raise SystemExit(f"expected PyTorch built for CUDA 12.4, got {torch.version.cuda}")
print("PyTorch import OK")
PY
