"""
Audio-text alignment using WhisperX.
Provides word-level timing for karaoke-style highlighting.
"""

import json
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import re

# Lazy-loaded models
_whisper_model = None
_align_model = None
_align_metadata = None


def load_alignment_models(
    model_size: str = "base",
    device: str = "auto",
    compute_type: str = "auto",
) -> None:
    """
    Lazy load WhisperX models for alignment.

    Args:
        model_size: Whisper model size (tiny, base, small, medium, large-v2)
        device: Device to use (auto, cuda, cpu)
        compute_type: Compute type (auto, float16, int8)
    """
    global _whisper_model, _align_model, _align_metadata

    if _whisper_model is not None:
        return

    import torch
    import whisperx

    # Auto-detect device
    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "cpu"  # WhisperX doesn't fully support MPS
        else:
            device = "cpu"

    # Auto-detect compute type
    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"

    print(f"Loading WhisperX model: {model_size} on {device} with {compute_type}")

    # Load whisper model
    _whisper_model = whisperx.load_model(
        model_size,
        device,
        compute_type=compute_type,
    )

    print("WhisperX model loaded")


def _load_alignment_model(language: str = "en", device: str = "auto"):
    """Load alignment model for specific language."""
    global _align_model, _align_metadata

    import torch
    import whisperx

    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"

    _align_model, _align_metadata = whisperx.load_align_model(
        language_code=language,
        device=device,
    )

    return _align_model, _align_metadata


def align_audio_with_text(
    audio_path: str,
    sentences: List[Dict[str, Any]],
    language: str = "en",
) -> Dict[str, Any]:
    """
    Align audio with text to get word-level timing.

    Args:
        audio_path: Path to audio file
        sentences: List of sentence dicts with 'text' and 'index' keys
        language: Language code (en, zh, ja, etc.)

    Returns:
        Timing data with word-level timestamps for each sentence
    """
    import whisperx

    # Load models if needed
    load_alignment_models()

    # Load audio
    audio = whisperx.load_audio(audio_path)

    # Transcribe with Whisper
    print("Transcribing audio...")
    result = _whisper_model.transcribe(audio, batch_size=16)

    # Load alignment model for language
    print(f"Loading alignment model for {language}...")
    align_model, align_metadata = _load_alignment_model(language)

    # Align
    print("Aligning transcription...")
    result = whisperx.align(
        result["segments"],
        align_model,
        align_metadata,
        audio,
        device=align_model.device if hasattr(align_model, 'device') else "cpu",
        return_char_alignments=False,
    )

    # Get audio duration
    import soundfile as sf
    info = sf.info(audio_path)
    audio_duration = info.duration

    # Map Whisper output to original sentences
    timing_data = map_words_to_sentences(result, sentences, audio_duration)

    return timing_data


def map_words_to_sentences(
    whisper_result: Dict[str, Any],
    sentences: List[Dict[str, Any]],
    audio_duration: float,
) -> Dict[str, Any]:
    """
    Map Whisper's word-level output to original text sentences.

    Args:
        whisper_result: WhisperX alignment result
        sentences: Original sentences with indices
        audio_duration: Total audio duration in seconds

    Returns:
        Timing data structure with sentences and word timings
    """
    # Extract all words with timing from Whisper
    all_words = []
    for segment in whisper_result.get("segments", []):
        for word_data in segment.get("words", []):
            if "start" in word_data and "end" in word_data:
                all_words.append({
                    "word": word_data.get("word", "").strip(),
                    "start": word_data["start"],
                    "end": word_data["end"],
                    "confidence": word_data.get("score", 0.9),
                })

    # Build timing for each sentence
    timing_sentences = []
    word_idx = 0

    for sent in sentences:
        sent_text = sent["text"]
        sent_index = sent["index"]

        # Extract words from sentence text
        sent_words = _extract_words(sent_text)

        # Find matching words in Whisper output
        matched_words = []
        sent_start = None
        sent_end = None

        for sent_word in sent_words:
            # Try to find a matching word in the remaining Whisper words
            best_match = None
            best_match_idx = None

            # Search in a window around current position
            search_start = max(0, word_idx - 5)
            search_end = min(len(all_words), word_idx + len(sent_words) + 10)

            for i in range(search_start, search_end):
                if i >= len(all_words):
                    break
                whisper_word = all_words[i]["word"].lower().strip(".,!?;:'\"")
                if _words_match(sent_word.lower(), whisper_word):
                    best_match = all_words[i]
                    best_match_idx = i
                    break

            if best_match:
                word_timing = {
                    "word": sent_word,
                    "start": best_match["start"],
                    "end": best_match["end"],
                    "confidence": best_match["confidence"],
                }
                matched_words.append(word_timing)

                if sent_start is None:
                    sent_start = best_match["start"]
                sent_end = best_match["end"]

                word_idx = best_match_idx + 1
            else:
                # No match found, will interpolate later
                matched_words.append({
                    "word": sent_word,
                    "start": None,
                    "end": None,
                    "confidence": 0.0,
                })

        # Set sentence timing
        if sent_start is None:
            # Estimate based on sentence index
            if timing_sentences:
                sent_start = timing_sentences[-1]["end"]
            else:
                sent_start = 0.0

        if sent_end is None:
            sent_end = sent_start + 2.0  # Default 2 second estimate

        timing_sentences.append({
            "sentence_index": sent_index,
            "text": sent_text,
            "start": sent_start,
            "end": sent_end,
            "words": matched_words,
        })

    # Interpolate missing timestamps
    timing_sentences = interpolate_missing_timestamps(timing_sentences, audio_duration)

    return {
        "version": "1.0",
        "audio_duration": audio_duration,
        "sentences": timing_sentences,
    }


def _extract_words(text: str) -> List[str]:
    """Extract words from text, preserving original form."""
    # Split on whitespace and punctuation boundaries, keeping words intact
    words = re.findall(r'\b[\w\']+\b', text)
    return words


def _words_match(word1: str, word2: str) -> bool:
    """Check if two words match (fuzzy)."""
    # Direct match
    if word1 == word2:
        return True

    # Strip common suffixes/prefixes
    w1 = word1.strip(".,!?;:'\"()-")
    w2 = word2.strip(".,!?;:'\"()-")

    if w1 == w2:
        return True

    # Check if one contains the other (for contractions etc)
    if len(w1) > 2 and len(w2) > 2:
        if w1 in w2 or w2 in w1:
            return True

    return False


def interpolate_missing_timestamps(
    sentences: List[Dict[str, Any]],
    audio_duration: float,
) -> List[Dict[str, Any]]:
    """
    Fill in missing word timestamps using linear interpolation.

    Args:
        sentences: List of sentence timing dicts
        audio_duration: Total audio duration

    Returns:
        Sentences with interpolated timestamps
    """
    for sent in sentences:
        words = sent["words"]
        if not words:
            continue

        # Find indices of words with known timing
        known_indices = []
        known_times = []

        for i, w in enumerate(words):
            if w["start"] is not None:
                known_indices.append(i)
                known_times.append((w["start"], w["end"]))

        if not known_indices:
            # No known times, distribute evenly within sentence
            sent_start = sent["start"]
            sent_end = sent["end"]
            word_duration = (sent_end - sent_start) / len(words)

            for i, w in enumerate(words):
                w["start"] = sent_start + i * word_duration
                w["end"] = sent_start + (i + 1) * word_duration
                w["confidence"] = 0.5  # Mark as interpolated
            continue

        # Interpolate gaps
        for i, w in enumerate(words):
            if w["start"] is not None:
                continue

            # Find surrounding known points
            prev_idx = None
            next_idx = None

            for ki in known_indices:
                if ki < i:
                    prev_idx = ki
                elif ki > i and next_idx is None:
                    next_idx = ki
                    break

            if prev_idx is not None and next_idx is not None:
                # Interpolate between two known points
                prev_end = words[prev_idx]["end"]
                next_start = words[next_idx]["start"]
                gap_words = next_idx - prev_idx - 1
                word_duration = (next_start - prev_end) / (gap_words + 1)
                offset = i - prev_idx
                w["start"] = prev_end + (offset - 0.5) * word_duration
                w["end"] = prev_end + (offset + 0.5) * word_duration
            elif prev_idx is not None:
                # Extrapolate forward
                prev_word = words[prev_idx]
                avg_duration = prev_word["end"] - prev_word["start"]
                offset = i - prev_idx
                w["start"] = prev_word["end"] + (offset - 1) * avg_duration
                w["end"] = w["start"] + avg_duration
            elif next_idx is not None:
                # Extrapolate backward
                next_word = words[next_idx]
                avg_duration = next_word["end"] - next_word["start"]
                offset = next_idx - i
                w["end"] = next_word["start"] - (offset - 1) * avg_duration
                w["start"] = w["end"] - avg_duration

            w["confidence"] = 0.5  # Mark as interpolated

        # Ensure no negative times and within bounds
        for w in words:
            w["start"] = max(0, min(w["start"], audio_duration))
            w["end"] = max(w["start"], min(w["end"], audio_duration))

    return sentences


def create_simple_timing(
    sentences: List[Dict[str, Any]],
    audio_duration: float,
    words_per_minute: int = 150,
) -> Dict[str, Any]:
    """
    Create simple timing estimates without alignment (fallback).

    Uses estimated speaking rate to assign timestamps.

    Args:
        sentences: List of sentence dicts with 'text' and 'index'
        audio_duration: Total audio duration
        words_per_minute: Estimated speaking rate

    Returns:
        Timing data structure
    """
    # Calculate total words
    total_words = sum(len(_extract_words(s["text"])) for s in sentences)

    if total_words == 0:
        return {
            "version": "1.0",
            "audio_duration": audio_duration,
            "sentences": [],
        }

    # Time per word
    time_per_word = audio_duration / total_words

    timing_sentences = []
    current_time = 0.0

    for sent in sentences:
        words = _extract_words(sent["text"])
        sent_duration = len(words) * time_per_word

        word_timings = []
        for i, word in enumerate(words):
            word_start = current_time + i * time_per_word
            word_end = word_start + time_per_word
            word_timings.append({
                "word": word,
                "start": word_start,
                "end": word_end,
                "confidence": 0.3,  # Low confidence for estimates
            })

        timing_sentences.append({
            "sentence_index": sent["index"],
            "text": sent["text"],
            "start": current_time,
            "end": current_time + sent_duration,
            "words": word_timings,
        })

        current_time += sent_duration

    return {
        "version": "1.0",
        "audio_duration": audio_duration,
        "sentences": timing_sentences,
    }


def align_or_estimate(
    audio_path: str,
    sentences: List[Dict[str, Any]],
    language: str = "en",
    use_whisper: bool = True,
) -> Dict[str, Any]:
    """
    Try WhisperX alignment, fall back to estimation if it fails.

    Args:
        audio_path: Path to audio file
        sentences: List of sentence dicts
        language: Language code
        use_whisper: Whether to try WhisperX first

    Returns:
        Timing data
    """
    if use_whisper:
        try:
            return align_audio_with_text(audio_path, sentences, language)
        except Exception as e:
            print(f"WhisperX alignment failed: {e}")
            print("Falling back to estimation...")

    # Fallback to simple estimation
    import soundfile as sf
    info = sf.info(audio_path)
    return create_simple_timing(sentences, info.duration)
