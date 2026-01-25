"""
Real-time synchronization calculations for karaoke display.
Handles playback position mapping and speed adjustments.
"""

from typing import Dict, List, Any, Optional, Tuple


def get_display_state(
    timing_data: Dict[str, Any],
    playback_time: float,
    speed: float = 1.0,
) -> Dict[str, Any]:
    """
    Calculate the current display state for karaoke highlighting.

    Args:
        timing_data: Timing data from alignment
        playback_time: Current audio playback time in seconds
        speed: Playback speed multiplier (1.0 = normal)

    Returns:
        Display state with current sentence, word, and progress info
    """
    sentences = timing_data.get("sentences", [])
    audio_duration = timing_data.get("audio_duration", 0)

    if not sentences:
        return {
            "current_sentence_index": None,
            "current_word_index": None,
            "previous_sentence": None,
            "current_sentence": None,
            "next_sentence": None,
            "sentence_progress": 0.0,
            "word_progress": 0.0,
            "total_progress": 0.0,
        }

    # Adjust time for speed (timing data is at 1x, but we're playing at speed x)
    # No adjustment needed - playback_time is actual audio time
    current_time = playback_time

    # Find current sentence
    current_sent_idx = None
    for i, sent in enumerate(sentences):
        if sent["start"] <= current_time < sent["end"]:
            current_sent_idx = i
            break

    # If between sentences or at end, find nearest
    if current_sent_idx is None:
        if current_time < sentences[0]["start"]:
            current_sent_idx = 0
        elif current_time >= sentences[-1]["end"]:
            current_sent_idx = len(sentences) - 1
        else:
            # Find the sentence that just ended
            for i, sent in enumerate(sentences):
                if current_time >= sent["end"]:
                    if i + 1 < len(sentences) and current_time < sentences[i + 1]["start"]:
                        current_sent_idx = i + 1
                        break
            if current_sent_idx is None:
                current_sent_idx = 0

    # Get current sentence
    current_sent = sentences[current_sent_idx]

    # Calculate sentence progress
    sent_duration = current_sent["end"] - current_sent["start"]
    if sent_duration > 0:
        sentence_progress = (current_time - current_sent["start"]) / sent_duration
        sentence_progress = max(0.0, min(1.0, sentence_progress))
    else:
        sentence_progress = 0.0

    # Find current word within sentence
    current_word_idx = None
    word_progress = 0.0
    words = current_sent.get("words", [])

    for i, word in enumerate(words):
        if word["start"] <= current_time < word["end"]:
            current_word_idx = i
            word_duration = word["end"] - word["start"]
            if word_duration > 0:
                word_progress = (current_time - word["start"]) / word_duration
            break

    # If no exact word match, find closest
    if current_word_idx is None and words:
        for i, word in enumerate(words):
            if current_time < word["start"]:
                current_word_idx = max(0, i - 1) if i > 0 else 0
                break
        if current_word_idx is None:
            current_word_idx = len(words) - 1

    # Get previous and next sentences
    previous_sent = sentences[current_sent_idx - 1] if current_sent_idx > 0 else None
    next_sent = sentences[current_sent_idx + 1] if current_sent_idx < len(sentences) - 1 else None

    # Calculate total progress
    total_progress = current_time / audio_duration if audio_duration > 0 else 0.0

    return {
        "current_sentence_index": current_sent_idx,
        "current_word_index": current_word_idx,
        "previous_sentence": previous_sent,
        "current_sentence": current_sent,
        "next_sentence": next_sent,
        "sentence_progress": sentence_progress,
        "word_progress": word_progress,
        "total_progress": total_progress,
        "current_time": current_time,
    }


def adjust_timing_for_speed(
    timing_data: Dict[str, Any],
    speed: float,
) -> Dict[str, Any]:
    """
    Scale all timing values by speed factor.

    Note: This is typically NOT needed for HTML5 audio playback since
    the playbackRate handles the speed and audio.currentTime reports
    actual playback position. This function is for cases where timing
    needs to be pre-adjusted.

    Args:
        timing_data: Original timing data
        speed: Speed multiplier

    Returns:
        Adjusted timing data (copy, not modified in place)
    """
    if speed == 1.0:
        return timing_data

    adjusted = {
        "version": timing_data.get("version", "1.0"),
        "audio_duration": timing_data.get("audio_duration", 0) / speed,
        "sentences": [],
    }

    for sent in timing_data.get("sentences", []):
        adjusted_sent = {
            "sentence_index": sent["sentence_index"],
            "text": sent["text"],
            "start": sent["start"] / speed,
            "end": sent["end"] / speed,
            "words": [],
        }

        for word in sent.get("words", []):
            adjusted_sent["words"].append({
                "word": word["word"],
                "start": word["start"] / speed,
                "end": word["end"] / speed,
                "confidence": word.get("confidence", 0.9),
            })

        adjusted["sentences"].append(adjusted_sent)

    return adjusted


def get_word_states(
    sentence: Dict[str, Any],
    current_time: float,
) -> List[Dict[str, Any]]:
    """
    Get display state for each word in a sentence.

    Args:
        sentence: Sentence timing data
        current_time: Current playback time

    Returns:
        List of word states with state (past/current/future) and progress
    """
    words = sentence.get("words", [])
    result = []

    for i, word in enumerate(words):
        word_start = word["start"]
        word_end = word["end"]

        if current_time < word_start:
            state = "future"
            progress = 0.0
        elif current_time >= word_end:
            state = "past"
            progress = 1.0
        else:
            state = "current"
            duration = word_end - word_start
            progress = (current_time - word_start) / duration if duration > 0 else 0.0

        result.append({
            "index": i,
            "word": word["word"],
            "state": state,
            "progress": progress,
            "start": word_start,
            "end": word_end,
        })

    return result


def find_sentence_at_time(
    timing_data: Dict[str, Any],
    target_time: float,
) -> Optional[int]:
    """
    Find the sentence index at a specific time.

    Args:
        timing_data: Timing data
        target_time: Time in seconds

    Returns:
        Sentence index or None
    """
    sentences = timing_data.get("sentences", [])

    for i, sent in enumerate(sentences):
        if sent["start"] <= target_time < sent["end"]:
            return i

    # Check if before first sentence
    if sentences and target_time < sentences[0]["start"]:
        return 0

    # Check if after last sentence
    if sentences and target_time >= sentences[-1]["end"]:
        return len(sentences) - 1

    return None


def time_to_sentence_index(
    timing_data: Dict[str, Any],
    target_time: float,
) -> Tuple[int, float]:
    """
    Convert a time to sentence index and progress within sentence.

    Args:
        timing_data: Timing data
        target_time: Time in seconds

    Returns:
        Tuple of (sentence_index, progress_within_sentence)
    """
    idx = find_sentence_at_time(timing_data, target_time)

    if idx is None:
        return (0, 0.0)

    sent = timing_data["sentences"][idx]
    duration = sent["end"] - sent["start"]
    progress = (target_time - sent["start"]) / duration if duration > 0 else 0.0

    return (idx, max(0.0, min(1.0, progress)))


def sentence_index_to_time(
    timing_data: Dict[str, Any],
    sentence_index: int,
    progress: float = 0.0,
) -> float:
    """
    Convert a sentence index and progress to time.

    Args:
        timing_data: Timing data
        sentence_index: Index of sentence
        progress: Progress within sentence (0.0 to 1.0)

    Returns:
        Time in seconds
    """
    sentences = timing_data.get("sentences", [])

    if not sentences or sentence_index < 0:
        return 0.0

    if sentence_index >= len(sentences):
        return timing_data.get("audio_duration", 0)

    sent = sentences[sentence_index]
    duration = sent["end"] - sent["start"]

    return sent["start"] + (duration * progress)


def generate_html_for_sentence(
    sentence: Dict[str, Any],
    current_time: float,
    highlight_color: str = "#FFD700",
) -> str:
    """
    Generate HTML for a sentence with word highlighting.

    Args:
        sentence: Sentence timing data
        current_time: Current playback time
        highlight_color: Color for current word highlight

    Returns:
        HTML string
    """
    word_states = get_word_states(sentence, current_time)

    html_parts = []
    for ws in word_states:
        css_class = f"word {ws['state']}"
        style = ""
        if ws["state"] == "current":
            # Partial highlight based on progress
            progress_pct = int(ws["progress"] * 100)
            style = f"background: linear-gradient(90deg, {highlight_color} {progress_pct}%, transparent {progress_pct}%);"

        html_parts.append(
            f'<span class="{css_class}" style="{style}" data-start="{ws["start"]}" data-end="{ws["end"]}">'
            f'{ws["word"]}</span>'
        )

    return " ".join(html_parts)
