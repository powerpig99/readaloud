# CLAUDE.md

This file provides guidance to Claude Code when working with this repository. It serves as both development documentation and context for resuming work.

## Project Overview

ReadAloud v2 is a local-first text-to-speech web application with library management. Built in 7 hours using AI-augmented development.

**Current Status**: Two UI options available - Gradio (original) and NiceGUI (new, recommended).

## UI Options

### NiceGUI Version (Recommended)
- **File**: `app_nicegui.py`
- **Port**: http://127.0.0.1:8080
- **Features**: Full speed control (0.5x-3x), proper progress indicator, modern UI with Tailwind

### Gradio Version (Legacy)
- **File**: `app.py`
- **Port**: http://127.0.0.1:7860
- **Limitations**: Speed capped at 2x, no progress indicator

## What's Working (All Features)

| Feature | Gradio | NiceGUI | Notes |
|---------|--------|---------|-------|
| Document library | ✅ | ✅ | Persistent storage in `library/` directory |
| Upload .md/.txt | ✅ | ✅ | Files stored with metadata |
| Title auto-prefill | ❌ | ✅ | Extracts from `#` headers or uses filename |
| Duplicate detection | ❌ | ✅ | SHA-256 hash check with replace/cancel dialog |
| Scrollable library | ❌ | ✅ | Card-based with selection highlighting |
| 9 preset voices | ✅ | ✅ | Ryan, Aiden, Serena, Vivian, Uncle Fu, Dylan, Eric, Ono Anna, Sohee |
| 10 languages | ✅ | ✅ | English, Chinese, Japanese, Korean, French, German, Spanish, Portuguese, Russian, Italian |
| CJK chunking | ❌ | ✅ | Properly splits on `。！？，；：` for Chinese/Japanese/Korean |
| Audio generation | ✅ | ✅ | Qwen3-TTS 0.6B or 1.7B models |
| Speed control | 0.5x-2x | **0.5x-3x** | NiceGUI uses custom HTML5 audio player |
| Progress indicator | ❌ | ✅ | NiceGUI shows "Generating chunk X/Y..." |
| Screen recording | ❌ | ✅ | Press 'D' key, records current tab (debug feature) |
| Download audio | ✅ | ✅ | WAV export |
| Library CRUD | ✅ | ✅ | Add, select, delete documents |

## Known Issues (Gradio Only)

### 1. No Progress Indicator During Audio Generation
**Fixed in NiceGUI**: The NiceGUI version has a dedicated status label that updates during generation.
**Still affects**: Gradio version - progress is hidden to avoid showing in multiple places.

### 2. Speed Control Limited to 2x
**Fixed in NiceGUI**: Custom HTML5 audio player with slider supports 0.5x-3x.
**Still affects**: Gradio version - native player only supports 0.5x-2x.

## Architecture

```
readaloud/
├── app.py              # Gradio UI (legacy) - port 7860
├── app_nicegui.py      # NiceGUI UI (recommended) - port 8080
├── tts_engine.py       # Qwen3-TTS wrapper, voice cloning
├── library.py          # Document/audio CRUD operations
├── text_processor.py   # Markdown parsing, text chunking
├── audio_processor.py  # Audio duration utilities
├── alignment.py        # Simple timing estimation (WhisperX code exists)
├── sync.py             # Sync calculations (for future karaoke)
├── static/
│   ├── karaoke.js      # Client-side highlighting (NOT integrated)
│   └── karaoke.css     # Karaoke styles (NOT integrated)
├── data/
│   └── library.json    # Library index
├── library/            # Persistent storage (gitignored)
│   └── {doc_id}/
│       ├── document.md
│       ├── audio.wav
│       ├── timing.json
│       └── metadata.json
├── screenshot.png      # UI screenshot for README
└── requirements.txt
```

## Build Commands

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run NiceGUI version (RECOMMENDED)
python app_nicegui.py
# Access at http://127.0.0.1:8080

# Run Gradio version (legacy)
python app.py
# Access at http://127.0.0.1:7860

# Kill existing instances if needed
pkill -f "python app"; lsof -ti:7860 -ti:8080 | xargs kill -9
```

## Key Code Locations

| Task | NiceGUI File | Gradio File |
|------|--------------|-------------|
| Main UI layout | `app_nicegui.py:ReadAloudApp.build_ui()` | `app.py:113-278` |
| Library cards | `app_nicegui.py:_create_library_card()` | N/A (uses dropdown) |
| Audio generation | `app_nicegui.py:add_and_generate()` | `app.py:add_and_generate()` |
| Duplicate dialog | `app_nicegui.py:show_duplicate_dialog()` | N/A |
| Custom audio player | `app_nicegui.py:update_audio_player()` | N/A (Gradio native) |
| Speed control | `app_nicegui.py:set_speed()` | N/A (Gradio native) |
| Screen recording | `app_nicegui.py:build_ui()` (JS injection) | N/A |
| TTS model loading | `tts_engine.py:load_model()` | Same |
| Text chunking (CJK) | `text_processor.py:chunk_text()` | Same |
| Content hashing | `library.py:compute_content_hash()` | Same |
| Library operations | `library.py` | Same |

## Data Flow

1. **Upload**: User uploads file → title auto-extracted → prefilled in input
2. **Duplicate Check**: Content hash computed → check against library → show dialog if duplicate
3. **Create**: `library.create_item()` → stores in `library/{uuid}/` with content hash
4. **Generate**: `tts_engine.generate_long_text()` → chunks text (CJK-aware) → TTS each chunk → concatenate → save
5. **Select**: Card click → highlight card → load text + audio path
6. **Play**: NiceGUI uses custom HTML5 audio player; Gradio uses native player
7. **Speed**: NiceGUI buttons control `audio.playbackRate` via JavaScript
8. **Record**: Press 'D' → `getDisplayMedia()` → MediaRecorder → download MP4/WebM

## Voices Available

| Voice | Speaker ID | Language |
|-------|------------|----------|
| Ryan | `ryan` | English Male |
| Aiden | `aiden` | English Male |
| Serena | `serena` | Chinese Female |
| Vivian | `vivian` | Chinese Female |
| Uncle Fu | `uncle_fu` | Chinese Male |
| Dylan | `dylan` | Beijing Male |
| Eric | `eric` | Sichuan Male |
| Ono Anna | `ono_anna` | Japanese Female |
| Sohee | `sohee` | Korean Female |

## Roadmap

| Feature | Status | Notes |
|---------|--------|-------|
| Progress indicator | ✅ Done | NiceGUI version shows chunk progress |
| Extended speed control | ✅ Done | NiceGUI supports 0.5x-3x |
| CJK text chunking | ✅ Done | Properly splits Chinese/Japanese/Korean text on `。！？，；：` |
| Title prefill | ✅ Done | Auto-extracts title from markdown headers on file upload |
| Duplicate detection | ✅ Done | SHA-256 content hashing with replace/cancel dialog |
| Scrollable library | ✅ Done | Card-based library view with selection highlighting |
| Screen recording | ✅ Done | Press 'D' key to toggle (debug feature for X feedback) |
| Voice cloning | ❌ Not started | Code exists in `tts_engine.py` but not exposed in UI |
| Karaoke highlighting | ❌ Not started | Timing data saved, JS exists in `static/`, needs integration |
| WhisperX alignment | ❌ Not started | Code exists in `alignment.py`, using simple estimation |
| PDF support | ❌ Not started | |
| Streaming playback | ❌ Not started | |

## NiceGUI Development

This project uses NiceGUI. The Nice Vibes MCP server is configured for enhanced NiceGUI development support.

**Available Nice Vibes tools:**
- `nicegui_docs` - Search NiceGUI documentation
- `nicegui_samples` - Browse and run sample applications
- `nicegui_api` - Get API details for specific components

**Common NiceGUI patterns in this project:**
- `ui.upload()` for file uploads with auto title extraction
- `ui.scroll_area()` + `ui.card()` for scrollable library cards
- `ui.dialog()` for duplicate detection confirmation
- `ui.html()` for custom HTML5 audio player and recording indicator
- `ui.add_body_html()` for screen recording JavaScript
- `run_javascript()` for client-side interactions (speed control, recording)
- `ui.notify()` for user feedback

## Resume Checklist

When resuming work:
1. Run `source venv/bin/activate && python app_nicegui.py`
2. Check http://127.0.0.1:8080 loads correctly
3. Test: Upload a file → verify title prefills from `#` header
4. Test: Upload same file again → verify duplicate dialog appears
5. Test: Generate audio, verify progress indicator shows chunk count
6. Test: Click library cards → verify selection highlighting
7. Test: Speed control buttons (should support 0.5x-3x)
8. Test: Press 'D' key (not in input field) → select current tab → recording indicator → press 'D' again or click "Stop sharing" → file downloads

## Screen Recording Implementation Notes

**Debug feature for sharing feedback on X to Qwen team - no visible button, hotkey only.**

**IMPORTANT - Do not regress these settings:**

The screen recording uses `getDisplayMedia()` with critical options:
```javascript
navigator.mediaDevices.getDisplayMedia({
    video: true,
    audio: true,
    selfBrowserSurface: 'include',  // CRITICAL: allows recording current tab
    preferCurrentTab: true           // CRITICAL: shows current tab in picker
});
```

Without `selfBrowserSurface: 'include'`, Chrome hides the current tab from the picker.

**Hotkey:** Press 'D' key (ignored when typing in input/textarea fields)

**Format:** Tries MP4 first (X/Twitter compatible), falls back to WebM. Chrome on macOS may not support MP4 - convert with: `ffmpeg -i input.webm -c:v libx264 -c:a aac output.mp4`
