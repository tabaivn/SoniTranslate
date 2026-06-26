#!/usr/bin/env bash
# Fail fast if the container is running stale/broken application code.
set -euo pipefail

APP_DIR="${1:-/app}"
PREPROCESSOR="${APP_DIR}/soni_translate/preprocessor.py"

if [[ ! -f "${PREPROCESSOR}" ]]; then
  echo "ERROR: missing ${PREPROCESSOR}"
  exit 1
fi

if grep -q 'subprocess\.Popen' "${PREPROCESSOR}"; then
  echo "ERROR: ${PREPROCESSOR} still calls subprocess.Popen directly."
  echo "Rebuild and redeploy the Docker image from the latest repository."
  exit 1
fi

cd "${APP_DIR}"

python3 - <<'PY'
import inspect
import sys

from soni_translate.preprocessor import audio_video_preprocessor
from soni_translate.utils import run_subprocess, yt_dlp_command

source = inspect.getsource(audio_video_preprocessor)
if "subprocess.Popen" in source:
    raise SystemExit("audio_video_preprocessor still references subprocess.Popen")

cmd = yt_dlp_command("--version")
if cmd[0] != sys.executable or cmd[1] != "-m" or cmd[2] != "yt_dlp":
    raise SystemExit(f"unexpected yt-dlp invocation: {cmd!r}")

if not callable(run_subprocess):
    raise SystemExit("run_subprocess helper is unavailable")

print("App verification OK")
PY
