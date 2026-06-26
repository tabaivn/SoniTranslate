#!/usr/bin/env bash
# VieNeu v3 Turbo needs tokenizers>=0.21; whisperX needs tokenizers==0.15.2 in main env.
set -euxo pipefail

APP_DIR="${SONITR_APP_DIR:-/app}"
VIENEU_VENV="${SONITR_VIENEU_VENV:-/opt/vieneu-venv}"
REQ_FILE="${APP_DIR}/requirements_vieneu.txt"

python3 -m venv --system-site-packages "${VIENEU_VENV}"
"${VIENEU_VENV}/bin/python" -m pip install --upgrade pip==23.1.2 wheel
"${VIENEU_VENV}/bin/pip" install --prefer-binary -r "${REQ_FILE}"

"${VIENEU_VENV}/bin/python" - <<'PY'
from importlib.metadata import version
import vieneu  # noqa: F401
from vieneu import Vieneu  # noqa: F401

tok = version("tokenizers")
tr = version("transformers")
if tuple(int(x) for x in tok.split(".")[:2]) < (0, 21):
    raise SystemExit(f"VieNeu venv tokenizers too old: {tok}")
print(f"VieNeu venv OK: tokenizers=={tok}, transformers=={tr}")
PY

echo "VieNeu isolated venv ready: ${VIENEU_VENV}"
