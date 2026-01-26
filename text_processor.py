"""
Text processing utilities for ReadAloud.
Handles markdown parsing and text chunking for TTS.
"""

import re
from typing import List, Dict, Any

from library import count_words


def should_auto_chunk(text: str, word_threshold: int = 5000) -> bool:
    """
    Return True if text should be split into chapters.

    Criteria:
    - Text has at least `word_threshold` words (default 5000)
    - Text has at least 2 level-1 or level-2 headings (# or ##)

    Args:
        text: The markdown text to check
        word_threshold: Minimum word count to consider chunking

    Returns:
        True if text should be split into chapters
    """
    # Check word count first (fast check)
    words = count_words(text)
    if words < word_threshold:
        return False

    # Check for heading structure (# or ## at start of line)
    headings = re.findall(r'^#{1,2}\s+.+$', text, re.MULTILINE)
    return len(headings) >= 2


def split_into_chapters(text: str) -> List[Dict[str, Any]]:
    """
    Split markdown by headings into chapter dicts.

    Splits on level-1 (#) and level-2 (##) headings. Content before the
    first heading becomes an "Introduction" chapter if non-empty.

    Args:
        text: The markdown text to split

    Returns:
        List of chapter dicts with keys:
        - title: Chapter title (heading text without # markers)
        - content: Full chapter content including the heading
        - word_count: Number of words in the chapter (CJK-aware)
    """
    # Pattern to split on # or ## headings (but not ### or deeper)
    # Captures the heading line as a delimiter
    heading_pattern = r'^(#{1,2}\s+.+)$'

    # Split text, keeping the delimiters (headings)
    parts = re.split(heading_pattern, text, flags=re.MULTILINE)

    chapters = []

    # Handle content before first heading (if any)
    if parts and parts[0].strip():
        intro_content = parts[0].strip()
        chapters.append({
            'title': 'Introduction',
            'content': intro_content,
            'word_count': count_words(intro_content)
        })
        parts = parts[1:]  # Remove the intro from parts
    elif parts:
        parts = parts[1:]  # Skip empty first part

    # Process heading-content pairs
    # After split with capturing group, odd indices are headings, even are content
    i = 0
    while i < len(parts):
        heading = parts[i].strip() if i < len(parts) else ''
        content_after = parts[i + 1].strip() if i + 1 < len(parts) else ''

        if heading:
            # Extract title (remove # markers)
            title = re.sub(r'^#{1,2}\s+', '', heading)

            # Full chapter content includes the heading
            full_content = heading + '\n\n' + content_after if content_after else heading

            chapters.append({
                'title': title,
                'content': full_content,
                'word_count': count_words(full_content)
            })

        i += 2

    return chapters


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
