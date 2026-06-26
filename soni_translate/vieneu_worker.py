"""Subprocess entrypoint for VieNeu-TTS (isolated tokenizers/transformers)."""

import json
import os
import sys


def main():
    payload_path = sys.argv[1]
    with open(payload_path, encoding="utf-8") as handle:
        payload = json.load(handle)

    os.chdir(payload["cwd"])
    os.environ.setdefault("SONITR_DEVICE", "cuda")

    from soni_translate.text_to_speech import segments_vieneu_tts_inprocess

    segments_vieneu_tts_inprocess(
        payload["segments"],
        payload["lang"],
        batch_size=payload.get("batch_size"),
    )


if __name__ == "__main__":
    main()
