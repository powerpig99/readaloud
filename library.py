"""
Library management for ReadAloud.
Handles persistent storage of documents, audio, and timing data.
"""

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

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

    # Count words
    from text_processor import extract_text_from_markdown
    plain_text = extract_text_from_markdown(markdown_content)
    word_count = len(plain_text.split())

    # Create metadata
    metadata = {
        "id": item_id,
        "title": title,
        "filename": filename,
        "created_at": datetime.now().isoformat(),
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
