from .utils import run_command
from .logging_setup import logger
import os
import soundfile as sf

DEFAULT_SAMPLE_RATE = 48000
FFMPEG_MIX_BATCH_SIZE = 200
WAV_RF64_BYTE_THRESHOLD = 3_500_000_000
DUB_DYNAUDNORM = "dynaudnorm=f=150:g=25:p=0.95:m=100:s=12"


def _probe_audio(path):
    info = sf.info(path)
    return info.samplerate, info.channels, float(info.duration)


def _estimated_pcm_bytes(duration_sec, sample_rate, channels):
    return int(duration_sec * sample_rate * channels * 2)


def _ffmpeg_output_args(output_path, sample_rate, channels, duration_sec):
    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".ogg":
        return f'-c:a libvorbis -ar {sample_rate} -ac {channels} -q:a 9'
    if ext == ".flac":
        return f'-c:a flac -ar {sample_rate} -ac {channels}'
    if ext == ".mp3":
        return f'-c:a libmp3lame -ar {sample_rate} -ac {channels} -q:a 2'

    args = f'-c:a pcm_s16le -ar {sample_rate} -ac {channels}'
    if _estimated_pcm_bytes(duration_sec, sample_rate, channels) >= (
        WAV_RF64_BYTE_THRESHOLD
    ):
        args += " -rf64 auto"
    return args


def _write_silence(output_path, duration_sec, sample_rate, channels):
    output_args = _ffmpeg_output_args(
        output_path, sample_rate, channels, duration_sec
    )
    layout = "mono" if channels == 1 else "stereo"
    command = (
        f'ffmpeg -y -loglevel error -f lavfi -i '
        f'anullsrc=channel_layout={layout}:sample_rate={sample_rate}:'
        f'd={duration_sec} {output_args} "{output_path}"'
    )
    run_command(command)


def _compute_segment_starts(segments, audio_files, avoid_overlap):
    starts = []
    last_end_time = 0.0
    previous_speaker = ""

    for line, audio_file in zip(segments, audio_files):
        start = float(line["start"])

        if avoid_overlap:
            speaker = line.get("speaker", "")
            if (last_end_time - 0.500) > start:
                overlap_time = last_end_time - start
                if previous_speaker and previous_speaker != speaker:
                    start = last_end_time - 0.500
                else:
                    start = last_end_time - 0.200
                if overlap_time > 2.5:
                    start = start - 0.3
                logger.info(
                    f"Avoid overlap for {audio_file} with {start}"
                )

            previous_speaker = speaker
            try:
                _, _, duration_tts_seconds = _probe_audio(audio_file)
            except Exception as error:
                logger.debug(str(error))
                duration_tts_seconds = 0.0
            last_end_time = start + duration_tts_seconds

        starts.append(max(0.0, start))

    return starts


def _build_mix_filter_lines(starts, sample_rate, channels, total_duration):
    layout = "mono" if channels == 1 else "stereo"
    lines = []
    mix_labels = []

    for index, start in enumerate(starts):
        delay_ms = int(start * 1000)
        delayed_label = f"d{index}"
        lines.append(
            f"[{index}:a]aresample={sample_rate},"
            f"aformat=sample_fmts=fltp:channel_layouts={layout},"
            f"adelay={delay_ms}|{delay_ms}[{delayed_label}]"
        )
        mix_labels.append(f"[{delayed_label}]")

    mix_inputs = "".join(mix_labels)
    lines.append(
        f"{mix_inputs}amix=inputs={len(mix_labels)}:"
        f"duration=longest:dropout_transition=0:normalize=0,"
        f"aformat=sample_fmts=fltp:channel_layouts={layout},"
        f"{DUB_DYNAUDNORM},"
        f"apad=whole_dur={total_duration}[out]"
    )
    return lines


def _mix_single_pass(
    starts,
    audio_files,
    output_path,
    total_duration,
    sample_rate,
    channels,
):
    if not audio_files:
        _write_silence(output_path, total_duration, sample_rate, channels)
        return

    filter_script = "_temp_dub_filter.txt"
    inputs = ""
    for audio_file in audio_files:
        inputs += f' -i "{audio_file}"'

    filter_lines = _build_mix_filter_lines(
        starts, sample_rate, channels, total_duration
    )
    with open(filter_script, "w", encoding="utf-8") as script_file:
        script_file.write(";\n".join(filter_lines))

    output_args = _ffmpeg_output_args(
        output_path, sample_rate, channels, total_duration
    )
    command = (
        f'ffmpeg -y -loglevel error {inputs} '
        f'-filter_complex_script "{filter_script}" -map "[out]" '
        f'{output_args} "{output_path}"'
    )
    try:
        run_command(command)
    finally:
        if os.path.exists(filter_script):
            os.remove(filter_script)


def _amix_existing_tracks(track_files, output_path, sample_rate, channels, duration_sec):
    if len(track_files) == 1:
        if os.path.abspath(track_files[0]) != os.path.abspath(output_path):
            os.replace(track_files[0], output_path)
        return

    inputs = " ".join(f'-i "{track_file}"' for track_file in track_files)
    mix_inputs = "".join(f"[{idx}:a]" for idx in range(len(track_files)))
    filter_complex = (
        f"{mix_inputs}amix=inputs={len(track_files)}:"
        f"duration=first:dropout_transition=0:normalize=0,"
        f"alimiter=limit=0.95:level=disabled[out]"
    )
    output_args = _ffmpeg_output_args(
        output_path, sample_rate, channels, duration_sec
    )
    command = (
        f'ffmpeg -y -loglevel error {inputs} -filter_complex "{filter_complex}" '
        f'-map "[out]" {output_args} "{output_path}"'
    )
    run_command(command)


def _mix_with_ffmpeg(
    segments,
    audio_files,
    output_path,
    total_duration,
    avoid_overlap,
):
    sample_rate = DEFAULT_SAMPLE_RATE
    channels = 1

    for audio_file in audio_files:
        try:
            sample_rate, channels, _ = _probe_audio(audio_file)
            break
        except Exception as error:
            logger.debug(str(error))

    starts = _compute_segment_starts(segments, audio_files, avoid_overlap)
    logger.debug(
        f"Audio duration: {int(total_duration) // 60} "
        f"minutes and {int(total_duration) % 60} seconds; "
        f"mixing {len(audio_files)} segments at {sample_rate} Hz"
    )

    estimated_bytes = _estimated_pcm_bytes(
        total_duration, sample_rate, channels
    )
    if estimated_bytes >= WAV_RF64_BYTE_THRESHOLD and output_path.lower().endswith(
        ".wav"
    ):
        logger.info(
            "Long output detected; writing RF64 WAV to avoid the 4 GB WAV limit"
        )

    if len(audio_files) <= FFMPEG_MIX_BATCH_SIZE:
        _mix_single_pass(
            starts,
            audio_files,
            output_path,
            total_duration,
            sample_rate,
            channels,
        )
        return

    batch_outputs = []
    try:
        for batch_index in range(0, len(audio_files), FFMPEG_MIX_BATCH_SIZE):
            batch_starts = starts[batch_index: batch_index + FFMPEG_MIX_BATCH_SIZE]
            batch_files = audio_files[batch_index: batch_index + FFMPEG_MIX_BATCH_SIZE]
            batch_output = f"_temp_dub_batch_{batch_index}.wav"
            _mix_single_pass(
                batch_starts,
                batch_files,
                batch_output,
                total_duration,
                sample_rate,
                channels,
            )
            batch_outputs.append(batch_output)

        _amix_existing_tracks(
            batch_outputs,
            output_path,
            sample_rate,
            channels,
            total_duration,
        )
    finally:
        for batch_output in batch_outputs:
            if os.path.exists(batch_output):
                os.remove(batch_output)


def create_translated_audio(
    result_diarize, audio_files, final_file, concat=False, avoid_overlap=False,
):
    total_duration = float(result_diarize["segments"][-1]["end"])

    if concat:
        with open("list.txt", "w", encoding="utf-8") as file:
            for index, audio_file in enumerate(audio_files):
                line = f"file {audio_file}"
                if index != len(audio_files) - 1:
                    line += "\n"
                file.write(line)

        output_args = _ffmpeg_output_args(
            final_file, DEFAULT_SAMPLE_RATE, 1, total_duration
        )
        command = (
            f'ffmpeg -y -loglevel error -f concat -safe 0 -i list.txt '
            f'{output_args} "{final_file}"'
        )
        run_command(command)
        return

    _mix_with_ffmpeg(
        result_diarize["segments"],
        audio_files,
        final_file,
        total_duration,
        avoid_overlap,
    )
