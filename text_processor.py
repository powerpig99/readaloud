"""
Text processing utilities for ReadAloud.
Handles markdown parsing and text chunking for TTS.
"""

import re
from typing import List, Dict, Any


def extract_text_from_markdown(content: str) -> str:
    """
    Extract plain text from markdown content.
    Removes formatting while preserving readability.
    """
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', content)
    text = re.sub(r'`[^`]+`', '', text)

    # Remove images
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

    # Remove links but keep text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Remove plain URLs (http/https)
    text = re.sub(r'https?://[^\s\)\]]+', '', text)

    # Remove headers markers but keep text
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Remove bold/italic markers
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)
    text = re.sub(r'_([^_]+)_', r'\1', text)

    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # Remove list markers
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

    # Remove blockquote markers
    text = re.sub(r'^\s*>\s+', '', text, flags=re.MULTILINE)

    # Normalize whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


def chunk_text(text: str, max_chars: int = 800) -> List[str]:
    """
    Split text into chunks suitable for TTS processing.

    Splits at sentence boundaries, respecting max character limit.
    Ensures no chunk exceeds the limit while keeping sentences intact.
    Handles both ASCII and CJK (Chinese/Japanese/Korean) punctuation.
    """
    # Split into sentences (handles ASCII and CJK sentence-ending punctuation)
    # ASCII: . ! ?   CJK: 。！？
    sentence_pattern = r'(?<=[.!?。！？])\s*'
    sentences = re.split(sentence_pattern, text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # If sentence itself exceeds max, split by clauses
        if len(sentence) > max_chars:
            # Split by commas, semicolons, colons (ASCII and CJK)
            # ASCII: , ; :   CJK: ，；：
            sub_parts = re.split(r'[,;:，；：]\s*', sentence)
            for part in sub_parts:
                part = part.strip()
                if not part:
                    continue
                if len(current_chunk) + len(part) + 1 <= max_chars:
                    current_chunk += (" " + part) if current_chunk else part
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = part
        elif len(current_chunk) + len(sentence) + 1 <= max_chars:
            current_chunk += (" " + sentence) if current_chunk else sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def estimate_duration(text: str, words_per_minute: int = 150) -> float:
    """
    Estimate audio duration in seconds based on text length.
    Default assumes ~150 words per minute at 1x speed.
    """
    word_count = len(text.split())
    return (word_count / words_per_minute) * 60


def get_text_stats(text: str) -> dict:
    """Return statistics about the text."""
    words = text.split()
    sentences = re.split(r'[.!?。！？]+', text)

    return {
        "characters": len(text),
        "words": len(words),
        "sentences": len([s for s in sentences if s.strip()]),
        "estimated_duration_seconds": estimate_duration(text),
    }


def get_sentences(text: str) -> List[Dict[str, Any]]:
    """
    Extract sentences with their indices for alignment.

    Returns a list of sentence dictionaries with:
    - index: sentence number (0-based)
    - text: the sentence text
    - start_char: character position where sentence starts
    - end_char: character position where sentence ends

    Args:
        text: Plain text to split into sentences

    Returns:
        List of sentence dictionaries
    """
    # Split into sentences (handles ASCII and CJK sentence-ending punctuation)
    sentence_pattern = r'(?<=[.!?。！？])\s*'
    parts = re.split(sentence_pattern, text)

    sentences = []
    current_pos = 0

    for i, sentence in enumerate(parts):
        sentence = sentence.strip()
        if not sentence:
            continue

        # Find where this sentence starts in the original text
        start_pos = text.find(sentence, current_pos)
        if start_pos == -1:
            start_pos = current_pos

        end_pos = start_pos + len(sentence)

        sentences.append({
            "index": len(sentences),
            "text": sentence,
            "start_char": start_pos,
            "end_char": end_pos,
        })

        current_pos = end_pos

    return sentences


def get_sentences_from_chunks(chunks: List[str]) -> List[Dict[str, Any]]:
    """
    Extract sentences from pre-chunked text.

    This is useful when text has already been chunked for TTS
    and we want sentence-level alignment.

    Args:
        chunks: List of text chunks

    Returns:
        List of sentence dictionaries
    """
    all_sentences = []

    for chunk in chunks:
        chunk_sentences = get_sentences(chunk)
        # Adjust indices to be global
        for sent in chunk_sentences:
            sent["index"] = len(all_sentences)
            all_sentences.append(sent)

    return all_sentences
