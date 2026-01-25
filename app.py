"""
ReadAloud v2 - Local TTS Reader with Library Management
Main Gradio application with library management.
"""

import gradio as gr
import tempfile
import os
from typing import Optional, Tuple, List, Any

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

# Available voices (CustomVoice model preset speakers)
VOICES = [
    ("Ryan (English Male)", "ryan"),
    ("Aiden (English Male)", "aiden"),
    ("Serena (Chinese Female)", "serena"),
    ("Vivian (Chinese Female)", "vivian"),
    ("Uncle Fu (Chinese Male)", "uncle_fu"),
    ("Dylan (Beijing Male)", "dylan"),
    ("Eric (Sichuan Male)", "eric"),
    ("Ono Anna (Japanese Female)", "ono_anna"),
    ("Sohee (Korean Female)", "sohee"),
]



def get_library_items_for_display() -> List[Tuple[str, str]]:
    """Get library items formatted for Gradio dropdown."""
    items = library.get_all_items()
    if not items:
        return []
    return [(f"{item['title']} ({item['word_count']} words)", item['id']) for item in items]


def refresh_library_list():
    """Refresh the library dropdown choices."""
    items = get_library_items_for_display()
    if items:
        return gr.update(choices=items, value=items[0][1])
    return gr.update(choices=[], value=None)


def select_library_item(item_id: str) -> Tuple[str, Optional[str], str]:
    """Load a library item for viewing/playback."""
    if not item_id:
        return "", None, ""

    try:
        item = library.get_item(item_id)
        if item is None:
            return "", None, ""

        content = library.get_document_content(item_id)
        text = extract_text_from_markdown(content)

        audio_path = None
        if library.has_audio(item_id):
            audio_path = str(library.get_audio_path(item_id))

        return text, audio_path, item_id
    except Exception as e:
        gr.Warning(f"Error loading: {str(e)}")
        return "", None, ""


def delete_library_item(item_id: str) -> Tuple[Any, str, Optional[str]]:
    """Delete a library item."""
    if not item_id:
        gr.Warning("No item selected")
        return refresh_library_list(), "", None

    try:
        library.delete_item(item_id)
        gr.Info("Item deleted")
        return refresh_library_list(), "", None
    except Exception as e:
        gr.Warning(f"Error: {str(e)}")
        return refresh_library_list(), "", None




# Build Gradio Interface
library.init_library()

with gr.Blocks(title="ReadAloud v2") as app:

    current_item_id = gr.State("")

    gr.Markdown("# ReadAloud v2\nUpload documents and generate audio.")

    # Library section
    gr.Markdown("### Library")

    library_dropdown = gr.Dropdown(
        label="Select Document",
        choices=get_library_items_for_display(),
        interactive=True,
    )

    with gr.Row():
        refresh_btn = gr.Button("Refresh", size="sm")
        delete_btn = gr.Button("Delete", size="sm", variant="stop")

    # Document Preview
    gr.Markdown("### Document Preview")

    text_preview = gr.Textbox(
        label="Text",
        lines=10,
        interactive=False,
        placeholder="Select a document from the library...",
    )

    # Audio Player
    gr.Markdown("### Audio Player")

    audio_player = gr.Audio(
        label="",
        type="filepath",
        interactive=False,
    )

    gr.Markdown("*Use the built-in speed button (next to volume) for 0.5x-2x speeds*", elem_id="speed-hint")

    # Add New Document at bottom
    gr.Markdown("---")
    with gr.Accordion("Add New Document", open=False):
        file_upload = gr.File(
            label="Upload .md or .txt",
            file_types=[".md", ".txt"],
        )
        title_input = gr.Textbox(
            label="Title (optional)",
            placeholder="Auto-extracted if empty",
        )

        gr.Markdown("#### Voice Settings")
        voice_dropdown = gr.Dropdown(
            choices=VOICES,
            value="ryan",
            label="Voice",
        )
        with gr.Row():
            language = gr.Dropdown(
                choices=LANGUAGES,
                value="English",
                label="Language",
            )
            model_size = gr.Dropdown(
                choices=["0.6B (Fast)", "1.7B (Quality)"],
                value="0.6B (Fast)",
                label="Model",
            )

        add_btn = gr.Button("Add & Generate Audio", variant="primary")

    # Event handlers
    def add_and_generate(file, title, voice, lang, msize):
        """Add to library and generate audio."""
        if file is None:
            gr.Warning("No file uploaded")
            return gr.update(), "", "", None

        try:
            # Read file
            with open(file.name, 'r', encoding='utf-8') as f:
                content = f.read()

            filename = os.path.basename(file.name)
            item = library.create_item(content, filename, title if title.strip() else None)

            text = extract_text_from_markdown(content)
            stats = get_text_stats(text)
            item_id = item['id']

            gr.Info(f"Added: {item['title']} ({stats['words']} words). Generating audio...")

            # Generate audio
            size = "0.6B" if "0.6B" in msize else "1.7B"
            chunks = chunk_text(text)

            wav, sr = generate_long_text(
                chunks=chunks,
                language=lang.lower(),
                model_size=size,
                speaker=voice,
            )

            temp_path = tempfile.mktemp(suffix=".wav")
            save_audio(wav, sr, temp_path)

            duration = get_audio_duration(temp_path)
            library.save_audio(item_id, temp_path, duration)

            library.update_item(item_id, {
                "voice_settings": {"voice": voice, "model_size": size},
                "language": lang.lower(),
            })

            audio_path = str(library.get_audio_path(item_id))

            sentences = get_sentences(text)
            timing_data = create_simple_timing(sentences, duration)
            library.save_timing(item_id, timing_data)

            gr.Info(f"Generated {duration:.1f}s of audio!")

            # Return all updates at once
            items = get_library_items_for_display()
            return (
                gr.update(choices=items, value=item_id),
                text,
                item_id,
                audio_path,
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            gr.Warning(f"Error: {str(e)}")
            return gr.update(), "", "", None

    # Long-running operation - use hidden progress to avoid showing in multiple places
    # gr.Info() toasts provide user feedback during generation
    add_btn.click(
        fn=add_and_generate,
        inputs=[file_upload, title_input, voice_dropdown, language, model_size],
        outputs=[library_dropdown, text_preview, current_item_id, audio_player],
        show_progress="hidden",
    )

    refresh_btn.click(
        fn=refresh_library_list,
        outputs=[library_dropdown],
        show_progress="hidden",
    )

    library_dropdown.change(
        fn=select_library_item,
        inputs=[library_dropdown],
        outputs=[text_preview, audio_player, current_item_id],
        show_progress="hidden",
    )

    delete_btn.click(
        fn=delete_library_item,
        inputs=[current_item_id],
        outputs=[library_dropdown, text_preview, audio_player],
        show_progress="hidden",
    )



if __name__ == "__main__":
    app.launch(
        server_name="127.0.0.1",
        server_port=7860,
    )
