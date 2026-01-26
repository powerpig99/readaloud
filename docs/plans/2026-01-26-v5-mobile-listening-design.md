# ReadAloud V5 Design: Mobile-First Long-Form Listening

**Date:** 2026-01-26
**Status:** Draft
**Author:** Brainstorming session with Claude

## Overview

ReadAloud V5 focuses on mobile/offline listening for long-form content. The core workflow: import ePub/PDF → auto-detect chapters → generate per-chapter audio → export to iCloud Drive → listen in BookPlayer on iPhone.

## Goals

1. **Import ePub/PDF with smart chapter detection** - no manual splitting
2. **Generate per-chapter audio files** - works with audiobook apps
3. **Export to iCloud Drive** - seamless sync to BookPlayer
4. **Track playback position in web UI** - for occasional read-along at computer

## Non-Goals (V5)

- Custom mobile app (future consideration)
- Karaoke highlighting (code exists, integrate later)
- Streaming playback (generate-then-listen is acceptable)
- Web article import via URL

## User Personas

**Primary use case:** Long-form listening away from computer (commute, cooking, walking)

**Content sources:**
- ePub files (primary)
- PDF files (secondary)
- LLM-generated markdown summaries (existing support)

**Listening context:**
- 80% mobile/background (phone in pocket)
- 20% at computer (reading along)

## Architecture

### New Components

```
readaloud/
├── epub_parser.py      # NEW: ePub extraction + chapter detection
├── pdf_parser.py       # NEW: PDF extraction + chapter detection
├── audio_export.py     # NEW: WAV→M4A conversion, iCloud export
├── library.py          # MODIFY: book/chapter data model, playback state
└── app_nicegui.py      # MODIFY: book import UI, chapter list, enhanced player
```

### Data Model

#### Book (extends existing library item)

```python
@dataclass
class Book:
    id: str
    title: str
    author: str | None
    source_file: str          # original ePub/PDF filename
    source_type: Literal["epub", "pdf", "markdown"]
    cover_path: str | None    # extracted cover image
    chapters: list[Chapter]
    created_at: datetime
    content_hash: str         # for duplicate detection
```

#### Chapter

```python
@dataclass
class Chapter:
    index: int
    title: str
    text: str
    word_count: int
    source_pages: tuple[int, int] | None  # for PDF only
    audio_path: str | None                # None = not generated yet
    audio_duration_seconds: float | None
    generated_at: datetime | None
```

#### Playback State

```python
# Stored in library/{book_id}/playback.json
@dataclass
class PlaybackState:
    current_chapter: int
    position_seconds: float
    bookmarks: list[Bookmark]
    last_played: datetime

@dataclass
class Bookmark:
    chapter: int
    position: float
    note: str
    created_at: datetime
```

### Storage Structure

```
library/
└── {book_id}/
    ├── metadata.json       # Book metadata
    ├── playback.json       # Playback position + bookmarks
    ├── cover.jpg           # Extracted cover (if available)
    ├── source.epub         # Original file (for re-parsing)
    └── chapters/
        ├── 01-introduction.md
        ├── 01-introduction.m4a
        ├── 02-chapter-one.md
        ├── 02-chapter-one.m4a
        └── ...
```

### iCloud Export Structure

```
~/Library/Mobile Documents/com~apple~CloudDocs/ReadAloud/
└── {Book Title}/
    ├── cover.jpg
    ├── 01 - Introduction.m4a
    ├── 02 - Chapter One.m4a
    ├── 03 - Chapter Two.m4a
    └── ...
```

BookPlayer automatically detects folders with audio files and imports them as audiobooks.

## Feature Details

### 1. ePub Import

**Library:** `ebooklib`

**Process:**
1. Parse ePub file structure
2. Extract TOC (table of contents) for chapter titles
3. Iterate through spine items (reading order)
4. Strip HTML tags, preserve paragraph breaks
5. Handle edge cases:
   - Nested chapters → flatten with numbering
   - No TOC → use spine item titles or "Chapter N"
   - Embedded images → skip or extract alt-text

**Code sketch:**
```python
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

def parse_epub(file_path: str) -> list[Chapter]:
    book = epub.read_epub(file_path)
    chapters = []

    for i, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
        soup = BeautifulSoup(item.get_content(), 'html.parser')
        text = soup.get_text(separator='\n\n')
        title = extract_title(soup) or f"Chapter {i+1}"

        if text.strip():  # skip empty items
            chapters.append(Chapter(
                index=len(chapters),
                title=title,
                text=text.strip(),
                word_count=len(text.split())
            ))

    return chapters
```

### 2. PDF Import

**Library:** `pymupdf` (fitz)

**Chapter detection heuristics (in priority order):**
1. PDF outline/bookmarks (most reliable)
2. Large font headings (>16pt, bold)
3. Pattern matching: "Chapter X", "Part X", "Section X"
4. Page breaks with centered text
5. Fallback: split every N pages (configurable, default 20)

**Code sketch:**
```python
import fitz  # pymupdf

def parse_pdf(file_path: str) -> list[Chapter]:
    doc = fitz.open(file_path)

    # Try outline first
    outline = doc.get_toc()
    if outline:
        return chapters_from_outline(doc, outline)

    # Fall back to heuristics
    return chapters_from_heuristics(doc)

def chapters_from_outline(doc, outline) -> list[Chapter]:
    chapters = []
    for i, (level, title, page_num) in enumerate(outline):
        if level == 1:  # top-level chapters only
            start_page = page_num - 1
            end_page = get_next_chapter_page(outline, i) - 1
            text = extract_pages(doc, start_page, end_page)
            chapters.append(Chapter(
                index=len(chapters),
                title=title,
                text=text,
                source_pages=(start_page, end_page)
            ))
    return chapters
```

### 3. Audio Generation

**Changes from V4:**
- Generate per-chapter instead of per-document
- Output M4A (AAC) instead of WAV
- Embed metadata (title, track number, album=book title)

**M4A conversion:**
```python
from pydub import AudioSegment

def convert_to_m4a(wav_path: str, m4a_path: str, metadata: dict):
    audio = AudioSegment.from_wav(wav_path)
    audio.export(
        m4a_path,
        format="ipod",  # M4A/AAC
        bitrate="128k",
        tags={
            "title": metadata["title"],
            "album": metadata["book_title"],
            "track": metadata["track_number"],
            "artist": metadata.get("author", "ReadAloud"),
        }
    )
```

**Generation flow:**
1. User selects chapters to generate
2. For each chapter:
   - Show progress: "Generating chapter 1/12: Introduction..."
   - Use existing `generate_long_text()` with selected voice
   - Convert WAV → M4A with metadata
   - Save to `library/{book_id}/chapters/`
   - Update chapter record with audio_path, duration
3. Auto-export to iCloud folder

### 4. iCloud Export

**Export path:** `~/Library/Mobile Documents/com~apple~CloudDocs/ReadAloud/{Book Title}/`

**Process:**
1. Create book folder (sanitize title for filesystem)
2. Copy cover.jpg if available
3. Copy all generated M4A files with sequential naming:
   - `01 - Introduction.m4a`
   - `02 - Chapter One.m4a`
4. BookPlayer auto-detects and imports

**Code sketch:**
```python
from pathlib import Path
import shutil

ICLOUD_BASE = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/ReadAloud"

def export_to_icloud(book: Book):
    book_dir = ICLOUD_BASE / sanitize_filename(book.title)
    book_dir.mkdir(parents=True, exist_ok=True)

    # Copy cover
    if book.cover_path:
        shutil.copy(book.cover_path, book_dir / "cover.jpg")

    # Copy audio files with sequential naming
    for chapter in book.chapters:
        if chapter.audio_path:
            dest_name = f"{chapter.index+1:02d} - {sanitize_filename(chapter.title)}.m4a"
            shutil.copy(chapter.audio_path, book_dir / dest_name)
```

### 5. Web UI Changes

**New book import flow:**
1. Upload button accepts `.epub`, `.pdf` (in addition to `.md`, `.txt`)
2. Parsing spinner while extracting chapters
3. Show chapter list view:
   ```
   ┌─────────────────────────────────────────────┐
   │ 📚 The Pragmatic Programmer                 │
   │ by David Thomas, Andrew Hunt               │
   │ 12 chapters • ~45,000 words • ~5h audio    │
   ├─────────────────────────────────────────────┤
   │ ☑ 1. A Pragmatic Philosophy (3,200 words)  │
   │ ☑ 2. A Pragmatic Approach (4,100 words)    │
   │ ☑ 3. The Basic Tools (3,800 words)         │
   │ ☐ 4. Pragmatic Paranoia (2,900 words)      │
   │ ...                                         │
   ├─────────────────────────────────────────────┤
   │ Voice: [Elon Musk ▼]  Model: [0.6B ▼]      │
   │                                             │
   │ [Generate Selected (11 chapters)]          │
   └─────────────────────────────────────────────┘
   ```

**Enhanced audio player:**
```
┌─────────────────────────────────────────────┐
│ Chapter: [3. The Basic Tools ▼]             │
│                                             │
│ ◀◀  ▶  ▶▶     🔖                           │
│ ━━━━━━━━━●━━━━━━━━━━━━━  12:34 / 28:15     │
│                                             │
│ Speed: [1x] [1.5x] [2x] [2.5x] [3x]        │
│                                             │
│ Book progress: Chapter 3/12 • 2h 15m left   │
└─────────────────────────────────────────────┘
```

**Bookmarks panel:**
```
┌─────────────────────────────────────────────┐
│ 🔖 Bookmarks                                │
├─────────────────────────────────────────────┤
│ Ch 1 @ 5:42 - "Key insight about pragmatism"│
│ Ch 3 @ 12:30 - "Tool recommendation"        │
│ Ch 7 @ 3:15 - (no note)                     │
└─────────────────────────────────────────────┘
```

### 6. Playback Position Tracking

**Auto-save:** Every 10 seconds during playback, save current position to `playback.json`

**Resume:** When selecting a book, load last position and offer:
- "Resume from Chapter 3 @ 12:34?" [Resume] [Start Over]

**Cross-chapter:** When chapter ends, auto-advance to next chapter and update position.

## Dependencies

**New packages:**
```
ebooklib>=0.18      # ePub parsing
pymupdf>=1.24       # PDF parsing
pydub>=0.25         # Audio conversion (uses ffmpeg)
beautifulsoup4>=4.12 # HTML parsing for ePub
```

**System dependency:**
- `ffmpeg` - required for M4A encoding (already common on macOS)

## Implementation Priority

| Priority | Feature | Effort | Notes |
|----------|---------|--------|-------|
| P0 | ePub import + chapter detection | 3-4h | Core feature |
| P0 | Per-chapter audio generation | 2h | Refactor existing code |
| P0 | M4A export with metadata | 2h | pydub + ffmpeg |
| P0 | iCloud folder export | 1h | File copy with naming |
| P1 | PDF import + chapter detection | 3-4h | Heuristics are tricky |
| P1 | Playback position persistence | 1-2h | JSON save/load |
| P1 | Chapter navigation in player | 2h | UI work |
| P2 | Bookmarks | 2h | UI + storage |
| P2 | Book cover extraction | 1h | ePub has it, PDF harder |

**Total estimated effort:** 8-12 hours for P0+P1

## Future Considerations (Post-V5)

1. **Lightweight mobile web app** - PWA for playback-only on phone
2. **Karaoke highlighting** - integrate existing code for read-along mode
3. **Audiobook chapter markers** - M4B format with embedded chapters
4. **Whisper alignment** - precise word-level timing for karaoke
5. **Queue management** - batch import multiple books
6. **Reading stats** - track listening time, books completed

## Open Questions

1. **PDF fallback granularity** - How many pages per chunk if no chapters detected? (Proposed: 20 pages, ~15-20 min audio)
2. **Regeneration** - If user changes voice, regenerate all chapters or just selected?
3. **Storage cleanup** - Auto-delete old audio when regenerating, or keep versions?

## Success Criteria

- [ ] Can import a 12-chapter ePub and see all chapters listed
- [ ] Can generate audio for selected chapters with progress indication
- [ ] Audio appears in iCloud folder within 30 seconds of generation
- [ ] BookPlayer imports and plays the audiobook correctly
- [ ] Can resume playback from last position in web UI
- [ ] Can add/view bookmarks in web UI
