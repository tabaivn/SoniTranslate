from .utils import (
    ffmpeg_command,
    ffprobe_command,
    remove_files,
    run_subprocess,
    yt_dlp_command,
)
import os
import shutil
import time
import json
from .logging_setup import logger

ERROR_INCORRECT_CODEC_PARAMETERS = [
    "prores",  # mov
    "ffv1",  # mkv
    "msmpeg4v3",  # avi
    "wmv2",  # wmv
    "theora",  # ogv
]  # fix final merge

TESTED_CODECS = [
    "h264",  # mp4
    "h265",  # mp4
    "hevc",
    "vp9",  # webm
    "mpeg4",  # mp4
    "mpeg2video",  # mpg
    "mjpeg",  # avi
]

_YT_DLP_COMMON_ARGS = (
    "--force-overwrites",
    "--max-downloads",
    "1",
    "--no-warnings",
    "--no-playlist",
    "--no-abort-on-error",
    "--ignore-no-formats-error",
)


class OperationFailedError(Exception):
    def __init__(self, message="The operation did not complete successfully."):
        self.message = message
        super().__init__(self.message)


def _yt_dlp_download_mp4_cmd(output_file, video_url, preview=False):
    args = ["-f", "mp4", *_YT_DLP_COMMON_ARGS, "--restrict-filenames", "-o", output_file]
    if preview:
        args[1:1] = [
            "--downloader",
            "ffmpeg",
            "--downloader-args",
            "ffmpeg_i: -ss 00:00:20 -t 00:00:10",
        ]
    args.append(video_url)
    return yt_dlp_command(*args)


def _yt_dlp_download_audio_wav_cmd(audio_wav, video_url):
    return yt_dlp_command(
        "--output",
        audio_wav,
        *_YT_DLP_COMMON_ARGS,
        "-x",
        "--audio-format",
        "wav",
        video_url,
    )


def _ffmpeg_extract_wav_from_mp4_cmd(input_mp4="Video.mp4", output_wav="audio.wav"):
    return ffmpeg_command(
        "-y",
        "-i",
        input_mp4,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "44100",
        "-ac",
        "2",
        output_wav,
    )


def get_video_codec(video_file):
    command = ffprobe_command(
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name",
        "-of",
        "json",
        video_file,
    )
    try:
        process, output, _ = run_subprocess(command)
        if process.returncode != 0:
            return None
        codec_info = json.loads(output.decode("utf-8"))
        codec_name = codec_info["streams"][0]["codec_name"]
        return codec_name
    except Exception as error:
        logger.debug(str(error))
        return None


def audio_preprocessor(preview, base_audio, audio_wav, use_cuda=False):
    base_audio = base_audio.strip()
    remove_files([audio_wav])

    if preview:
        logger.warning(
            "Creating a preview video of 10 seconds, to disable "
            "this option, go to advanced settings and turn off preview."
        )
        wav_cmd = ffmpeg_command(
            "-y",
            "-i",
            base_audio,
            "-ss",
            "00:00:20",
            "-t",
            "00:00:10",
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "44100",
            "-ac",
            "2",
            audio_wav,
        )
    else:
        wav_cmd = ffmpeg_command(
            "-y",
            "-i",
            base_audio,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "44100",
            "-ac",
            "2",
            audio_wav,
        )

    result_convert_audio, output, errors = run_subprocess(wav_cmd)
    time.sleep(1)
    if result_convert_audio.returncode in [1, 2] or not os.path.exists(audio_wav):
        raise OperationFailedError(
            f"Error can't create the audio file:\n{errors.decode('utf-8')}"
        )


def _run_media_command(command):
    process, _, errors = run_subprocess(command)
    return process, errors


def audio_video_preprocessor(
    preview, video, OutputFile, audio_wav, use_cuda=False
):
    video = video.strip()
    remove_files([OutputFile, "audio.webm", audio_wav])

    if os.path.exists(video):
        if preview:
            logger.warning(
                "Creating a preview video of 10 seconds, "
                "to disable this option, go to advanced "
                "settings and turn off preview."
            )
            mp4_cmd = ffmpeg_command(
                "-y",
                "-i",
                video,
                "-ss",
                "00:00:20",
                "-t",
                "00:00:10",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-strict",
                "experimental",
                "Video.mp4",
            )
        else:
            video_codec = get_video_codec(video)
            if not video_codec:
                logger.debug("No video codec found in video")
            else:
                logger.info(f"Video codec: {video_codec}")

            if video.endswith(".mp4") or video_codec in TESTED_CODECS:
                destination_path = os.path.join(os.getcwd(), "Video.mp4")
                shutil.copy(video, destination_path)
                time.sleep(0.5)
                if os.path.exists(OutputFile):
                    mp4_cmd = ffmpeg_command("-h")
                else:
                    mp4_cmd = ffmpeg_command("-y", "-i", video, "-c", "copy", "Video.mp4")
            else:
                logger.warning(
                    "File does not have the '.mp4' extension  or a "
                    "supported codec. Converting video to mp4 (codec: h264)."
                )
                mp4_cmd = ffmpeg_command(
                    "-y",
                    "-i",
                    video,
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-strict",
                    "experimental",
                    "Video.mp4",
                )

        logger.info("Process video...")
        result_convert_video, errors = _run_media_command(mp4_cmd)
        time.sleep(1)
        if result_convert_video.returncode in [1, 2] or not os.path.exists(OutputFile):
            raise OperationFailedError(
                f"Error processing video:\n{errors.decode('utf-8')}"
            )

        logger.info("Process audio...")
        wav_cmd = _ffmpeg_extract_wav_from_mp4_cmd(output_wav=audio_wav)
        result_convert_audio, errors = _run_media_command(wav_cmd)
        time.sleep(1)
        if result_convert_audio.returncode in [1, 2] or not os.path.exists(audio_wav):
            raise OperationFailedError(
                f"Error can't create the audio file:\n{errors.decode('utf-8')}"
            )
        return

    mp4_cmd = _yt_dlp_download_mp4_cmd(OutputFile, video, preview=preview)
    if preview:
        wav_cmd = _ffmpeg_extract_wav_from_mp4_cmd(output_wav=audio_wav)
        result_convert_video, errors = _run_media_command(mp4_cmd)
        time.sleep(0.5)
        result_convert_audio, errors = _run_media_command(wav_cmd)
        time.sleep(0.5)
        if result_convert_audio.returncode in [1, 2] or not os.path.exists(audio_wav):
            raise OperationFailedError(
                f"Error can't create the preview file:\n{errors.decode('utf-8')}"
            )
        return

    logger.info("Process audio...")
    wav_cmd = _yt_dlp_download_audio_wav_cmd(audio_wav, video)
    result_convert_audio, errors = _run_media_command(wav_cmd)
    time.sleep(1)
    if result_convert_audio.returncode in [1, 2] or not os.path.exists(audio_wav):
        raise OperationFailedError(
            f"Error can't download the audio:\n{errors.decode('utf-8')}"
        )

    logger.info("Process video...")
    result_convert_video, errors = _run_media_command(mp4_cmd)
    time.sleep(1)
    if result_convert_video.returncode in [1, 2] or not os.path.exists(OutputFile):
        raise OperationFailedError(
            f"Error can't download the video:\n{errors.decode('utf-8')}"
        )


def old_audio_video_preprocessor(preview, video, OutputFile, audio_wav):
    audio_video_preprocessor(preview, video, OutputFile, audio_wav)
