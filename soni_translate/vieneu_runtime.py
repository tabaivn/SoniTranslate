"""Run VieNeu-TTS in an isolated venv (new tokenizers) without breaking whisperX."""

import json
import os
import subprocess
import sys
import tempfile

from .logging_setup import logger

DEFAULT_VIENEU_PYTHON = "/opt/vieneu-venv/bin/python"


def get_vieneu_python():
    return os.environ.get("SONITR_VIENEU_PYTHON", DEFAULT_VIENEU_PYTHON)


def vieneu_venv_available():
    vieneu_python = get_vieneu_python()
    return os.path.isfile(vieneu_python)


def verify_vieneu_runtime():
    vieneu_python = get_vieneu_python()
    if not os.path.isfile(vieneu_python):
        raise FileNotFoundError(
            f"VieNeu Python not found at {vieneu_python}. "
            "Rebuild the Docker image (docker/setup_vieneu_venv.sh)."
        )
    subprocess.run(
        [vieneu_python, "-c", "from vieneu import Vieneu"],
        check=True,
        capture_output=True,
    )


def run_vieneu_tts_subprocess(filtered_vieneu_segments, translate_audio_to, batch_size):
    verify_vieneu_runtime()
    vieneu_python = get_vieneu_python()

    payload = {
        "segments": filtered_vieneu_segments,
        "lang": translate_audio_to,
        "batch_size": batch_size,
        "cwd": os.getcwd(),
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as handle:
        json.dump(payload, handle)
        payload_path = handle.name

    env = os.environ.copy()
    app_dir = os.environ.get("SONITR_APP_DIR", "/app")
    env["SONITR_APP_DIR"] = app_dir
    env["PYTHONPATH"] = app_dir + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )

    try:
        result = subprocess.run(
            [vieneu_python, "-m", "soni_translate.vieneu_worker", payload_path],
            env=env,
            cwd=payload["cwd"],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            logger.info(result.stdout.strip())
        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(stderr[-4000:] if stderr else "unknown error")
    finally:
        try:
            os.unlink(payload_path)
        except OSError:
            pass
