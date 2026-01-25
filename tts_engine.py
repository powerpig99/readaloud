"""
TTS Engine wrapper for Qwen3-TTS.
Handles model loading, generation, and voice cloning.
"""

import torch
import numpy as np
import soundfile as sf
import tempfile
import os
from typing import Optional, Tuple, List, Callable, Any
import librosa


# Global model cache
_model = None
_model_name = None
_clone_model = None
_clone_model_name = None

# Default speaker for CustomVoice model
DEFAULT_SPEAKER = "serena"


def get_device():
    """Determine the best available device."""
    if torch.cuda.is_available():
        return "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def get_dtype():
    """Determine the best dtype for the device."""
    device = get_device()
    if device == "cuda":
        return torch.bfloat16
    return torch.float32


def load_model(model_size: str = "0.6B", for_cloning: bool = False) -> Any:
    """
    Load the Qwen3-TTS model. Downloads on first use.

    Args:
        model_size: "0.6B" or "1.7B"
        for_cloning: If True, load Base model for voice cloning;
                     If False, load CustomVoice model for default voices

    Returns:
        The loaded model
    """
    global _model, _model_name, _clone_model, _clone_model_name

    # Import here to avoid startup delay
    from qwen_tts import Qwen3TTSModel

    if for_cloning:
        # Base model for voice cloning
        model_map = {
            "0.6B": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
            "1.7B": "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
        }
        model_name = model_map.get(model_size, model_map["0.6B"])

        if _clone_model is not None and _clone_model_name == model_name:
            return _clone_model

        print(f"Loading clone model: {model_name}")
        print(f"Device: {get_device()}, dtype: {get_dtype()}")

        _clone_model = Qwen3TTSModel.from_pretrained(model_name)
        _clone_model_name = model_name
        print("Clone model loaded successfully")
        return _clone_model
    else:
        # CustomVoice model for default speakers
        model_map = {
            "0.6B": "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
            "1.7B": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
        }
        model_name = model_map.get(model_size, model_map["0.6B"])

        if _model is not None and _model_name == model_name:
            return _model

        print(f"Loading model: {model_name}")
        print(f"Device: {get_device()}, dtype: {get_dtype()}")

        _model = Qwen3TTSModel.from_pretrained(model_name)
        _model_name = model_name
        print("Model loaded successfully")
        return _model


def generate_speech(
    text: str,
    language: str = "english",
    model_size: str = "0.6B",
    speaker: str = DEFAULT_SPEAKER,
) -> Tuple[np.ndarray, int]:
    """
    Generate speech from text using default voice.

    Args:
        text: Text to convert to speech
        language: Target language (lowercase)
        model_size: Model size to use
        speaker: Speaker name (aiden, dylan, eric, ono_anna, ryan, serena, sohee, uncle_fu, vivian)

    Returns:
        Tuple of (audio_array, sample_rate)
    """
    model = load_model(model_size, for_cloning=False)

    # Generate using CustomVoice model
    wavs, sr = model.generate_custom_voice(
        text=text,
        speaker=speaker,
        language=language.lower(),
    )

    # wavs is a list, return first item
    return wavs[0] if wavs else np.array([]), sr


def create_voice_clone_prompt(
    ref_audio_path: str,
    ref_transcript: str,
    model_size: str = "0.6B",
) -> List[Any]:
    """
    Create a voice clone prompt from reference audio.

    Args:
        ref_audio_path: Path to reference audio file
        ref_transcript: Exact transcript of reference audio
        model_size: Model size to use

    Returns:
        Voice clone prompt object for use in generation
    """
    model = load_model(model_size, for_cloning=True)

    # Load reference audio
    ref_wav, ref_sr = librosa.load(ref_audio_path, sr=None)

    voice_prompt = model.create_voice_clone_prompt(
        ref_audio=(ref_wav, ref_sr),
        ref_text=ref_transcript.strip(),
    )

    return voice_prompt


def generate_speech_with_clone(
    text: str,
    voice_prompt: List[Any],
    language: str = "english",
    model_size: str = "0.6B",
) -> Tuple[np.ndarray, int]:
    """
    Generate speech using a cloned voice.

    Args:
        text: Text to convert to speech
        voice_prompt: Voice clone prompt from create_voice_clone_prompt
        language: Target language (lowercase)
        model_size: Model size to use

    Returns:
        Tuple of (audio_array, sample_rate)
    """
    model = load_model(model_size, for_cloning=True)

    wavs, sr = model.generate_voice_clone(
        text=text,
        language=language.lower(),
        voice_clone_prompt=voice_prompt,
    )

    # wavs is a list, return first item
    return wavs[0] if wavs else np.array([]), sr


def generate_long_text(
    chunks: List[str],
    language: str = "english",
    model_size: str = "0.6B",
    voice_prompt: Optional[List[Any]] = None,
    speaker: str = DEFAULT_SPEAKER,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Tuple[np.ndarray, int]:
    """
    Generate speech for multiple text chunks and concatenate.

    Args:
        chunks: List of text chunks
        language: Target language
        model_size: Model size to use
        voice_prompt: Optional voice clone prompt
        speaker: Speaker name for default voice
        progress_callback: Optional callback(current, total) for progress updates

    Returns:
        Tuple of (concatenated_audio_array, sample_rate)
    """
    all_wavs = []
    sample_rate = None

    for i, chunk in enumerate(chunks):
        if progress_callback:
            progress_callback(i, len(chunks))

        if voice_prompt is not None:
            wav, sr = generate_speech_with_clone(
                text=chunk,
                voice_prompt=voice_prompt,
                language=language.lower(),
                model_size=model_size,
            )
        else:
            wav, sr = generate_speech(
                text=chunk,
                language=language.lower(),
                model_size=model_size,
                speaker=speaker,
            )

        if sample_rate is None:
            sample_rate = sr

        all_wavs.append(wav)

    if progress_callback:
        progress_callback(len(chunks), len(chunks))

    # Concatenate all audio
    if all_wavs:
        full_wav = np.concatenate(all_wavs)
    else:
        full_wav = np.array([])

    return full_wav, sample_rate


def save_audio(
    wav: np.ndarray,
    sample_rate: int,
    output_path: str,
) -> str:
    """
    Save audio array to file.

    Args:
        wav: Audio array
        sample_rate: Sample rate
        output_path: Output file path

    Returns:
        Path to saved file
    """
    sf.write(output_path, wav, sample_rate)
    return output_path


def generate_to_file(
    text: str,
    output_path: Optional[str] = None,
    language: str = "english",
    model_size: str = "0.6B",
    voice_prompt: Optional[List[Any]] = None,
    speaker: str = DEFAULT_SPEAKER,
) -> str:
    """
    Convenience function to generate speech and save to file.

    Args:
        text: Text to convert
        output_path: Output path (auto-generated if None)
        language: Target language
        model_size: Model size
        voice_prompt: Optional voice clone prompt
        speaker: Speaker name for default voice

    Returns:
        Path to generated audio file
    """
    if voice_prompt is not None:
        wav, sr = generate_speech_with_clone(text, voice_prompt, language, model_size)
    else:
        wav, sr = generate_speech(text, language, model_size, speaker)

    if output_path is None:
        output_path = tempfile.mktemp(suffix=".wav")

    return save_audio(wav, sr, output_path)
