from .utils import run_command
import os

DUB_DYNAUDNORM = "dynaudnorm=f=150:g=25:p=0.95:m=100:s=12"


def _quoted_path(path):
    return f'"{path}"'


def mix_original_and_dub(
    original_audio,
    dub_audio,
    output_path,
    volume_original=0.05,
    volume_translated=1.0,
    use_sidechain=False,
):
    """Mix background/original audio with the dubbed translation track."""
    original_audio = _quoted_path(original_audio)
    dub_audio = _quoted_path(dub_audio)
    output_path = _quoted_path(output_path)

    dub_chain = (
        "aformat=sample_fmts=fltp:channel_layouts=stereo,"
        f"{DUB_DYNAUDNORM},"
        f"volume={volume_translated}[dub]"
    )
    original_chain = (
        f"[0:a]aformat=sample_fmts=fltp:channel_layouts=stereo,"
        f"volume={volume_original}[orig]"
    )

    if use_sidechain:
        filter_complex = (
            f"[1:a]{dub_chain};"
            f"[dub]asplit=2[sc][mix];"
            f"{original_chain};"
            f"[orig][sc]sidechaincompress=threshold=0.02:ratio=10:"
            f"attack=20:release=250:makeup=1[ducked];"
            f"[ducked][mix]amix=inputs=2:duration=longest:"
            f"dropout_transition=0:normalize=0,"
            f"alimiter=limit=0.95:level=disabled[out]"
        )
    else:
        filter_complex = (
            f"{original_chain};"
            f"[1:a]{dub_chain};"
            f"[orig][dub]amix=inputs=2:duration=longest:"
            f"dropout_transition=0:normalize=0,"
            f"alimiter=limit=0.95:level=disabled[out]"
        )

    command = (
        f"ffmpeg -y -loglevel error -i {original_audio} -i {dub_audio} "
        f'-filter_complex "{filter_complex}" -map "[out]" '
        f"-c:a libmp3lame -q:a 2 {output_path}"
    )
    run_command(command)
