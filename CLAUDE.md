# CLAUDE.md

This file provides guidance to Claude Code when working with this repository. It serves as both development documentation and context for resuming work.

## Project Overview

ReadAloud v2 is a local-first text-to-speech web application with library management. Built in 7 hours using AI-augmented development.

**Current Status**: MVP working, with known issues documented below.

## What's Working (MVP Features)

| Feature | Status | Notes |
|---------|--------|-------|
| Document library | ✅ Working | Persistent storage in `library/` directory |
| Upload .md/.txt | ✅ Working | Files stored with metadata |
| 9 preset voices | ✅ Working | Ryan, Aiden, Serena, Vivian, Uncle Fu, Dylan, Eric, Ono Anna, Sohee |
| 10 languages | ✅ Working | English, Chinese, Japanese, Korean, French, German, Spanish, Portuguese, Russian, Italian |
| Audio generation | ✅ Working | Qwen3-TTS 0.6B or 1.7B models |
| Audio playback | ✅ Working | Gradio native player |
| Speed control | ✅ Working | 0.5x-2x (Gradio native) |
| Download audio | ✅ Working | WAV export via Gradio player |
| Library CRUD | ✅ Working | Add, select, delete documents |

## Known Bugs / Issues

### 1. No Progress Indicator During Audio Generation
**Severity**: Medium
**Description**: After clicking "Add & Generate Audio", there's no visual feedback showing generation progress. User has no way to know if it's working or how long to wait.
**Root Cause**: We set `show_progress="hidden"` to fix a bug where progress was showing in 3 places simultaneously (dropdown, text preview, and audio player).
**Attempted Fix**: Tried `show_progress="minimal"` but it showed progress on ALL outputs.
**Proper Fix Needed**: Add a dedicated status component that updates during generation, separate from the function outputs.

### 2. Speed Control Limited to 2x
**Severity**: Low
**Description**: Gradio's native audio player only supports 0.5x-2x. User wanted up to 3x.
**Root Cause**: Custom JavaScript to extend speed control caused the page to freeze/not load.
**Attempted Fix**: Multiple JS approaches tried - all caused UI blocking.
**Proper Fix Needed**: Either fix the JS approach or add a separate speed slider that controls `audio.playbackRate` directly.

## What Was Attempted But Didn't Work

### Custom JavaScript Speed Control
**Goal**: Extend speed options to include 2.5x and 3x
**Approaches Tried**:
1. MutationObserver + setInterval to intercept speed button clicks
2. `ratechange` event listener to override Gradio's speed changes
3. `requestAnimationFrame` loop to enforce speed while playing

**What Happened**: All approaches caused the page to freeze or not load at all. The JavaScript was blocking the main thread during page initialization.

**Why It Failed**: The MutationObserver was firing too frequently on Gradio's dynamic DOM updates, creating an infinite loop or blocking render.

**Code That Was Removed** (for reference if attempting again):
```javascript
// This blocked the page - DO NOT USE as-is
const observer = new MutationObserver(() => {
    // This fires too often on Gradio pages
    setupAllAudios();
    interceptSpeedButton();
});
observer.observe(document.body, { childList: true, subtree: true });
```

### Progress Indicator
**Goal**: Show generation progress without duplicating across multiple outputs
**Approaches Tried**:
1. `show_progress="minimal"` - showed progress on ALL 4 outputs
2. `show_progress="hidden"` - no progress at all (current state)

**What's Needed**: A dedicated `gr.Markdown` or `gr.Textbox` component for status that gets updated via generator/yield pattern during the `add_and_generate` function.

## Architecture

```
readaloud/
├── app.py              # Gradio UI (287 lines) - main entry point
├── tts_engine.py       # Qwen3-TTS wrapper, voice cloning (unused)
├── library.py          # Document/audio CRUD operations
├── text_processor.py   # Markdown parsing, text chunking
├── audio_processor.py  # Audio duration utilities
├── alignment.py        # Simple timing estimation (WhisperX code exists but unused)
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

# Run the application
python app.py
# Access at http://127.0.0.1:7860

# Kill existing instance if needed
pkill -f "python app.py"; lsof -ti:7860 | xargs kill -9
```

## Key Code Locations

| Task | File | Function/Line |
|------|------|---------------|
| Main UI layout | `app.py` | Line 113-278 |
| Audio generation | `app.py` | `add_and_generate()` line 186 |
| TTS model loading | `tts_engine.py` | `get_model()` line 32 |
| Library operations | `library.py` | All CRUD functions |
| Text chunking | `text_processor.py` | `chunk_text()` |

## Data Flow

1. **Upload**: User uploads file → `library.create_item()` → stores in `library/{uuid}/`
2. **Generate**: `tts_engine.generate_long_text()` → chunks text → TTS each chunk → concatenate → save
3. **Select**: Dropdown change → `select_library_item()` → load text + audio path
4. **Play**: Gradio audio player handles playback

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

## Roadmap (Not Implemented)

1. **Progress indicator** - Show generation status without triple-display bug
2. **Extended speed control** - 2.5x and 3x playback speeds
3. **Voice cloning** - Code exists in `tts_engine.py` but not exposed in UI
4. **Karaoke highlighting** - Code exists in `static/` but not integrated
5. **WhisperX alignment** - Code exists in `alignment.py` but using simple estimation instead
6. **PDF support**
7. **Streaming playback**

## Git History

```
b504814 - Add screenshot to README
50728b0 - Update README to reflect actual MVP features
123ea0f - Initial MVP: ReadAloud v2
```

## Resume Checklist

When resuming work:
1. Run `source venv/bin/activate && python app.py`
2. Check http://127.0.0.1:7860 loads correctly
3. Test: Upload a file, generate audio, play it
4. Refer to "Known Bugs" section for priority fixes
