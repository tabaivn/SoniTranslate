#!/usr/bin/env bash
# ctranslate2/whisperX need cuDNN 8 (libcudnn_ops_infer.so.8).
# CUDA 12.4 runtime images ship cuDNN 9 only — install libcudnn8 from NVIDIA apt repo.
set -euo pipefail

if ldconfig -p 2>/dev/null | grep -q 'libcudnn_ops_infer.so.8'; then
  echo "libcudnn8 already installed"
  exit 0
fi

export DEBIAN_FRONTEND=noninteractive
KEYRING=/tmp/cuda-keyring.deb

wget -q -O "${KEYRING}" \
  https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
dpkg -i "${KEYRING}"
apt-get update
apt-get install -y --no-install-recommends libcudnn8
ldconfig
rm -f "${KEYRING}"

if ! ldconfig -p | grep -q 'libcudnn_ops_infer.so.8'; then
  echo "ERROR: libcudnn8 install did not provide libcudnn_ops_infer.so.8"
  exit 1
fi

echo "libcudnn8 installed for CUDA 12.x"
