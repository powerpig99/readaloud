# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ReadAloud v2 is a local-first text-to-speech web application with library management and karaoke-style text synchronization. It uses Qwen3-TTS for speech synthesis and WhisperX for word-level alignment.

**Key Features**:
- Persistent document library with audio storage
- Word-level karaoke highlighting synchronized with playback
- Real-time speed control via HTML5 audio playbackRate
- Voice cloning from reference audio
- Customizable display (highlight color, font size, card style)

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

# Verify key imports work
python -c "import gradio; print('Gradio OK')"
python -c "import torch; print(f'Torch OK, CUDA: {torch.cuda.is_available()}')"
python -c "from qwen_tts import Qwen3TTSModel; print('Qwen-TTS OK')"
python -c "import whisperx; print('WhisperX OK')"
```

## Architecture

```
readaloud/
├── app.py              # Gradio UI, library sidebar, karaoke display
├── tts_engine.py       # Qwen3-TTS model wrapper, voice cloning
├── text_processor.py   # Markdown parsing, sentence extraction
├── audio_processor.py  # Audio duration, format conversion
├── library.py          # Document/audio library CRUD operations
├── alignment.py        # WhisperX forced alignment, timing extraction
├── sync.py             # Real-time sync calculations
├── static/
│   ├── karaoke.js      # Real-time JS highlighting (KaraokeSync class)
│   └── karaoke.css     # Karaoke styles, card variations
├── data/
│   └── library.json    # Library index
├── library/            # Persistent storage
│   └── {doc_id}/
│       ├── document.md
│       ├── audio.wav
│       ├── timing.json   # Word-level timing
│       └── metadata.json
└── requirements.txt
```

## Key Data Structures

### timing.json (Word-level timing from alignment)
```json
{
  "version": "1.0",
  "audio_duration": 45.2,
  "sentences": [
    {
      "sentence_index": 0,
      "text": "ReadAloud converts text into speech.",
      "start": 0.0,
      "end": 3.2,
      "words": [
        {"word": "ReadAloud", "start": 0.0, "end": 0.6, "confidence": 0.95}
      ]
    }
  ]
}
```

### metadata.json (Library item)
```json
{
  "id": "uuid",
  "title": "Document Title",
  "filename": "original.md",
  "created_at": "2025-01-24T...",
  "audio_generated": true,
  "audio_duration_seconds": 45.2,
  "word_count": 150,
  "language": "english",
  "voice_settings": {"mode": "default", "model_size": "0.6B"}
}
```

## Data Flow

1. **Upload**: User uploads markdown → `library.create_item()` → stores in library/{id}/
2. **Generate Audio**: `tts_engine.generate_long_text()` → chunks → TTS → concatenate → save audio
3. **Alignment**: `alignment.align_or_estimate()` → WhisperX transcribe → align → timing.json
4. **Playback**: `karaoke.js` KaraokeSync class → requestAnimationFrame loop → highlight words

## Module Responsibilities

| Module | Purpose |
|--------|---------|
| `library.py` | CRUD for documents/audio, path helpers |
| `alignment.py` | WhisperX model loading, forced alignment, timing extraction |
| `sync.py` | Calculate display state from playback time |
| `karaoke.js` | Client-side real-time highlighting |
| `karaoke.css` | Card styles (Bubble/Card/Minimal), word states |

## Technical Stack

| Component | Technology |
|-----------|------------|
| UI | Gradio ≥4.0 |
| TTS | Qwen3-TTS-12Hz-0.6B/1.7B |
| Alignment | WhisperX + faster-whisper |
| Audio | pydub, librosa, soundfile |
| Speed Control | HTML5 audio.playbackRate |

## Speed Control Approach

Speed is controlled via HTML5 `audio.playbackRate` instead of regenerating audio:
- Instant speed changes, no processing needed
- Timing calculations remain in original time (playbackRate handles actual speed)
- Speed buttons: 0.5x, 0.75x, 1x, 1.25x, 1.5x, 2x, 3x

## Customization Options

- **Highlight Color**: CSS variable `--highlight-color`
- **Font Size**: CSS variable `--karaoke-font-size`
- **Card Style**: Bubble (rounded), Card (square), Minimal (border only)
