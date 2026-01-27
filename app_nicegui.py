"""
ReadAloud v5 - NiceGUI Version
Local TTS Reader with Library Management.
Features: Auto-chunking, book/chapter support, voice cloning, unified generation interface.
"""

from nicegui import ui, app, run, context
import asyncio
import tempfile
import time
import io
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass, field
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


def estimate_audio_duration(word_count: int, words_per_minute: int = 150) -> str:
    """Estimate audio duration based on word count. Returns formatted string like '~5 min'."""
    if word_count <= 0:
        return ""
    minutes = word_count / words_per_minute
    if minutes < 1:
        return f"~{int(minutes * 60)}s"
    elif minutes < 60:
        return f"~{int(minutes)} min"
    else:
        hours = int(minutes // 60)
        mins = int(minutes % 60)
        return f"~{hours}h {mins}m"


def parse_epub_content(epub_bytes: bytes) -> Tuple[str, str, List[dict]]:
    """
    Parse EPUB file and extract title, content, and chapters.
    Returns: (title, full_markdown_content, chapters_list)
    """
    # Read EPUB from bytes
    book = epub.read_epub(io.BytesIO(epub_bytes))

    # Extract title
    title = book.get_metadata('DC', 'title')
    title = title[0][0] if title else "Untitled"

    chapters = []
    all_content = []

    # Process each document item
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            # Parse HTML content
            soup = BeautifulSoup(item.get_content(), 'html.parser')

            # Try to find chapter title from headings
            chapter_title = None
            for tag in ['h1', 'h2', 'h3']:
                heading = soup.find(tag)
                if heading:
                    chapter_title = heading.get_text(strip=True)
                    break

            # Extract text content
            text = soup.get_text(separator='\n', strip=True)
            if text.strip():
                # Use item name as fallback title
                if not chapter_title:
                    chapter_title = Path(item.get_name()).stem.replace('_', ' ').replace('-', ' ').title()

                # Calculate word count
                word_count = len(text.split())

                chapters.append({
                    'title': chapter_title,
                    'content': text,
                    'word_count': word_count,
                })
                all_content.append(f"# {chapter_title}\n\n{text}")

    # Combine all content as markdown
    full_content = "\n\n---\n\n".join(all_content)

    return title, full_content, chapters


# Speed presets for extended control (native player only goes to 2x)
SPEED_OPTIONS = {
    "0.5x": 0.5, "0.75x": 0.75, "1x": 1.0, "1.25x": 1.25,
    "1.5x": 1.5, "1.75x": 1.75, "2x": 2.0, "2.5x": 2.5, "3x": 3.0
}

from text_processor import (
    extract_text_from_markdown,
    chunk_text,
    get_text_stats,
    get_sentences,
    should_auto_chunk,
    split_into_chapters,
)
from tts_engine import (
    generate_long_text,
    save_audio,
    create_voice_clone_prompt,
)
from audio_processor import get_audio_duration
import library
from alignment import create_simple_timing

# Supported languages
LANGUAGES = [
    "English",
    "Chinese",
    "Japanese",
    "Korean",
    "French",
    "German",
    "Spanish",
    "Portuguese",
    "Russian",
    "Italian",
]

# Available voices
VOICES = {
    "Ryan (English Male)": "ryan",
    "Aiden (English Male)": "aiden",
    "Serena (Chinese Female)": "serena",
    "Vivian (Chinese Female)": "vivian",
    "Uncle Fu (Chinese Male)": "uncle_fu",
    "Dylan (Beijing Male)": "dylan",
    "Eric (Sichuan Male)": "eric",
    "Ono Anna (Japanese Female)": "ono_anna",
    "Sohee (Korean Female)": "sohee",
}

# Voice cloning samples (pre-loaded)
VOICE_SAMPLES_DIR = Path(__file__).parent / "voice_samples"
CLONE_SAMPLES = {
    "Custom (Upload your own)": None,
    "Elon Musk": {
        "audio": "elon-musk_trimmed.wav",
        "transcript": "elon-musk.txt",
    },
    "Jensen Huang (NVIDIA)": {
        "audio": "jensen-huang_trimmed.wav",
        "transcript": "jensen-huang.txt",
    },
    "Donald Trump": {
        "audio": "donald-trump.wav",
        "transcript": "donald-trump.txt",
    },
    "Bill Gates": {
        "audio": "bill_gates_trimmed.wav",
        "transcript": "bill_gates.txt",
    },
}

# Initialize library on startup
library.init_library()


@dataclass
class GenerationProgress:
    """Thread-safe progress state for TTS generation."""
    current_chunk: int = 0
    total_chunks: int = 0
    start_time: float = 0.0
    chunk_times: list = field(default_factory=list)
    is_generating: bool = False

    def start(self, total: int):
        self.current_chunk = 0
        self.total_chunks = total
        self.start_time = time.time()
        self.chunk_times = []
        self.is_generating = True

    def update(self, current: int, total: int):
        if current > self.current_chunk:
            self.chunk_times.append(time.time())
        self.current_chunk = current
        self.total_chunks = total

    def stop(self):
        self.is_generating = False

    @property
    def progress_fraction(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return self.current_chunk / self.total_chunks

    @property
    def elapsed_seconds(self) -> float:
        if self.start_time == 0:
            return 0.0
        return time.time() - self.start_time

    @property
    def estimated_remaining(self) -> float:
        """Estimate remaining time based on average chunk time."""
        if self.current_chunk == 0 or len(self.chunk_times) == 0:
            return 0.0
        avg_time_per_chunk = self.elapsed_seconds / self.current_chunk
        remaining_chunks = self.total_chunks - self.current_chunk
        return avg_time_per_chunk * remaining_chunks


class ReadAloudApp:
    """Main application state and UI."""

    def __init__(self):
        self.current_item_id: Optional[str] = None
        self.current_chapter_idx: Optional[int] = None  # For books: which chapter is selected
        self.current_audio_path: Optional[str] = None

        # UI components (will be set in build_ui)
        self.library_container = None  # Scrollable card container
        self.library_cards = {}  # {item_id: card_element}
        self.text_preview = None
        self.audio_container = None
        self.status_label = None
        self.current_speed = 1.0

        # Progress tracking
        self.progress_state = GenerationProgress()
        self.progress_card = None
        self.progress_bar = None
        self.progress_text = None
        self.progress_timer = None

        # Generate Audio section components
        self.generation_container = None
        self.gen_selected_label = None
        self.voice_row = None
        self.stock_voice_select = None
        self.clone_voice_select = None
        self.settings_row = None
        self.gen_language = None
        self.gen_model = None
        self.gen_button = None

        # Voice cloning state
        self.clone_audio_path: Optional[str] = None
        self.clone_transcript: Optional[str] = None

        # Generation section state (tracks what's selected for audio generation)
        self._gen_item_id: Optional[str] = None
        self._gen_chapter_idx: Optional[int] = None

    def refresh_library(self):
        """Refresh library cards in the scrollable container."""
        items = library.get_all_items()

        # Clear existing cards
        self.library_container.clear()
        self.library_cards = {}

        with self.library_container:
            if not items:
                ui.label("No documents yet. Upload one below!").classes(
                    "text-gray-500 italic p-4"
                )
            else:
                for item in items:
                    self._create_library_card(item)

        # If current item was deleted, clear selection
        if self.current_item_id and self.current_item_id not in self.library_cards:
            self.current_item_id = None
            self.current_chapter_idx = None
            self.current_audio_path = None
            self.text_preview.value = ""
            self.update_audio_player(None)
        elif self.current_item_id:
            # Re-highlight current selection
            self._highlight_card(self.current_item_id)

    def _create_library_card(self, item: dict):
        """Create a clickable card for a library item (or expandable card for books)."""
        item_id = item['id']
        has_audio = item.get('audio_generated', False)
        # Check for both type='book' (from create_book) and source_type='epub' (from EPUB import)
        is_book = item.get('type') == 'book' or item.get('source_type') == 'epub'

        if is_book:
            # Get full book metadata with chapters
            book_meta = library.get_item(item_id)
            chapters = book_meta.get('chapters', []) if book_meta else []
            word_count = item.get('total_words', 0)
            chapter_count = item.get('chapter_count', 0)

            # Create expandable card for books with delete button in header
            est_duration = estimate_audio_duration(word_count)
            with ui.row().classes("w-full items-center"):
                with ui.expansion(
                    f"{item['title']}",
                    icon="menu_book"
                ).classes("flex-1") as expansion:
                    # Summary line with estimated duration
                    ui.label(f"{chapter_count} chapters | {word_count:,} words | {est_duration}").classes(
                        "text-xs text-gray-500 mb-2"
                    )

                    # Chapter list
                    for idx, ch in enumerate(chapters):
                        self._create_chapter_row(item_id, idx, ch)

                # Delete button outside expansion
                ui.button(
                    icon="delete",
                    on_click=lambda i=item_id: self._delete_single_item(i),
                    color="red"
                ).props("flat dense round size=sm").classes("opacity-50 hover:opacity-100")

            self.library_cards[item_id] = expansion
        else:
            # Standard card for documents
            word_count = item.get('word_count', 0)
            audio_duration = item.get('audio_duration', 0)

            # Show actual duration if audio exists, otherwise estimated
            if has_audio and audio_duration > 0:
                duration_str = f"{audio_duration:.0f}s"
            else:
                duration_str = estimate_audio_duration(word_count)

            card = ui.card().classes(
                "w-full cursor-pointer hover:bg-blue-50 transition-colors p-3"
            ).on('click', lambda i=item_id: self._on_card_click(i))

            with card:
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.column().classes("gap-0 flex-1"):
                        ui.label(item['title']).classes("font-semibold text-sm truncate max-w-xs")
                        ui.label(f"{word_count:,} words | {duration_str}").classes("text-xs text-gray-500")

                    with ui.row().classes("gap-2 items-center"):
                        # Audio status badge
                        if has_audio:
                            ui.badge("Audio", color="green").props("outline")
                        else:
                            ui.badge("No Audio", color="grey").props("outline")

                        # Delete button for this item
                        ui.button(
                            icon="delete",
                            on_click=lambda i=item_id: self._delete_single_item(i),
                            color="red"
                        ).props("flat dense round size=sm").classes("opacity-50 hover:opacity-100")

            self.library_cards[item_id] = card

    def _create_chapter_row(self, book_id: str, chapter_idx: int, chapter: dict):
        """Create a clickable row for a chapter within a book."""
        has_audio = chapter.get('audio_path') is not None
        chapter_title = chapter.get('title', f'Chapter {chapter_idx + 1}')
        word_count = chapter.get('word_count', 0)
        audio_duration = chapter.get('audio_duration', 0)

        # Show actual duration if audio exists, otherwise estimated
        if has_audio and audio_duration > 0:
            duration_str = f"{audio_duration:.0f}s"
        else:
            duration_str = estimate_audio_duration(word_count)

        with ui.row().classes(
            "w-full p-2 hover:bg-blue-50 cursor-pointer rounded items-center justify-between"
        ).on('click', lambda b=book_id, idx=chapter_idx: self.select_chapter(b, idx)):
            with ui.column().classes("gap-0 flex-1"):
                ui.label(f"{chapter_idx + 1}. {chapter_title[:40]}").classes("text-sm")
                ui.label(f"{word_count:,} words | {duration_str}").classes("text-xs text-gray-400")

            if has_audio:
                ui.badge("Audio", color="green").props("outline size=sm")
            else:
                ui.badge("No Audio", color="grey").props("outline size=sm")

    def select_chapter(self, book_id: str, chapter_idx: int):
        """Select and load a specific chapter from a book."""
        try:
            # Get chapter text
            content = library.get_chapter_text(book_id, chapter_idx)
            if content is None:
                ui.notify("Chapter not found", type="warning")
                return

            # Extract plain text from markdown
            text = extract_text_from_markdown(content)
            self.text_preview.value = text

            # Update selection state
            self.current_item_id = book_id
            self.current_chapter_idx = chapter_idx

            # Get book metadata to check for chapter audio
            book_meta = library.get_item(book_id)
            if book_meta:
                chapters = book_meta.get('chapters', [])
                if chapter_idx < len(chapters):
                    audio_path = chapters[chapter_idx].get('audio_path')
                    if audio_path and Path(audio_path).exists():
                        self.current_audio_path = audio_path
                        self.update_audio_player(audio_path)
                    else:
                        self.current_audio_path = None
                        self.update_audio_player(None)

            # Highlight the book in library (expansion doesn't need highlight like cards)
            self._highlight_card(book_id)

            # Update generation section for this chapter
            self.update_generation_section(book_id, chapter_idx)

            # Show chapter info in status
            chapter_title = book_meta['chapters'][chapter_idx].get('title', f'Chapter {chapter_idx + 1}') if book_meta else f'Chapter {chapter_idx + 1}'
            ui.notify(f"Selected: {chapter_title}", type="info")

        except Exception as e:
            ui.notify(f"Error loading chapter: {str(e)}", type="negative")

    def _on_card_click(self, item_id: str):
        """Handle library card click."""
        self._highlight_card(item_id)
        self.select_item(item_id)

    def _highlight_card(self, item_id: str):
        """Highlight the selected card/expansion and unhighlight others."""
        for card_id, element in self.library_cards.items():
            if card_id == item_id:
                # Add highlight - works for both cards and expansions
                element.classes(remove="hover:bg-blue-50", add="bg-blue-100 ring-2 ring-blue-400")
            else:
                # Remove highlight
                element.classes(remove="bg-blue-100 ring-2 ring-blue-400", add="hover:bg-blue-50")

    def select_item(self, item_id: str):
        """Load a library item (document, not book chapter)."""
        if not item_id:
            return

        try:
            item = library.get_item(item_id)
            if item is None:
                return

            content = library.get_document_content(item_id)
            text = extract_text_from_markdown(content)
            self.text_preview.value = text

            self.current_item_id = item_id
            self.current_chapter_idx = None  # Reset chapter selection (this is a document, not a book chapter)

            if library.has_audio(item_id):
                audio_path = str(library.get_audio_path(item_id))
                self.current_audio_path = audio_path
                self.update_audio_player(audio_path)
            else:
                self.current_audio_path = None
                self.update_audio_player(None)

            # Update generation section for this document
            self.update_generation_section(item_id)

        except Exception as e:
            ui.notify(f"Error loading: {str(e)}", type="negative")

    def update_generation_section(self, item_id: str, chapter_idx: int = None):
        """Update generation section for selected item or chapter."""
        item = library.get_item(item_id)
        if item is None:
            return

        if 'chapters' in item and chapter_idx is not None:
            # Book chapter selected
            chapter = item['chapters'][chapter_idx]
            chapter_title = chapter.get('title', f'Chapter {chapter_idx + 1}')
            title = f"{item['title']} - Ch. {chapter_idx + 1}: {chapter_title}"
            has_audio = chapter.get('audio_path') is not None
        else:
            # Document selected
            title = item['title']
            has_audio = library.has_audio(item_id)

        # Update UI
        self.gen_selected_label.text = f"Selected: {title}"
        self.voice_row.classes(remove="hidden")
        self.settings_row.classes(remove="hidden")
        self.gen_button.classes(remove="hidden")

        # Change button text based on whether audio exists
        self.gen_button.text = "Regenerate Audio" if has_audio else "Generate Audio"

        # Store selection for generation
        self._gen_item_id = item_id
        self._gen_chapter_idx = chapter_idx

    async def on_generate_from_section(self):
        """Generate audio for selected item/chapter from the Generate Audio section."""
        if not hasattr(self, '_gen_item_id') or self._gen_item_id is None:
            ui.notify("Select an item first", type="warning")
            return

        # Capture client context before any background tasks
        client = context.client

        # Determine voice settings
        voice_prompt = None
        speaker = None

        # Get model size
        model_size = "0.6B" if "0.6B" in self.gen_model.value else "1.7B"

        # Check if using clone voice
        if self.clone_voice_select.value != "None":
            # Voice cloning mode
            if self.clone_voice_select.value == "custom":
                # Custom upload - should already have clone_audio_path and clone_transcript
                if not self.clone_audio_path:
                    ui.notify("Upload reference audio for custom voice", type="warning")
                    return
                if not self.clone_transcript:
                    ui.notify("Enter transcript for custom voice", type="warning")
                    return
            else:
                # Preset clone sample - load if not already loaded
                sample_name = self.clone_voice_select.value
                if sample_name in CLONE_SAMPLES and CLONE_SAMPLES[sample_name] is not None:
                    sample = CLONE_SAMPLES[sample_name]
                    self.clone_audio_path = str(VOICE_SAMPLES_DIR / sample["audio"])
                    self.clone_transcript = (VOICE_SAMPLES_DIR / sample["transcript"]).read_text()
                else:
                    ui.notify(f"Clone sample not found: {sample_name}", type="negative")
                    return

            # Create voice clone prompt
            self.status_label.text = "Creating voice clone prompt..."
            self.status_label.classes(remove="text-gray-500 text-green-600", add="text-blue-600")
            await asyncio.sleep(0)  # Yield to UI

            try:
                voice_prompt = await run.io_bound(
                    create_voice_clone_prompt,
                    self.clone_audio_path,
                    self.clone_transcript,
                    model_size,
                )
            except Exception as e:
                with client:
                    ui.notify(f"Failed to create voice clone prompt: {e}", type="negative")
                    self.reset_status()
                return
        else:
            # Stock voice mode
            if self.stock_voice_select.value == "None":
                ui.notify("Select a voice (stock or clone)", type="warning")
                return
            speaker = VOICES.get(self.stock_voice_select.value, "ryan")

        # Get language
        language = self.gen_language.value.lower()

        # Get the text to generate
        if self._gen_chapter_idx is not None:
            # Chapter generation
            content = library.get_chapter_text(self._gen_item_id, self._gen_chapter_idx)
            if content is None:
                ui.notify("Chapter content not found", type="negative")
                return
            text = extract_text_from_markdown(content)
            await self._generate_chapter_audio(
                self._gen_item_id,
                self._gen_chapter_idx,
                text,
                language,
                model_size,
                voice_prompt,
                speaker,
            )
        else:
            # Document generation
            content = library.get_document_content(self._gen_item_id)
            if content is None:
                ui.notify("Document content not found", type="negative")
                return
            text = extract_text_from_markdown(content)
            await self._generate_document_audio(
                self._gen_item_id,
                text,
                language,
                model_size,
                voice_prompt,
                speaker,
            )

    async def _generate_document_audio(
        self,
        item_id: str,
        text: str,
        language: str,
        model_size: str,
        voice_prompt,
        speaker: str,
    ):
        """Generate audio for a document."""
        # Capture client context before background task (needed for UI ops after)
        client = context.client

        try:
            # Chunk text for TTS
            chunks = chunk_text(text)
            total_chunks = len(chunks)

            # Show progress card
            self.show_progress(total_chunks)
            await asyncio.sleep(0)  # Yield to UI event loop

            # Progress callback updates shared state (thread-safe)
            def progress_callback(current, total):
                self.progress_state.update(current, total)

            # Run TTS in thread pool
            wav, sr = await run.io_bound(
                generate_long_text,
                chunks,
                language,
                model_size,
                voice_prompt,
                speaker,
                progress_callback,
            )

            # Save audio
            temp_path = tempfile.mktemp(suffix=".wav")
            save_audio(wav, sr, temp_path)

            duration = get_audio_duration(temp_path)
            library.save_audio(item_id, temp_path, duration)

            # Track voice settings
            voice_settings = {
                "voice": speaker if speaker else "clone",
                "model_size": model_size,
                "mode": "clone" if voice_prompt is not None else "preset",
            }
            library.update_item(item_id, {
                "voice_settings": voice_settings,
                "language": language,
            })

            # Create timing data
            sentences = get_sentences(text)
            timing_data = create_simple_timing(sentences, duration)
            library.save_timing(item_id, timing_data)

            # Re-enter client context for UI operations after background task
            with client:
                # Hide progress and show completion
                self.hide_progress(duration)

                # Refresh library and reload item
                self.refresh_library()
                self._on_card_click(item_id)

                ui.notify(f"Audio generated: {duration:.1f}s", type="positive")

                # Reset status after delay
                ui.timer(5.0, lambda: self.reset_status(), once=True)

        except Exception as e:
            import traceback
            traceback.print_exc()
            with client:
                self.hide_progress()
                self.status_label.text = f"Error: {str(e)}"
                self.status_label.classes(remove="text-gray-500", add="text-red-600")
                ui.notify(f"Error: {str(e)}", type="negative")

    async def _generate_chapter_audio(
        self,
        book_id: str,
        chapter_idx: int,
        text: str,
        language: str,
        model_size: str,
        voice_prompt,
        speaker: str,
    ):
        """Generate audio for a book chapter."""
        # Capture client context before background task (needed for UI ops after)
        client = context.client

        try:
            # Get chapter title for notifications
            book_meta = library.get_item(book_id)
            chapter_title = "Chapter"
            if book_meta and 'chapters' in book_meta:
                chapters = book_meta['chapters']
                if chapter_idx < len(chapters):
                    chapter_title = chapters[chapter_idx].get('title', f'Chapter {chapter_idx + 1}')

            # Chunk text for TTS
            chunks = chunk_text(text)
            total_chunks = len(chunks)

            # Show progress card
            self.show_progress(total_chunks)
            await asyncio.sleep(0)  # Yield to UI event loop

            # Progress callback updates shared state (thread-safe)
            def progress_callback(current, total):
                self.progress_state.update(current, total)

            # Run TTS in thread pool
            wav, sr = await run.io_bound(
                generate_long_text,
                chunks,
                language,
                model_size,
                voice_prompt,
                speaker,
                progress_callback,
            )

            # Save audio
            temp_path = tempfile.mktemp(suffix=".wav")
            save_audio(wav, sr, temp_path)

            duration = get_audio_duration(temp_path)
            library.save_chapter_audio(book_id, chapter_idx, temp_path, duration)

            # Track voice settings at book level (chapters share voice)
            voice_settings = {
                "voice": speaker if speaker else "clone",
                "model_size": model_size,
                "mode": "clone" if voice_prompt is not None else "preset",
            }
            library.update_item(book_id, {
                "voice_settings": voice_settings,
                "language": language,
            })

            # Create timing data for this chapter
            sentences = get_sentences(text)
            timing_data = create_simple_timing(sentences, duration)
            library.save_chapter_timing(book_id, chapter_idx, timing_data)

            # Re-enter client context for UI operations after background task
            with client:
                # Hide progress and show completion
                self.hide_progress(duration)

                # Refresh library and reload chapter
                self.refresh_library()
                self.select_chapter(book_id, chapter_idx)

                ui.notify(f"Chapter audio generated: {chapter_title} ({duration:.1f}s)", type="positive")

                # Reset status after delay
                ui.timer(5.0, lambda: self.reset_status(), once=True)

        except Exception as e:
            import traceback
            traceback.print_exc()
            with client:
                self.hide_progress()
                self.status_label.text = f"Error: {str(e)}"
                self.status_label.classes(remove="text-gray-500", add="text-red-600")
                ui.notify(f"Error: {str(e)}", type="negative")

    def update_audio_player(self, audio_path: Optional[str]):
        """Update the audio player with native controls + extended speed buttons."""
        self.audio_container.clear()
        self.current_speed = getattr(self, 'current_speed', 1.0)

        with self.audio_container:
            if audio_path and Path(audio_path).exists():
                # Create unique element ID for this audio
                audio_id = f"audio-{id(self)}"

                # Build audio URL from path
                # Path could be: library/{item_id}/audio.wav (document)
                # Or: library/{item_id}/chapters/00-CHAPTER.m4a (book chapter)
                audio_path_obj = Path(audio_path)
                library_dir = Path(__file__).parent / "library"

                try:
                    # Get relative path from library directory
                    rel_path = audio_path_obj.relative_to(library_dir)
                    audio_url = f"/audio/{rel_path}"
                except ValueError:
                    # Path is not under library dir (e.g., absolute path from worktree)
                    # Try to extract the relative portion after "library/"
                    path_str = str(audio_path_obj)
                    if "/library/" in path_str:
                        rel_path = path_str.split("/library/", 1)[1]
                        audio_url = f"/audio/{rel_path}"
                    else:
                        # Fallback: use filename only (may not work)
                        audio_url = f"/audio/{audio_path_obj.name}"

                # Determine MIME type from extension
                ext = audio_path_obj.suffix.lower()
                mime_types = {
                    '.wav': 'audio/wav',
                    '.mp3': 'audio/mpeg',
                    '.m4a': 'audio/mp4',
                    '.ogg': 'audio/ogg',
                }
                mime_type = mime_types.get(ext, 'audio/wav')

                # Native HTML5 audio player (noplaybackrate hides native speed menu)
                ui.html(f'''
                    <audio id="{audio_id}" controls controlsList="noplaybackrate" style="width: 100%;">
                        <source src="{audio_url}" type="{mime_type}">
                        Your browser does not support the audio element.
                    </audio>
                ''', sanitize=False).classes('w-full')

                self.current_audio_id = audio_id

                # Extended speed control (for 2.5x, 3x beyond native menu)
                with ui.row().classes("w-full items-center gap-1 mt-2 flex-wrap"):
                    ui.label("Speed:").classes("text-sm text-gray-500 mr-1")
                    self.speed_buttons = {}
                    for label, speed in SPEED_OPTIONS.items():
                        is_active = (speed == self.current_speed)
                        btn = ui.button(
                            label,
                            on_click=lambda s=speed, l=label: self.set_speed(s, l)
                        ).props(f'flat dense size=sm {"color=primary" if is_active else ""}').classes("min-w-0 px-2")
                        self.speed_buttons[label] = btn

                # Apply current speed
                ui.timer(0.1, lambda: self.apply_speed(self.current_speed), once=True)
            else:
                ui.label("No audio available").classes("text-gray-500 italic")

    def set_speed(self, speed: float, label: str):
        """Set playback speed and update button states."""
        self.current_speed = speed
        self.apply_speed(speed)
        # Update button highlights
        for btn_label, btn in self.speed_buttons.items():
            if btn_label == label:
                btn.props('color=primary')
            else:
                btn.props(remove='color=primary')

    def apply_speed(self, speed: float):
        """Apply playback speed to current audio player."""
        if hasattr(self, 'current_audio_id'):
            ui.run_javascript(f'''
                const audio = document.getElementById("{self.current_audio_id}");
                if (audio) {{ audio.playbackRate = {speed}; }}
            ''')

    def delete_item(self):
        """Delete current library item."""
        if not self.current_item_id:
            ui.notify("No item selected", type="warning")
            return

        try:
            library.delete_item(self.current_item_id)
            ui.notify("Item deleted", type="positive")
            self.refresh_library()
        except Exception as e:
            ui.notify(f"Error: {str(e)}", type="negative")

    async def _delete_single_item(self, item_id: str):
        """Delete a specific library item with confirmation dialog."""
        # Get item title for confirmation message
        item = library.get_item(item_id)
        title = item.get('title', 'this item') if item else 'this item'

        # Show confirmation dialog
        confirmed = [False]

        with ui.dialog() as dialog, ui.card():
            ui.label(f"Delete '{title}'?").classes("text-lg font-semibold")
            ui.label("This action cannot be undone.").classes("text-gray-500")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                def confirm_delete():
                    confirmed[0] = True
                    dialog.close()

                ui.button("Delete", on_click=confirm_delete, color="red")

        dialog.open()
        await dialog

        if not confirmed[0]:
            return

        try:
            library.delete_item(item_id)
            ui.notify("Item deleted", type="positive")

            # Clear selection if deleted item was selected
            if self.current_item_id == item_id:
                self.current_item_id = None
                self.current_chapter_idx = None
                self.current_audio_path = None
                self.text_preview.value = ""
                self.update_audio_player(None)
                self.update_generation_section(None)

            self.refresh_library()
        except Exception as e:
            ui.notify(f"Error: {str(e)}", type="negative")

    async def add_and_generate(self, file_content: bytes, filename: str, title: str,
                                voice: str, lang: str, model_size: str,
                                voice_prompt=None):
        """Add document to library and generate audio."""
        if not file_content:
            ui.notify("No file uploaded", type="warning")
            return

        try:
            # Decode file content
            content = file_content.decode('utf-8')

            # Create library item
            item = library.create_item(content, filename, title if title.strip() else None)
            text = extract_text_from_markdown(content)
            stats = get_text_stats(text)
            item_id = item['id']

            ui.notify(f"Added: {item['title']} ({stats['words']} words)", type="positive")

            # Get speaker ID from voice name
            speaker = VOICES.get(voice, "ryan")

            # Get model size
            size = "0.6B" if "0.6B" in model_size else "1.7B"

            # Chunk text for TTS
            chunks = chunk_text(text)
            total_chunks = len(chunks)

            # Show progress card
            self.show_progress(total_chunks)
            await asyncio.sleep(0)  # Yield to UI event loop

            # Progress callback updates shared state (thread-safe)
            def progress_callback(current, total):
                self.progress_state.update(current, total)

            # Run TTS in thread pool to avoid blocking event loop
            wav, sr = await run.io_bound(
                generate_long_text,
                chunks,
                lang.lower(),    # language
                size,            # model_size
                voice_prompt,    # voice_prompt (None for preset, or clone prompt)
                speaker,         # speaker (used if voice_prompt is None)
                progress_callback,
            )

            # Save audio
            temp_path = tempfile.mktemp(suffix=".wav")
            save_audio(wav, sr, temp_path)

            duration = get_audio_duration(temp_path)
            library.save_audio(item_id, temp_path, duration)

            # Track voice settings including clone mode
            voice_settings = {
                "voice": speaker,
                "model_size": size,
                "mode": "clone" if voice_prompt is not None else "preset",
            }
            library.update_item(item_id, {
                "voice_settings": voice_settings,
                "language": lang.lower(),
            })

            # Create timing data
            sentences = get_sentences(text)
            timing_data = create_simple_timing(sentences, duration)
            library.save_timing(item_id, timing_data)

            # Hide progress and show completion
            self.hide_progress(duration)

            # Refresh and select new item
            self.refresh_library()
            self._on_card_click(item_id)

            # Reset status after delay
            ui.timer(5.0, lambda: self.reset_status(), once=True)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.hide_progress()  # Hide progress on error
            self.status_label.text = f"Error: {str(e)}"
            self.status_label.classes(remove="text-gray-500", add="text-red-600")
            ui.notify(f"Error: {str(e)}", type="negative")

    def reset_status(self):
        """Reset status label to default."""
        self.status_label.text = "Ready"
        self.status_label.classes(remove="text-green-600 text-red-600 text-blue-600", add="text-gray-500")

    async def show_duplicate_dialog(self, existing_title: str) -> str:
        """Show dialog for duplicate document. Returns 'override', 'cancel', or None."""
        result = {'choice': None}

        with ui.dialog() as dialog, ui.card():
            ui.label("Duplicate Document Detected").classes("text-lg font-bold")
            ui.label(f'A document with identical content already exists:').classes("mt-2")
            ui.label(f'"{existing_title}"').classes("font-semibold text-blue-600")
            ui.label("What would you like to do?").classes("mt-2")

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                def on_cancel():
                    result['choice'] = 'cancel'
                    dialog.close()

                def on_override():
                    result['choice'] = 'override'
                    dialog.close()

                ui.button("Cancel", on_click=on_cancel).props("flat")
                ui.button("Replace Existing", on_click=on_override, color="red")

        dialog.open()
        await dialog
        return result['choice']

    async def _show_add_to_library_dialog(self):
        """Show popup dialog for adding files to library."""
        result = {'item': None}
        upload_state = {'content': None, 'filename': None, 'is_epub': False, 'epub_parsed': None}

        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Add to Library").classes("text-lg font-bold")

            # File upload
            title_input = ui.input(
                label="Title (auto-extracted)",
                placeholder="Will be extracted from file",
            ).classes("w-full")

            async def on_upload(e):
                file_bytes = await e.file.read()
                upload_state['content'] = file_bytes
                upload_state['filename'] = e.file.name
                upload_state['is_epub'] = e.file.name.lower().endswith('.epub')

                try:
                    if upload_state['is_epub']:
                        title, content, chapters = parse_epub_content(file_bytes)
                        upload_state['epub_parsed'] = (title, content, chapters)
                        title_input.value = title
                        word_count = sum(ch.get('word_count', 0) for ch in chapters)
                        ui.notify(f"EPUB loaded: {len(chapters)} chapters, {word_count:,} words", type="positive")
                    else:
                        content = file_bytes.decode('utf-8')
                        # Extract title
                        extracted_title = None
                        for line in content.strip().split('\n'):
                            if line.startswith('#'):
                                extracted_title = line.lstrip('#').strip()
                                break
                        if not extracted_title:
                            extracted_title = Path(e.file.name).stem
                        title_input.value = extracted_title
                        word_count = len(content.split())
                        ui.notify(f"File loaded: {word_count:,} words", type="positive")
                except Exception as ex:
                    ui.notify(f"Error: {ex}", type="warning")
                    title_input.value = Path(e.file.name).stem

            ui.upload(
                label="Upload .md, .txt, or .epub",
                auto_upload=True,
                max_files=1,
                on_upload=on_upload,
            ).classes("w-full").props('accept=".md,.txt,.epub"')

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                async def on_add():
                    if upload_state['content'] is None:
                        ui.notify("Please upload a file first", type="warning")
                        return

                    try:
                        filename = upload_state['filename']
                        title = title_input.value.strip() if title_input.value else None

                        if upload_state['is_epub']:
                            epub_title, content, chapters = upload_state['epub_parsed']
                            if title is None:
                                title = epub_title

                            content_hash = library.compute_content_hash(content)
                            existing = library.find_by_hash(content_hash)

                            if existing:
                                dialog.close()
                                dup_result = await self.show_duplicate_dialog(existing['title'])
                                if dup_result == 'cancel':
                                    ui.notify("Upload cancelled", type="info")
                                    return
                                elif dup_result == 'override':
                                    library.delete_item(existing['id'])

                            lib_chapters = [
                                {'title': ch['title'], 'content': ch['content'], 'word_count': ch.get('word_count', 0)}
                                for ch in chapters if ch['content'].strip()
                            ]

                            item = library.create_book(
                                title=title,
                                filename=filename,
                                chapters=lib_chapters,
                                content_hash=content_hash,
                                source_type='epub',
                            )
                            result['item'] = item
                            ui.notify(f"Added: {title} ({item['chapter_count']} chapters)", type="positive")
                        else:
                            content = upload_state['content'].decode('utf-8')
                            content_hash = library.compute_content_hash(content)
                            existing = library.find_by_hash(content_hash)

                            if existing:
                                dialog.close()
                                dup_result = await self.show_duplicate_dialog(existing['title'])
                                if dup_result == 'cancel':
                                    ui.notify("Upload cancelled", type="info")
                                    return
                                elif dup_result == 'override':
                                    library.delete_item(existing['id'])

                            text = extract_text_from_markdown(content)

                            if should_auto_chunk(text):
                                chapters = split_into_chapters(content)
                                if title is None:
                                    for line in content.strip().split('\n'):
                                        if line.startswith('#'):
                                            title = line.lstrip('#').strip()
                                            break
                                    if not title:
                                        title = Path(filename).stem

                                item = library.create_book(
                                    title=title,
                                    filename=filename,
                                    chapters=chapters,
                                    content_hash=content_hash,
                                )
                            else:
                                item = library.create_item(content, filename, title)

                            result['item'] = item
                            stats = get_text_stats(text)
                            ui.notify(f"Added: {item['title']} ({stats['words']} words)", type="positive")

                        dialog.close()
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        ui.notify(f"Error: {str(e)}", type="negative")

                ui.button("Add", on_click=on_add, color="primary")

        dialog.open()
        await dialog

        if result['item']:
            self.refresh_library()
            self._on_card_click(result['item']['id'])

    def show_progress(self, total_chunks: int):
        """Show the progress card and start tracking."""
        self.progress_state.start(total_chunks)
        self.progress_card.classes(remove="hidden")
        self.status_label.classes(add="hidden")
        self.progress_bar.value = 0
        self.progress_text.text = "Loading model..."
        self.progress_time.text = f"0/{total_chunks} chunks"

        # Activate the progress timer (created during build_ui)
        if self.progress_timer:
            self.progress_timer.activate()

    def update_progress_ui(self):
        """Update progress UI from shared state (called by timer)."""
        if not self.progress_state.is_generating:
            return

        state = self.progress_state
        self.progress_bar.value = state.progress_fraction
        elapsed = state.elapsed_seconds

        if state.current_chunk == 0:
            # Still on first chunk - model loading
            self.progress_text.text = "Loading model & generating first chunk..."
            self.progress_time.text = f"{elapsed:.0f}s"
        else:
            self.progress_text.text = f"Chunk {state.current_chunk}/{state.total_chunks}"
            remaining = state.estimated_remaining
            self.progress_time.text = f"{elapsed:.0f}s elapsed • ~{remaining:.0f}s remaining"

    def hide_progress(self, final_duration: float = None):
        """Hide progress card and stop timer."""
        self.progress_state.stop()

        # Deactivate the progress timer (don't cancel, it's reused)
        if self.progress_timer:
            self.progress_timer.deactivate()

        self.progress_card.classes(add="hidden")
        self.status_label.classes(remove="hidden")

        if final_duration is not None:
            elapsed = self.progress_state.elapsed_seconds
            self.status_label.text = f"Generated {final_duration:.1f}s audio in {elapsed:.0f}s"
            self.status_label.classes(remove="text-gray-500", add="text-green-600")

    def _build_clone_options(self) -> dict:
        """Build clone voice dropdown options with transcript previews."""
        options = {"None": "None"}
        for name, data in CLONE_SAMPLES.items():
            if data is None:
                # Custom upload option
                options["custom"] = "Custom - Upload..."
            else:
                # Load transcript preview from file
                try:
                    transcript_path = VOICE_SAMPLES_DIR / data["transcript"]
                    transcript = transcript_path.read_text()
                    preview = transcript[:35] + "..." if len(transcript) > 35 else transcript
                    options[name] = f'{name} - "{preview}"'
                except Exception:
                    options[name] = name
        return options

    def on_stock_voice_change(self, e):
        """Handle stock voice selection - clears clone voice if stock is selected."""
        if e.value != "None":
            self.clone_voice_select.value = "None"
            # Clear clone state
            self.clone_audio_path = None
            self.clone_transcript = None

    def on_clone_voice_change(self, e):
        """Handle clone voice selection - clears stock voice and loads sample."""
        if e.value != "None":
            self.stock_voice_select.value = "None"
            if e.value == "custom":
                self._show_custom_upload_dialog()
            else:
                self._load_clone_sample(e.value)

    def _load_clone_sample(self, sample_name: str):
        """Load a preset clone sample's audio and transcript."""
        if sample_name not in CLONE_SAMPLES or CLONE_SAMPLES[sample_name] is None:
            return

        data = CLONE_SAMPLES[sample_name]
        audio_path = VOICE_SAMPLES_DIR / data["audio"]
        transcript_path = VOICE_SAMPLES_DIR / data["transcript"]

        if audio_path.exists() and transcript_path.exists():
            self.clone_audio_path = str(audio_path)
            self.clone_transcript = transcript_path.read_text()
            ui.notify(f"Loaded voice sample: {sample_name}", type="positive")
        else:
            ui.notify(f"Sample files not found for {sample_name}", type="negative")
            self.clone_voice_select.value = "None"

    def _show_custom_upload_dialog(self):
        """Show dialog for custom voice upload with audio file and transcript."""

        async def handle_dialog():
            result = {'audio': None, 'transcript': None}

            with ui.dialog() as dialog, ui.card().classes("w-96"):
                ui.label("Upload Custom Voice Sample").classes("text-lg font-bold")
                ui.label("Provide 3-30 seconds of clean speech audio and its transcript.").classes(
                    "text-sm text-gray-600 mt-1"
                )

                # Audio upload
                audio_content = {'data': None, 'name': None}

                async def on_audio_upload(e):
                    audio_content['data'] = await e.file.read()
                    audio_content['name'] = e.file.name
                    ui.notify(f"Audio loaded: {e.file.name}", type="positive")

                ui.label("Reference Audio").classes("mt-4 font-semibold")
                ui.upload(
                    label="Upload .wav or .mp3 (3-30 seconds)",
                    auto_upload=True,
                    max_files=1,
                    on_upload=on_audio_upload,
                ).classes("w-full").props('accept=".wav,.mp3"')

                # Transcript input
                ui.label("Transcript").classes("mt-4 font-semibold")
                transcript_input = ui.textarea(
                    label="Exact text spoken in the audio",
                    placeholder="Enter the exact words spoken in the reference audio...",
                ).classes("w-full").props("rows=3")

                # Buttons
                with ui.row().classes("w-full justify-end gap-2 mt-4"):
                    def on_cancel():
                        result['audio'] = None
                        result['transcript'] = None
                        dialog.close()

                    def on_confirm():
                        if audio_content['data'] is None:
                            ui.notify("Please upload an audio file", type="warning")
                            return
                        if not transcript_input.value or not transcript_input.value.strip():
                            ui.notify("Please enter the transcript", type="warning")
                            return

                        result['audio'] = audio_content
                        result['transcript'] = transcript_input.value.strip()
                        dialog.close()

                    ui.button("Cancel", on_click=on_cancel).props("flat")
                    ui.button("Use This Voice", on_click=on_confirm, color="primary")

            dialog.open()
            await dialog

            return result

        async def process_upload():
            result = await handle_dialog()

            if result['audio'] is not None and result['transcript'] is not None:
                # Save audio to temp file
                import tempfile
                suffix = Path(result['audio']['name']).suffix
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                temp_file.write(result['audio']['data'])
                temp_file.close()

                self.clone_audio_path = temp_file.name
                self.clone_transcript = result['transcript']
                ui.notify("Custom voice sample ready", type="positive")
            else:
                # User cancelled - reset to None
                self.clone_voice_select.value = "None"
                self.clone_audio_path = None
                self.clone_transcript = None

        # Run the async dialog
        asyncio.create_task(process_upload())

    def build_ui(self):
        """Build the main UI."""
        # Add screen recording JavaScript and hotkey handler
        ui.add_body_html('''
        <script>
        (function() {
            let mediaRecorder = null;
            let recordedChunks = [];
            let isRecording = false;
            let recordingStream = null;

            function stopAndSave() {
                if (!isRecording) return;

                isRecording = false;
                document.getElementById('recording-indicator').style.display = 'none';

                if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                    mediaRecorder.stop();
                } else {
                    // MediaRecorder already stopped, save directly
                    saveRecording();
                }
            }

            function saveRecording() {
                if (recordedChunks.length === 0) {
                    console.log('No recorded data to save');
                    return;
                }

                const fileExt = window._recordingFileExt || 'webm';
                const mimeType = fileExt === 'mp4' ? 'video/mp4' : 'video/webm';

                const blob = new Blob(recordedChunks, { type: mimeType });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
                a.download = `readaloud-${timestamp}.${fileExt}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);

                // Cleanup after short delay
                setTimeout(() => URL.revokeObjectURL(url), 1000);

                // Stop all tracks
                if (recordingStream) {
                    recordingStream.getTracks().forEach(track => track.stop());
                    recordingStream = null;
                }

                recordedChunks = [];
                console.log('Recording saved as ' + fileExt.toUpperCase() + '!');
            }

            window.toggleRecording = async function() {
                if (isRecording) {
                    stopAndSave();
                } else {
                    // Start recording
                    try {
                        recordingStream = await navigator.mediaDevices.getDisplayMedia({
                            video: true,
                            audio: true,
                            selfBrowserSurface: 'include',
                            preferCurrentTab: true
                        });

                        recordedChunks = [];

                        // Prefer MP4 for X/Twitter compatibility, fall back to WebM
                        let mimeType = 'video/webm';
                        let fileExt = 'webm';
                        if (MediaRecorder.isTypeSupported('video/mp4;codecs=avc1,mp4a.40.2')) {
                            mimeType = 'video/mp4;codecs=avc1,mp4a.40.2';
                            fileExt = 'mp4';
                        } else if (MediaRecorder.isTypeSupported('video/mp4')) {
                            mimeType = 'video/mp4';
                            fileExt = 'mp4';
                        }
                        window._recordingFileExt = fileExt;

                        mediaRecorder = new MediaRecorder(recordingStream, { mimeType: mimeType });
                        console.log('Recording with format:', mimeType);

                        mediaRecorder.ondataavailable = function(e) {
                            if (e.data.size > 0) {
                                recordedChunks.push(e.data);
                            }
                        };

                        mediaRecorder.onstop = function() {
                            saveRecording();
                        };

                        // Handle user clicking Chrome's "Stop sharing" button
                        recordingStream.getVideoTracks()[0].onended = function() {
                            console.log('User stopped sharing');
                            if (isRecording) {
                                stopAndSave();
                            }
                        };

                        // Request data every second to ensure we capture everything
                        mediaRecorder.start(1000);
                        isRecording = true;
                        document.getElementById('recording-indicator').style.display = 'flex';
                        console.log('Recording started!');

                    } catch (err) {
                        console.error('Recording failed:', err);
                        isRecording = false;
                    }
                }
            };

            // Hotkey: 'D' key to toggle debug recording (only when not in input field)
            document.addEventListener('keydown', function(e) {
                // Ignore if typing in input/textarea
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

                if (e.key.toLowerCase() === 'd') {
                    e.preventDefault();
                    window.toggleRecording();
                }
            });
        })();
        </script>
        ''')

        # Recording indicator (fixed position, hidden by default)
        ui.html('''
        <div id="recording-indicator" style="display: none; position: fixed; top: 16px; right: 16px; z-index: 9999; background: #dc2626; color: white; padding: 12px 20px; border-radius: 9999px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); align-items: center; gap: 10px; font-weight: 500;">
            <span style="animation: pulse 1s infinite; font-size: 18px;">&#9679;</span>
            <span>RECORDING - Press D to stop</span>
        </div>
        <style>
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.3; }
            }
        </style>
        ''', sanitize=False)

        # Header
        with ui.column().classes("w-full max-w-4xl mx-auto p-4"):
            ui.markdown("# ReadAloud v5").classes("text-3xl font-bold")
            ui.label("Upload documents and generate audio.").classes("text-gray-600")

            ui.separator().classes("my-4")

            # Library section (collapsible)
            with ui.expansion("Library", icon="folder", value=True).classes("w-full"):
                # Scrollable library card container (resizable, no max height)
                self.library_scroll = ui.scroll_area().classes("w-full border rounded").style("height: 600px; resize: vertical; overflow: auto")
                with self.library_scroll:
                    self.library_container = ui.column().classes("w-full gap-1 p-1")

                # Initial load of library cards
                self.refresh_library()

            ui.separator().classes("my-4")

            # Text preview
            ui.markdown("### Document Preview").classes("text-xl font-semibold")

            self.text_preview = ui.textarea(
                label="Text",
                placeholder="Select a document from the library...",
            ).classes("w-full").props("readonly outlined rows=10")

            ui.separator().classes("my-4")

            # Audio player section
            ui.markdown("### Audio Player").classes("text-xl font-semibold")

            # Custom audio container (includes integrated speed control)
            self.audio_container = ui.column().classes("w-full gap-2")
            with self.audio_container:
                ui.label("No audio available").classes("text-gray-500 italic")

            ui.separator().classes("my-4")

            # Status and Progress section
            with ui.column().classes("w-full gap-2"):
                # Simple status line (shown when not generating)
                with ui.row().classes("w-full items-center gap-2"):
                    ui.icon("info").classes("text-gray-400")
                    self.status_label = ui.label("Ready").classes("text-gray-500")

                # Progress card (shown during generation)
                self.progress_card = ui.card().classes("w-full hidden")
                with self.progress_card:
                    with ui.column().classes("w-full gap-3 p-2"):
                        with ui.row().classes("w-full items-center gap-3"):
                            ui.spinner("audio", size="md", color="primary")
                            ui.label("Generating Audio").classes("text-lg font-semibold text-primary")

                        self.progress_bar = ui.linear_progress(value=0, show_value=False).classes("w-full")

                        with ui.row().classes("w-full justify-between text-sm"):
                            self.progress_text = ui.label("Starting...").classes("text-gray-600")
                            self.progress_time = ui.label("").classes("text-gray-500")

                # Create progress timer during build (inactive until generation starts)
                self.progress_timer = ui.timer(0.5, self.update_progress_ui, active=False)

            ui.separator().classes("my-4")

            # Generate Audio section (collapsible)
            with ui.expansion("Generate Audio", icon="audiotrack", value=True).classes("w-full") as self.gen_expansion:
                self.generation_container = ui.column().classes("w-full gap-4 p-4")
                with self.generation_container:
                    # Selected item label (shown when no item selected)
                    self.gen_selected_label = ui.label(
                        "Select an item from the library"
                    ).classes("text-gray-500 italic")

                    # Voice selection row (hidden until item selected)
                    self.voice_row = ui.row().classes("w-full gap-4 hidden")
                    with self.voice_row:
                        # Stock voice dropdown with "None" as first option
                        stock_options = ["None"] + list(VOICES.keys())
                        self.stock_voice_select = ui.select(
                            label="Stock Voice",
                            options=stock_options,
                            value="Ryan (English Male)",
                            on_change=self.on_stock_voice_change,
                        ).classes("flex-1")

                        # Clone voice dropdown with transcript previews
                        self.clone_voice_select = ui.select(
                            label="Clone Voice",
                            options=self._build_clone_options(),
                            value="None",
                            on_change=self.on_clone_voice_change,
                        ).classes("flex-1")

                    # Settings row (hidden until item selected)
                    self.settings_row = ui.row().classes("w-full gap-4 hidden")
                    with self.settings_row:
                        self.gen_language = ui.select(
                            label="Language",
                            options=LANGUAGES,
                            value="English",
                        ).classes("flex-1")

                        self.gen_model = ui.select(
                            label="Model",
                            options=["0.6B (faster)", "1.7B (better)"],
                            value="1.7B (better)",
                        ).classes("flex-1")

                    # Generate button (hidden until item selected)
                    # Note: Pass async function directly to on_click - NiceGUI handles it properly
                    self.gen_button = ui.button(
                        "Generate Audio",
                        on_click=self.on_generate_from_section,
                        color="primary",
                        icon="audiotrack",
                    ).classes("w-full hidden")

            ui.separator().classes("my-4")

            # Add to Library button (opens popup dialog)
            ui.button(
                "Add to Library",
                on_click=self._show_add_to_library_dialog,
                color="primary",
                icon="add",
            ).classes("w-full")


# Serve audio files from the library directory
# Use path:file_path to capture paths with subdirectories (e.g., {item_id}/chapters/{filename})
@app.get('/audio/{file_path:path}')
async def serve_audio(file_path: str):
    """Serve audio files from library. Handles both document and chapter audio."""
    from fastapi.responses import FileResponse
    from fastapi import HTTPException

    library_dir = Path(__file__).parent / "library"
    audio_path = library_dir / file_path

    # Security: ensure path doesn't escape library directory
    try:
        audio_path.resolve().relative_to(library_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if audio_path.exists():
        # Determine MIME type from extension
        ext = audio_path.suffix.lower()
        mime_types = {
            '.wav': 'audio/wav',
            '.mp3': 'audio/mpeg',
            '.m4a': 'audio/mp4',
            '.ogg': 'audio/ogg',
        }
        mime_type = mime_types.get(ext, 'audio/octet-stream')

        return FileResponse(
            audio_path,
            media_type=mime_type,
            filename=audio_path.name,
        )

    raise HTTPException(status_code=404, detail="Audio file not found")


# Create and run the app
read_aloud = ReadAloudApp()


@ui.page("/")
def main_page():
    """Main page."""
    read_aloud.build_ui()


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="ReadAloud v5",
        host="127.0.0.1",
        port=8080,
        reload=False,
        show=False,
    )
