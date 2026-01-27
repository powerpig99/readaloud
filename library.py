"""
Library management for ReadAloud.
Handles persistent storage of documents, audio, and timing data.
"""

import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


def compute_content_hash(content: str) -> str:
    """Compute SHA-256 hash of document content."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def find_by_hash(content_hash: str) -> Optional[Dict[str, Any]]:
    """
    Find a library item by content hash.

    Args:
        content_hash: SHA-256 hash of the document content

    Returns:
        Item metadata if found, None otherwise
    """
    index = _load_index()
    for item in index.get("items", []):
        if item.get("content_hash") == content_hash:
            return item
    return None


def count_words(text: str) -> int:
    """Count words, handling Chinese/Japanese/Korean text."""
    # CJK Unicode ranges
    cjk_pattern = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]')

    cjk_chars = len(cjk_pattern.findall(text))
    # Remove CJK chars, count remaining words
    non_cjk = cjk_pattern.sub(' ', text)
    other_words = len(non_cjk.split())

    return cjk_chars + other_words

# Default paths
LIBRARY_DIR = Path(__file__).parent / "library"
DATA_DIR = Path(__file__).parent / "data"
LIBRARY_INDEX = DATA_DIR / "library.json"


def init_library() -> None:
    """Initialize library directories and index file."""
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not LIBRARY_INDEX.exists():
        _save_index({"items": []})


def _load_index() -> Dict[str, Any]:
    """Load the library index."""
    if not LIBRARY_INDEX.exists():
        return {"items": []}

    with open(LIBRARY_INDEX, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save_index(index: Dict[str, Any]) -> None:
    """Save the library index."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(LIBRARY_INDEX, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def _get_item_dir(item_id: str) -> Path:
    """Get the directory path for a library item."""
    return LIBRARY_DIR / item_id


def create_item(
    markdown_content: str,
    filename: str,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Add a new document to the library.

    Args:
        markdown_content: The markdown content to store
        filename: Original filename
        title: Optional title (extracted from content if not provided)

    Returns:
        The created item metadata
    """
    init_library()

    # Generate unique ID
    item_id = str(uuid.uuid4())
    item_dir = _get_item_dir(item_id)
    item_dir.mkdir(parents=True, exist_ok=True)

    # Extract title from first heading if not provided
    if title is None:
        lines = markdown_content.strip().split('\n')
        for line in lines:
            if line.startswith('#'):
                title = line.lstrip('#').strip()
                break
        if title is None:
            title = Path(filename).stem

    # Count words (handles CJK text properly)
    from text_processor import extract_text_from_markdown
    plain_text = extract_text_from_markdown(markdown_content)
    word_count = count_words(plain_text)

    # Compute content hash for duplicate detection
    content_hash = compute_content_hash(markdown_content)

    # Create metadata
    metadata = {
        "id": item_id,
        "title": title,
        "filename": filename,
        "created_at": datetime.now().isoformat(),
        "content_hash": content_hash,
        "audio_generated": False,
        "audio_duration_seconds": None,
        "word_count": word_count,
        "language": "english",
        "voice_settings": {
            "mode": "default",
            "speaker": "serena",
            "model_size": "0.6B"
        }
    }

    # Save document
    doc_path = item_dir / "document.md"
    with open(doc_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)

    # Save metadata
    meta_path = item_dir / "metadata.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Update index
    index = _load_index()
    index["items"].append({
        "id": item_id,
        "title": title,
        "filename": filename,
        "created_at": metadata["created_at"],
        "content_hash": content_hash,
        "audio_generated": False,
        "word_count": word_count,
    })
    _save_index(index)

    return metadata


def get_item(item_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a library item by ID.

    Args:
        item_id: The item ID

    Returns:
        Item metadata or None if not found
    """
    item_dir = _get_item_dir(item_id)
    meta_path = item_dir / "metadata.json"

    if not meta_path.exists():
        return None

    with open(meta_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_all_items() -> List[Dict[str, Any]]:
    """
    Get all items in the library.

    Returns:
        List of item metadata (summary info from index)
    """
    init_library()
    index = _load_index()
    return index.get("items", [])


def delete_item(item_id: str) -> bool:
    """
    Delete a library item and all its files.

    Args:
        item_id: The item ID to delete

    Returns:
        True if deleted, False if not found
    """
    item_dir = _get_item_dir(item_id)

    if not item_dir.exists():
        return False

    # Remove directory and all contents
    shutil.rmtree(item_dir)

    # Update index
    index = _load_index()
    index["items"] = [item for item in index["items"] if item["id"] != item_id]
    _save_index(index)

    return True


def update_item(item_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Update a library item's metadata.

    Args:
        item_id: The item ID
        updates: Dictionary of fields to update

    Returns:
        Updated metadata or None if not found
    """
    item_dir = _get_item_dir(item_id)
    meta_path = item_dir / "metadata.json"

    if not meta_path.exists():
        return None

    # Load current metadata
    with open(meta_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    # Apply updates
    metadata.update(updates)

    # Save updated metadata
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Update index if relevant fields changed
    index = _load_index()
    for item in index["items"]:
        if item["id"] == item_id:
            if "title" in updates:
                item["title"] = updates["title"]
            if "audio_generated" in updates:
                item["audio_generated"] = updates["audio_generated"]
            if "audio_duration_seconds" in updates:
                item["audio_duration_seconds"] = updates["audio_duration_seconds"]
            break
    _save_index(index)

    return metadata


def get_document_path(item_id: str) -> Optional[Path]:
    """Get the path to the document file."""
    path = _get_item_dir(item_id) / "document.md"
    return path if path.exists() else None


def get_audio_path(item_id: str) -> Path:
    """Get the path where audio should be stored (may not exist yet)."""
    return _get_item_dir(item_id) / "audio.wav"


def get_timing_path(item_id: str) -> Path:
    """Get the path where timing data should be stored (may not exist yet)."""
    return _get_item_dir(item_id) / "timing.json"


def get_document_content(item_id: str) -> Optional[str]:
    """
    Get the markdown content of a document.

    Args:
        item_id: The item ID

    Returns:
        Markdown content or None if not found
    """
    doc_path = get_document_path(item_id)
    if doc_path is None:
        return None

    with open(doc_path, 'r', encoding='utf-8') as f:
        return f.read()


def save_audio(item_id: str, audio_path: str, duration: float) -> bool:
    """
    Copy generated audio to library and update metadata.

    Args:
        item_id: The item ID
        audio_path: Path to the generated audio file
        duration: Audio duration in seconds

    Returns:
        True if successful
    """
    item_dir = _get_item_dir(item_id)
    if not item_dir.exists():
        return False

    # Copy audio to library
    dest_path = get_audio_path(item_id)
    shutil.copy2(audio_path, dest_path)

    # Update metadata
    update_item(item_id, {
        "audio_generated": True,
        "audio_duration_seconds": duration,
    })

    return True


def save_timing(item_id: str, timing_data: Dict[str, Any]) -> bool:
    """
    Save word-level timing data for an item.

    Args:
        item_id: The item ID
        timing_data: Timing data from alignment

    Returns:
        True if successful
    """
    item_dir = _get_item_dir(item_id)
    if not item_dir.exists():
        return False

    timing_path = get_timing_path(item_id)
    with open(timing_path, 'w', encoding='utf-8') as f:
        json.dump(timing_data, f, indent=2, ensure_ascii=False)

    return True


def get_timing(item_id: str) -> Optional[Dict[str, Any]]:
    """
    Get timing data for an item.

    Args:
        item_id: The item ID

    Returns:
        Timing data or None if not available
    """
    timing_path = get_timing_path(item_id)
    if not timing_path.exists():
        return None

    with open(timing_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def has_audio(item_id: str) -> bool:
    """Check if an item has generated audio."""
    return get_audio_path(item_id).exists()


def has_timing(item_id: str) -> bool:
    """Check if an item has timing data."""
    return get_timing_path(item_id).exists()


def create_book(
    title: str,
    filename: str,
    chapters: List[Dict[str, Any]],
    content_hash: Optional[str] = None,
    source_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a book with multiple chapters.

    A book stores chapters as a list in metadata.json rather than
    as separate library items. This keeps related content together.

    Args:
        title: Book title
        filename: Original filename
        chapters: List of chapter dicts with keys:
            - title: Chapter title
            - content: Chapter markdown content
            - word_count: Number of words in chapter
        content_hash: Optional pre-computed content hash

    Returns:
        The created book metadata
    """
    init_library()

    # Generate unique ID
    book_id = str(uuid.uuid4())
    book_dir = _get_item_dir(book_id)
    book_dir.mkdir(parents=True, exist_ok=True)

    # Calculate totals
    total_words = sum(ch.get('word_count', 0) for ch in chapters)
    chapter_count = len(chapters)

    # Prepare chapters for storage (add audio_path field)
    stored_chapters = []
    for ch in chapters:
        stored_chapters.append({
            'title': ch['title'],
            'content': ch['content'],
            'word_count': ch.get('word_count', 0),
            'audio_path': None,  # Will be set when audio is generated
        })

    # Compute content hash if not provided
    if content_hash is None:
        full_content = '\n\n'.join(ch['content'] for ch in chapters)
        content_hash = compute_content_hash(full_content)

    # Create metadata
    metadata = {
        "id": book_id,
        "type": "book",
        "title": title,
        "filename": filename,
        "created_at": datetime.now().isoformat(),
        "content_hash": content_hash,
        "chapter_count": chapter_count,
        "total_words": total_words,
        "chapters": stored_chapters,
        "language": "english",
        "voice_settings": {
            "mode": "default",
            "speaker": "serena",
            "model_size": "0.6B"
        }
    }

    # Add source type if specified (e.g., 'epub')
    if source_type:
        metadata["source_type"] = source_type

    # Save full document (all chapters concatenated)
    doc_path = book_dir / "document.md"
    full_content = '\n\n'.join(ch['content'] for ch in chapters)
    with open(doc_path, 'w', encoding='utf-8') as f:
        f.write(full_content)

    # Save metadata
    meta_path = book_dir / "metadata.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Update index (summary info only, not full chapters)
    index = _load_index()
    index["items"].append({
        "id": book_id,
        "type": "book",
        "title": title,
        "filename": filename,
        "created_at": metadata["created_at"],
        "content_hash": content_hash,
        "chapter_count": chapter_count,
        "total_words": total_words,
        "word_count": total_words,  # For compatibility with existing UI
        "audio_generated": False,
    })
    _save_index(index)

    return metadata


def save_chapter_audio(
    book_id: str,
    chapter_idx: int,
    audio_path: str,
    duration: float,
) -> bool:
    """
    Save generated audio for a specific chapter.

    Args:
        book_id: The book ID
        chapter_idx: Zero-based chapter index
        audio_path: Path to the generated audio file
        duration: Audio duration in seconds

    Returns:
        True if successful, False otherwise
    """
    item = get_item(book_id)
    if item is None:
        return False

    # Check this is actually a book
    is_book = item.get('type') == 'book' or item.get('source_type') == 'epub'
    if not is_book:
        return False

    chapters = item.get('chapters', [])
    if chapter_idx < 0 or chapter_idx >= len(chapters):
        return False

    # Create chapters audio directory if needed
    book_dir = _get_item_dir(book_id)
    chapters_audio_dir = book_dir / "chapters_audio"
    chapters_audio_dir.mkdir(exist_ok=True)

    # Generate filename: 00-chapter-title.wav
    chapter = chapters[chapter_idx]
    chapter_title = chapter.get('title', f'Chapter {chapter_idx + 1}')
    # Sanitize title for filename
    safe_title = "".join(c if c.isalnum() or c in ' -_' else '_' for c in chapter_title)[:50]
    dest_filename = f"{chapter_idx:02d}-{safe_title}.wav"
    dest_path = chapters_audio_dir / dest_filename

    # Copy audio to library
    shutil.copy2(audio_path, dest_path)

    # Update chapter metadata with audio path
    chapters[chapter_idx]['audio_path'] = str(dest_path)
    chapters[chapter_idx]['audio_duration_seconds'] = duration

    # Save updated metadata
    meta_path = book_dir / "metadata.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(item, f, indent=2, ensure_ascii=False)

    # Check if all chapters have audio
    all_have_audio = all(ch.get('audio_path') is not None for ch in chapters)

    # Update index
    index = _load_index()
    for idx_item in index["items"]:
        if idx_item["id"] == book_id:
            idx_item["audio_generated"] = all_have_audio
            break
    _save_index(index)

    return True


def save_chapter_timing(
    book_id: str,
    chapter_idx: int,
    timing_data: Dict[str, Any],
) -> bool:
    """
    Save timing data for a specific chapter.

    Args:
        book_id: The book ID
        chapter_idx: Zero-based chapter index
        timing_data: Timing data from alignment

    Returns:
        True if successful, False otherwise
    """
    item = get_item(book_id)
    if item is None:
        return False

    # Check this is actually a book
    is_book = item.get('type') == 'book' or item.get('source_type') == 'epub'
    if not is_book:
        return False

    chapters = item.get('chapters', [])
    if chapter_idx < 0 or chapter_idx >= len(chapters):
        return False

    # Create chapters audio directory if needed (timing goes alongside audio)
    book_dir = _get_item_dir(book_id)
    chapters_audio_dir = book_dir / "chapters_audio"
    chapters_audio_dir.mkdir(exist_ok=True)

    # Save timing file: 00-timing.json, 01-timing.json, etc.
    timing_filename = f"{chapter_idx:02d}-timing.json"
    timing_path = chapters_audio_dir / timing_filename

    with open(timing_path, 'w', encoding='utf-8') as f:
        json.dump(timing_data, f, indent=2, ensure_ascii=False)

    return True


def get_chapter_text(book_id: str, chapter_idx: int) -> Optional[str]:
    """
    Get the text content of a specific chapter.

    Handles two storage formats:
    1. Content stored in metadata (from create_book())
    2. Content stored as separate .md files in chapters/ dir (from EPUB import)

    Args:
        book_id: The book ID
        chapter_idx: Zero-based chapter index

    Returns:
        Chapter content as markdown text, or None if not found
    """
    item = get_item(book_id)
    if item is None:
        return None

    # Check this is actually a book (type='book' from create_book, or source_type='epub' from EPUB import)
    is_book = item.get('type') == 'book' or item.get('source_type') == 'epub'
    if not is_book:
        return None

    chapters = item.get('chapters', [])
    if chapter_idx < 0 or chapter_idx >= len(chapters):
        return None

    chapter = chapters[chapter_idx]

    # Method 1: Content stored directly in metadata
    if chapter.get('content'):
        return chapter['content']

    # Method 2: Content stored as separate file in chapters/ directory
    book_dir = _get_item_dir(book_id)
    chapters_dir = book_dir / "chapters"

    if chapters_dir.exists():
        # Look for chapter file by index prefix (e.g., "00-*.md", "01-*.md")
        prefix = f"{chapter_idx:02d}-"
        for file_path in chapters_dir.glob(f"{prefix}*.md"):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()

    return None
