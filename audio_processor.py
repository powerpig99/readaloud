"""
Audio processing utilities for ReadAloud.
Handles speed adjustment, format conversion, and audio manipulation.
"""

import numpy as np
import soundfile as sf
import tempfile
from pydub import AudioSegment
from typing import Optional
import os


def adjust_speed(
    input_path: str,
    speed_factor: float,
    output_path: Optional[str] = None,
) -> str:
    """
    Adjust audio playback speed.

    Args:
        input_path: Path to input audio file
        speed_factor: Speed multiplier (0.5 = half speed, 2.0 = double speed)
        output_path: Output path (auto-generated if None)

    Returns:
        Path to speed-adjusted audio file
    """
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".wav")

    # Load audio
    audio = AudioSegment.from_file(input_path)

    # Adjust speed by changing frame rate then resampling
    # This changes speed without changing pitch significantly
    new_frame_rate = int(audio.frame_rate * speed_factor)
    adjusted = audio._spawn(audio.raw_data, overrides={
        "frame_rate": new_frame_rate
    }).set_frame_rate(audio.frame_rate)

    # Export
    adjusted.export(output_path, format="wav")

    return output_path


def convert_format(
    input_path: str,
    output_format: str = "mp3",
    output_path: Optional[str] = None,
) -> str:
    """
    Convert audio to different format.

    Args:
        input_path: Path to input audio file
        output_format: Target format (mp3, wav, ogg, etc.)
        output_path: Output path (auto-generated if None)

    Returns:
        Path to converted audio file
    """
    if output_path is None:
        output_path = tempfile.mktemp(suffix=f".{output_format}")

    audio = AudioSegment.from_file(input_path)
    audio.export(output_path, format=output_format)

    return output_path


def get_audio_duration(file_path: str) -> float:
    """
    Get duration of audio file in seconds.

    Args:
        file_path: Path to audio file

    Returns:
        Duration in seconds
    """
    audio = AudioSegment.from_file(file_path)
    return len(audio) / 1000.0


def normalize_audio(
    input_path: str,
    target_dbfs: float = -20.0,
    output_path: Optional[str] = None,
) -> str:
    """
    Normalize audio to target volume level.

    Args:
        input_path: Path to input audio file
        target_dbfs: Target volume in dBFS
        output_path: Output path (auto-generated if None)

    Returns:
        Path to normalized audio file
    """
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".wav")

    audio = AudioSegment.from_file(input_path)
    change_in_dbfs = target_dbfs - audio.dBFS
    normalized = audio.apply_gain(change_in_dbfs)
    normalized.export(output_path, format="wav")

    return output_path


def concatenate_audio_files(
    file_paths: list,
    output_path: Optional[str] = None,
    crossfade_ms: int = 50,
) -> str:
    """
    Concatenate multiple audio files with optional crossfade.

    Args:
        file_paths: List of audio file paths
        output_path: Output path (auto-generated if None)
        crossfade_ms: Crossfade duration in milliseconds (0 for no crossfade)

    Returns:
        Path to concatenated audio file
    """
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".wav")

    if not file_paths:
        raise ValueError("No files to concatenate")

    combined = AudioSegment.from_file(file_paths[0])

    for path in file_paths[1:]:
        segment = AudioSegment.from_file(path)
        if crossfade_ms > 0:
            combined = combined.append(segment, crossfade=crossfade_ms)
        else:
            combined += segment

    combined.export(output_path, format="wav")

    return output_path


def trim_silence(
    input_path: str,
    silence_threshold: int = -50,
    chunk_size: int = 10,
    output_path: Optional[str] = None,
) -> str:
    """
    Remove silence from beginning and end of audio.

    Args:
        input_path: Path to input audio file
        silence_threshold: Volume threshold for silence (dBFS)
        chunk_size: Analysis chunk size in ms
        output_path: Output path (auto-generated if None)

    Returns:
        Path to trimmed audio file
    """
    from pydub.silence import detect_leading_silence

    if output_path is None:
        output_path = tempfile.mktemp(suffix=".wav")

    audio = AudioSegment.from_file(input_path)

    # Trim leading silence
    start_trim = detect_leading_silence(audio, silence_threshold, chunk_size)

    # Trim trailing silence
    end_trim = detect_leading_silence(audio.reverse(), silence_threshold, chunk_size)

    trimmed = audio[start_trim:len(audio) - end_trim]
    trimmed.export(output_path, format="wav")

    return output_path
