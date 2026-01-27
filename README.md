# ReadAloud

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![NiceGUI](https://img.shields.io/badge/UI-NiceGUI-green.svg)](https://nicegui.io/)
[![Local First](https://img.shields.io/badge/Local-First-purple.svg)](#)
[![Version](https://img.shields.io/badge/version-5.1.0-brightgreen.svg)](https://github.com/powerpig99/readaloud/releases)

**Local-first text-to-speech reader powered by Qwen3-TTS.**

Upload markdown, text, or EPUB files, choose from 9 natural voices or clone any voice, and listen at your preferred speed. Everything runs locally—no cloud, no accounts.

![ReadAloud Screenshot](screenshot.png)

---

## Why This Exists

I built the initial MVP in 7 hours, then spent another 5-7 hours migrating to NiceGUI and adding advanced features. Total: ~12-14 hours to demonstrate a thesis: **AI-augmented development delivers orders of magnitude efficiency improvements over traditional hand-coding.**

But the motivation goes deeper.

### The Parallel Journey

In 2017, I discovered 樊登读书—a Chinese app where the founder summarizes books in 45-minute audio tracks. I was hooked. One book became ten, became a hundred, became finishing all 300+ books on the platform. My listening speed climbed: 1x → 2x → 3x. Chinese is more information-dense than English; I was processing faster than I ever could by reading.

When that platform couldn't satisfy my pace, I moved to 得到 and consumed another 3000+ books. Then Audible. Then podcasts. Audio became my primary channel for information.

Then I watched [Cliff Weitzman's interview](https://youtu.be/yfALZJcurZw)—the founder of Speechify—and felt recognition. His journey with dyslexia, his father reading Harry Potter onto cassette tapes, learning English through 22 listens of the audiobook, consuming 100 books a year for 16 years. Different starting points, same destination: audio as the unlock.

### The Technical Moment

In January 2025, Qwen released [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)—open-source, runs locally, supports 10 languages. The core technology that powers premium TTS services became freely available.

This project is what happens when personal resonance meets technical timing.

---

## Features

### Core
- **Document Library** — Persistent storage with card-based UI and selection highlighting
- **9 Natural Voices** — Ryan, Aiden, Serena, Vivian, Uncle Fu, Dylan, Eric, Ono Anna, Sohee
- **Voice Cloning** — Clone any voice from 3-30 second reference audio (V4)
- **10 Languages** — English, Chinese, Japanese, Korean, French, German, Spanish, Portuguese, Russian, Italian
- **Speed Control** — 0.5x to 3x playback speed
- **Model Choice** — 0.6B (fast) or 1.7B (higher quality)
- **Fully Local** — No cloud, no accounts, your data stays on your machine

### V5.1: Streamlined Interface (Latest)
- **EPUB Support** — Import EPUB books with automatic chapter extraction
- **Duration Estimation** — Shows estimated audio length before generation, actual duration after
- **Collapsible Sections** — Library and Generate Audio sections collapse for cleaner interface
- **Per-Item Delete** — Delete individual items with confirmation dialog
- **Popup Upload** — Simplified "Add to Library" button opens popup dialog

### V5.0: Unified Generation Interface
- **Auto-Chunking** — Long documents (5000+ words with headings) automatically split into chapters
- **Book Support** — Expandable cards show chapters with individual audio status
- **Chapter Generation** — Generate audio for specific chapters, not just whole documents
- **Separated Workflow** — Add documents first, generate audio later via fixed bottom section
- **Mutually Exclusive Voice** — Stock voices and clone voices in one clear interface

### Additional Features
- **Title Auto-Prefill** — Extracts title from markdown `#` headers on upload
- **Duplicate Detection** — SHA-256 content hashing with replace/cancel dialog
- **CJK Text Chunking** — Properly splits Chinese/Japanese/Korean on sentence boundaries (。！？，；：)
- **Progress Indicator** — Shows "Generating chunk X/Y..." during audio generation
- **Screen Recording** — Press 'D' key to record current tab for sharing feedback

---

## Quick Start

### Prerequisites

- Python 3.10+
- ~8GB RAM (for 0.6B model) or ~16GB (for 1.7B model)
- macOS, Linux, or Windows

### Installation

```bash
git clone https://github.com/powerpig99/readaloud.git
cd readaloud

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run

```bash
python app_nicegui.py
```
Open http://127.0.0.1:8080 in your browser.

**First run:** The TTS model (~1.5GB) downloads automatically from HuggingFace.

---

## Usage

### Adding Documents

1. Click **+ Add to Library** button in the Library header
2. Upload a `.md`, `.txt`, or `.epub` file (title auto-fills from content)
3. Click **Add to Library** in the popup dialog

Long documents with chapter headings and EPUB files are automatically split into books with chapters.

### Generating Audio

1. Select a document or chapter from the library
2. In the **Generate Audio** section at the bottom:
   - Choose a **Stock Voice** (preset) OR
   - Choose a **Clone Voice** (preset samples or upload your own)
3. Select language and model size
4. Click **Generate Audio**

### Voice Cloning

To clone a voice:
1. Select "Custom - Upload..." from the Clone Voice dropdown
2. Upload 3-30 seconds of clear speech audio
3. Enter the exact transcript of what's spoken
4. Generate audio — the cloned voice will be used

Preset clone samples included: Elon Musk, Jensen Huang, Donald Trump, Bill Gates

### Hidden Features

- **Screen Recording**: Press `D` key (not while typing) to record the current tab with audio. Press `D` again or click Chrome's "Stop sharing" to save.

---

## Technical Details

### Stack

| Component | Technology |
|-----------|------------|
| TTS Model | Qwen3-TTS (0.6B or 1.7B) |
| UI | NiceGUI + Tailwind CSS |
| Audio | soundfile, numpy |
| Text Processing | regex with CJK support |
| EPUB Parsing | ebooklib, BeautifulSoup |

### Architecture

```
readaloud/
├── app_nicegui.py      # NiceGUI UI - port 8080
├── tts_engine.py       # Qwen3-TTS model wrapper + voice cloning
├── library.py          # Document/book/audio persistence
├── text_processor.py   # Markdown parsing, auto-chunking, CJK support
├── audio_processor.py  # Audio duration utilities
├── alignment.py        # Timing estimation
├── data/
│   └── library.json    # Library index
├── library/            # Persistent storage (gitignored)
│   └── {item_id}/
│       ├── document.md
│       ├── audio.wav
│       ├── timing.json
│       ├── metadata.json
│       └── chapters_audio/     # For books
│           ├── 00-chapter.wav
│           └── 00-timing.json
└── voice_samples/      # Clone voice presets
```

### How It Works

1. **Upload** — Store document in library, extract title from headers
2. **Auto-Chunk** — Detect long docs (5000+ words, 2+ headings), split into chapters
3. **Duplicate Check** — Compute SHA-256 hash, prompt if content already exists
4. **Extract** — Strip markdown formatting, remove URLs, keep readable text
5. **Chunk** — Split at sentence boundaries (~800 chars per chunk), CJK-aware
6. **Generate** — Process each chunk through Qwen3-TTS with progress tracking
7. **Concatenate** — Join audio chunks into single file
8. **Play** — Stream through custom HTML5 audio player with extended speed control

---

## Version History

| Version | Features |
|---------|----------|
| **v5.1.0** | EPUB support, duration estimation, collapsible UI, per-item delete, popup upload |
| **v5.0.0** | Unified generation interface, book/chapter support, auto-chunking |
| **v4.0.0** | Voice cloning with preset samples and custom upload |
| **v3.0.0** | NiceGUI migration, CJK support, extended speed control |

---

## Limitations

- **No PDF/DOCX** — Only markdown, text, and EPUB files supported
- **No streaming** — Full audio generates before playback
- **WebM recording** — Chrome on macOS outputs WebM; convert to MP4 for X/Twitter with `ffmpeg -i input.webm -c:v libx264 -c:a aac output.mp4`

---

## Roadmap

- [x] Extended speed control (up to 3x)
- [x] Progress indicator during generation
- [x] CJK text chunking
- [x] Title auto-extraction
- [x] Duplicate document detection
- [x] Scrollable library cards
- [x] Screen recording for feedback
- [x] Voice cloning from reference audio
- [x] Book/chapter support with auto-chunking
- [x] Unified generation interface
- [x] EPUB file support
- [x] Audio duration estimation
- [x] Collapsible UI sections
- [ ] Synchronized text highlighting (karaoke mode)
- [ ] PDF support
- [ ] Real-time streaming playback
- [ ] Mobile-friendly UI

---

## Built With

This project was built using AI-augmented development with Claude:
- **V2 (Gradio MVP)**: 7 hours — core TTS, library management, basic UI
- **V3 (NiceGUI)**: +5-7 hours — modern UI, CJK support, duplicate detection
- **V4 (Voice Cloning)**: +2 hours — clone any voice from reference audio
- **V5 (Unified UI)**: +4 hours — book support, chapter generation, streamlined interface
- **V5.1 (Polish)**: +2 hours — EPUB support, duration estimation, UI refinements

Total development time: ~20-22 hours for a full-featured local TTS application with voice cloning and EPUB support.

**Tested on**: MacBook Pro M4 with 48GB RAM. Performance will vary on other hardware.

---

## License

MIT

---

## Acknowledgments

- [Qwen Team](https://github.com/QwenLM) for open-sourcing Qwen3-TTS
- [Cliff Weitzman](https://twitter.com/ACliffW) and Speechify for the inspiration
- The Chinese audio learning community (樊登读书, 得到) that showed me this path

---

## Author

**Jing Liang**
Helsinki, Finland
[GitHub](https://github.com/powerpig99)

*Building at the intersection of AI, learning, and human potential.*
