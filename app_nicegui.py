"""
ReadAloud v3 - NiceGUI Version
Local TTS Reader with Library Management.
Migrated from Gradio for better audio control and custom speed settings.
"""

from nicegui import ui, app, run
import asyncio
import tempfile
import time
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

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
)
from tts_engine import (
    generate_long_text,
    save_audio,
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
            self.current_audio_path = None
            self.text_preview.value = ""
            self.update_audio_player(None)
        elif self.current_item_id:
            # Re-highlight current selection
            self._highlight_card(self.current_item_id)

    def _create_library_card(self, item: dict):
        """Create a clickable card for a library item."""
        item_id = item['id']
        has_audio = item.get('audio_generated', False)

        card = ui.card().classes(
            "w-full cursor-pointer hover:bg-blue-50 transition-colors p-3"
        ).on('click', lambda i=item_id: self._on_card_click(i))

        with card:
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-0"):
                    ui.label(item['title']).classes("font-semibold text-sm truncate max-w-xs")
                    ui.label(f"{item['word_count']} words").classes("text-xs text-gray-500")

                # Audio status badge
                if has_audio:
                    ui.badge("Audio", color="green").props("outline")
                else:
                    ui.badge("No Audio", color="grey").props("outline")

        self.library_cards[item_id] = card

    def _on_card_click(self, item_id: str):
        """Handle library card click."""
        self._highlight_card(item_id)
        self.select_item(item_id)

    def _highlight_card(self, item_id: str):
        """Highlight the selected card and unhighlight others."""
        for card_id, card in self.library_cards.items():
            if card_id == item_id:
                card.classes(remove="hover:bg-blue-50", add="bg-blue-100 ring-2 ring-blue-400")
            else:
                card.classes(remove="bg-blue-100 ring-2 ring-blue-400", add="hover:bg-blue-50")

    def select_item(self, item_id: str):
        """Load a library item."""
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

            if library.has_audio(item_id):
                audio_path = str(library.get_audio_path(item_id))
                self.current_audio_path = audio_path
                self.update_audio_player(audio_path)
            else:
                self.current_audio_path = None
                self.update_audio_player(None)

        except Exception as e:
            ui.notify(f"Error loading: {str(e)}", type="negative")

    def update_audio_player(self, audio_path: Optional[str]):
        """Update the audio player with native controls + extended speed buttons."""
        self.audio_container.clear()
        self.current_speed = getattr(self, 'current_speed', 1.0)

        with self.audio_container:
            if audio_path and Path(audio_path).exists():
                # Create unique element ID for this audio
                audio_id = f"audio-{id(self)}"

                # Get item_id from path (library/{item_id}/audio.wav)
                item_id = Path(audio_path).parent.name

                # Native HTML5 audio player (noplaybackrate hides native speed menu)
                ui.html(f'''
                    <audio id="{audio_id}" controls controlsList="noplaybackrate" style="width: 100%;">
                        <source src="/audio/{item_id}/audio.wav" type="audio/wav">
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

    async def add_and_generate(self, file_content: bytes, filename: str, title: str,
                                voice: str, lang: str, model_size: str):
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
                None,            # voice_prompt
                speaker,         # speaker
                progress_callback,
            )

            # Save audio
            temp_path = tempfile.mktemp(suffix=".wav")
            save_audio(wav, sr, temp_path)

            duration = get_audio_duration(temp_path)
            library.save_audio(item_id, temp_path, duration)

            library.update_item(item_id, {
                "voice_settings": {"voice": speaker, "model_size": size},
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

    def show_progress(self, total_chunks: int):
        """Show the progress card and start tracking."""
        self.progress_state.start(total_chunks)
        self.progress_card.classes(remove="hidden")
        self.status_label.classes(add="hidden")
        self.progress_bar.value = 0
        self.progress_text.text = "Loading model..."
        self.progress_time.text = f"0/{total_chunks} chunks"

        # Start timer to poll progress
        self.progress_timer = ui.timer(0.5, self.update_progress_ui)

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

        if self.progress_timer:
            self.progress_timer.cancel()
            self.progress_timer = None

        self.progress_card.classes(add="hidden")
        self.status_label.classes(remove="hidden")

        if final_duration is not None:
            elapsed = self.progress_state.elapsed_seconds
            self.status_label.text = f"Generated {final_duration:.1f}s audio in {elapsed:.0f}s"
            self.status_label.classes(remove="text-gray-500", add="text-green-600")

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
            ui.markdown("# ReadAloud v3").classes("text-3xl font-bold")
            ui.label("Upload documents and generate audio.").classes("text-gray-600")

            ui.separator().classes("my-4")

            # Library section
            with ui.row().classes("w-full items-center justify-between"):
                ui.markdown("### Library").classes("text-xl font-semibold")
                with ui.row().classes("gap-2"):
                    ui.button("Refresh", on_click=self.refresh_library, icon="refresh").props("flat dense")
                    ui.button("Delete", on_click=self.delete_item, icon="delete", color="red").props("flat dense")

            # Scrollable library card container
            self.library_scroll = ui.scroll_area().classes("w-full border rounded").style("height: 300px")
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

            ui.separator().classes("my-4")

            # Add new document section
            with ui.expansion("Add New Document", icon="add").classes("w-full"):
                with ui.column().classes("w-full gap-4 p-4"):
                    # File upload handler - store content and filename for later use
                    async def handle_upload(e):
                        # NiceGUI 3.0+: e.file.name and e.file.read() (async)
                        self._uploaded_content = await e.file.read()
                        self._uploaded_filename = e.file.name

                        # Extract and prefill title from content
                        try:
                            content = self._uploaded_content.decode('utf-8')
                            extracted_title = None
                            lines = content.strip().split('\n')
                            for line in lines:
                                if line.startswith('#'):
                                    extracted_title = line.lstrip('#').strip()
                                    break
                            if extracted_title is None:
                                # Use filename stem as fallback
                                extracted_title = Path(e.file.name).stem
                            title_input.value = extracted_title
                        except Exception:
                            pass  # Keep title empty on decode errors

                        ui.notify(f"File ready: {e.file.name}", type="positive")

                    upload = ui.upload(
                        label="Upload .md or .txt (one file only)",
                        auto_upload=True,
                        max_files=1,
                        on_upload=handle_upload,
                    ).classes("w-full").props('accept=".md,.txt"')

                    title_input = ui.input(
                        label="Title (optional)",
                        placeholder="Auto-extracted if empty",
                    ).classes("w-full")

                    ui.markdown("#### Voice Settings").classes("font-semibold mt-4")

                    voice_select = ui.select(
                        options=list(VOICES.keys()),
                        value="Ryan (English Male)",
                        label="Voice",
                    ).classes("w-full")

                    with ui.row().classes("w-full gap-4"):
                        language_select = ui.select(
                            options=LANGUAGES,
                            value="English",
                            label="Language",
                        ).classes("flex-1")

                        model_select = ui.select(
                            options=["0.6B (Fast)", "1.7B (Quality)"],
                            value="0.6B (Fast)",
                            label="Model",
                        ).classes("flex-1")

                    async def on_generate():
                        if not hasattr(self, '_uploaded_content') or self._uploaded_content is None:
                            ui.notify("Please upload a file first", type="warning")
                            return

                        # Use stored file content and filename
                        file_content = self._uploaded_content
                        filename = self._uploaded_filename

                        # Check for duplicate content
                        try:
                            content = file_content.decode('utf-8')
                            content_hash = library.compute_content_hash(content)
                            existing = library.find_by_hash(content_hash)

                            if existing:
                                # Show duplicate dialog
                                result = await self.show_duplicate_dialog(existing['title'])
                                if result == 'cancel':
                                    ui.notify("Upload cancelled", type="info")
                                    return
                                elif result == 'override':
                                    # Delete existing item first
                                    library.delete_item(existing['id'])
                                    ui.notify(f"Replaced: {existing['title']}", type="info")
                        except Exception:
                            pass  # Continue with upload on any error

                        await self.add_and_generate(
                            file_content,
                            filename,
                            title_input.value,
                            voice_select.value,
                            language_select.value,
                            model_select.value,
                        )
                        # Clear upload state
                        self._uploaded_content = None
                        self._uploaded_filename = None
                        upload.reset()
                        title_input.value = ""

                    ui.button(
                        "Add & Generate Audio",
                        on_click=on_generate,
                        color="primary",
                    ).classes("w-full mt-4")


# Serve audio files from the library directory
@app.get('/audio/{item_id}/{filename}')
async def serve_audio(item_id: str, filename: str):
    """Serve audio files from library."""
    from fastapi.responses import FileResponse
    from fastapi import HTTPException

    library_dir = Path(__file__).parent / "library"
    audio_path = library_dir / item_id / filename

    if audio_path.exists():
        return FileResponse(
            audio_path,
            media_type="audio/wav",
            filename=filename,
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
        title="ReadAloud v3",
        host="127.0.0.1",
        port=8080,
        reload=False,
        show=False,
    )
