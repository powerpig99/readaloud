"""
TTS Engine wrapper for Qwen3-TTS using mlx-audio.
Handles model loading, generation, and voice cloning with native Apple Silicon optimization.
"""

import numpy as np
import soundfile as sf
import tempfile
import os
from typing import Optional, Tuple, List, Callable, Any
import librosa


# Global model cache
_model = None
_model_id = None
_clone_model = None
_clone_model_id = None

# Default speaker for CustomVoice model
DEFAULT_SPEAKER = "serena"


def _get_model_id(model_size: str, quantization: str, for_cloning: bool) -> str:
    """
    Get the mlx-community model ID based on size, quantization, and mode.

    Args:
        model_size: "0.6B" or "1.7B"
        quantization: "bf16" or "4bit"
        for_cloning: If True, use Base model; if False, use CustomVoice model

    Returns:
        Model ID string for mlx-community
    """
    model_type = "Base" if for_cloning else "CustomVoice"

    # Model mapping
    models = {
        ("0.6B", "bf16", False): "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-bf16",
        ("0.6B", "4bit", False): "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-4bit",
        ("1.7B", "bf16", False): "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-bf16",
        ("1.7B", "4bit", False): "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-4bit",
        ("0.6B", "bf16", True): "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-bf16",
        ("0.6B", "4bit", True): "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit",
        ("1.7B", "bf16", True): "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16",
        ("1.7B", "4bit", True): "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit",
    }

    key = (model_size, quantization, for_cloning)
    return models.get(key, models[("0.6B", "bf16", for_cloning)])


def load_model(model_size: str = "0.6B", quantization: str = "bf16", for_cloning: bool = False) -> Any:
    """
    Load the Qwen3-TTS model via mlx-audio. Downloads on first use.

    Args:
        model_size: "0.6B" or "1.7B"
        quantization: "bf16" (best quality) or "4bit" (faster)
        for_cloning: If True, load Base model for voice cloning;
                     If False, load CustomVoice model for default voices

    Returns:
        The loaded model
    """
    global _model, _model_id, _clone_model, _clone_model_id

    # Import here to avoid startup delay
    from mlx_audio.tts.utils import load_model as mlx_load_model

    model_id = _get_model_id(model_size, quantization, for_cloning)

    if for_cloning:
        if _clone_model is not None and _clone_model_id == model_id:
            return _clone_model

        print(f"Loading clone model: {model_id}")
        _clone_model = mlx_load_model(model_id)
        _clone_model_id = model_id
        print("Clone model loaded successfully")
        return _clone_model
    else:
        if _model is not None and _model_id == model_id:
            return _model

        print(f"Loading model: {model_id}")
        _model = mlx_load_model(model_id)
        _model_id = model_id
        print("Model loaded successfully")
        return _model


def generate_speech(
    text: str,
    language: str = "english",
    model_size: str = "0.6B",
    quantization: str = "bf16",
    speaker: str = DEFAULT_SPEAKER,
) -> Tuple[np.ndarray, int]:
    """
    Generate speech from text using default voice.

    Args:
        text: Text to convert to speech
        language: Target language (lowercase)
        model_size: Model size to use
        quantization: "bf16" or "4bit"
        speaker: Speaker name (aiden, dylan, eric, ono_anna, ryan, serena, sohee, uncle_fu, vivian)

    Returns:
        Tuple of (audio_array, sample_rate)
    """
    model = load_model(model_size, quantization, for_cloning=False)

    # Generate using mlx-audio's generate method
    # The model.generate() returns a generator of results
    results = list(model.generate(
        text=text,
        voice=speaker,
        language=language.capitalize(),  # mlx-audio expects capitalized language
    ))

    if results:
        # Convert mx.array to numpy
        audio_mx = results[0].audio
        audio_np = np.array(audio_mx, dtype=np.float32)
        # mlx-audio Qwen3-TTS outputs at 24kHz
        sample_rate = 24000
        return audio_np, sample_rate

    return np.array([]), 24000


def create_voice_clone_prompt(
    ref_audio_path: str,
    ref_transcript: str,
    model_size: str = "0.6B",
    quantization: str = "bf16",
) -> Any:
    """
    Create a voice clone prompt from reference audio.

    Args:
        ref_audio_path: Path to reference audio file
        ref_transcript: Exact transcript of reference audio
        model_size: Model size to use
        quantization: "bf16" or "4bit"

    Returns:
        Voice clone prompt object for use in generation (the model itself with reference loaded)
    """
    model = load_model(model_size, quantization, for_cloning=True)

    # Load reference audio and resample to 24kHz if needed
    ref_wav, ref_sr = librosa.load(ref_audio_path, sr=24000)

    # For mlx-audio, we return a dict with the reference info
    # The generate_speech_with_clone function will use this
    return {
        'ref_audio': ref_wav,
        'ref_sr': ref_sr,
        'ref_text': ref_transcript.strip(),
        'model_size': model_size,
        'quantization': quantization,
    }


def generate_speech_with_clone(
    text: str,
    voice_prompt: dict,
    language: str = "english",
    model_size: str = "0.6B",
    quantization: str = "bf16",
) -> Tuple[np.ndarray, int]:
    """
    Generate speech using a cloned voice.

    Args:
        text: Text to convert to speech
        voice_prompt: Voice clone prompt from create_voice_clone_prompt
        language: Target language (lowercase)
        model_size: Model size to use
        quantization: "bf16" or "4bit"

    Returns:
        Tuple of (audio_array, sample_rate)
    """
    # Use model_size/quantization from voice_prompt if available
    size = voice_prompt.get('model_size', model_size)
    quant = voice_prompt.get('quantization', quantization)

    model = load_model(size, quant, for_cloning=True)

    # Generate using voice cloning
    results = list(model.generate(
        text=text,
        language=language.capitalize(),
        audio=voice_prompt['ref_audio'],
        ref_text=voice_prompt['ref_text'],
    ))

    if results:
        audio_mx = results[0].audio
        audio_np = np.array(audio_mx, dtype=np.float32)
        sample_rate = 24000
        return audio_np, sample_rate

    return np.array([]), 24000


def generate_long_text(
    chunks: List[str],
    language: str = "english",
    model_size: str = "0.6B",
    voice_prompt: Optional[dict] = None,
    speaker: str = DEFAULT_SPEAKER,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    quantization: str = "bf16",
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
        quantization: "bf16" or "4bit"

    Returns:
        Tuple of (concatenated_audio_array, sample_rate)
    """
    all_wavs = []
    sample_rate = 24000  # mlx-audio Qwen3-TTS outputs at 24kHz

    for i, chunk in enumerate(chunks):
        if progress_callback:
            progress_callback(i, len(chunks))

        if voice_prompt is not None:
            wav, sr = generate_speech_with_clone(
                text=chunk,
                voice_prompt=voice_prompt,
                language=language.lower(),
                model_size=model_size,
                quantization=quantization,
            )
        else:
            wav, sr = generate_speech(
                text=chunk,
                language=language.lower(),
                model_size=model_size,
                quantization=quantization,
                speaker=speaker,
            )

        if sr != sample_rate:
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
    quantization: str = "bf16",
    voice_prompt: Optional[dict] = None,
    speaker: str = DEFAULT_SPEAKER,
) -> str:
    """
    Convenience function to generate speech and save to file.

    Args:
        text: Text to convert
        output_path: Output path (auto-generated if None)
        language: Target language
        model_size: Model size
        quantization: "bf16" or "4bit"
        voice_prompt: Optional voice clone prompt
        speaker: Speaker name for default voice

    Returns:
        Path to generated audio file
    """
    if voice_prompt is not None:
        wav, sr = generate_speech_with_clone(text, voice_prompt, language, model_size, quantization)
    else:
        wav, sr = generate_speech(text, language, model_size, quantization, speaker)

    if output_path is None:
        output_path = tempfile.mktemp(suffix=".wav")

    return save_audio(wav, sr, output_path)
