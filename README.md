# ReadAloud

**Local-first text-to-speech reader powered by Qwen3-TTS.**

Upload markdown or text files, choose from 9 natural voices, and listen at your preferred speed. Everything runs locally—no cloud, no accounts.

![ReadAloud Screenshot](screenshot.png)

---

## Why This Exists

I built this in 7 hours to demonstrate a thesis: **AI-augmented development delivers orders of magnitude efficiency improvements over traditional hand-coding.**

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

- **Document Library** — Persistent storage for your documents and generated audio
- **9 Natural Voices** — Ryan, Aiden, Serena, Vivian, Uncle Fu, Dylan, Eric, Ono Anna, Sohee
- **10 Languages** — English, Chinese, Japanese, Korean, French, German, Spanish, Portuguese, Russian, Italian
- **Speed Control** — 0.5x to 2x playback speed
- **Model Choice** — 0.6B (fast) or 1.7B (higher quality)
- **Fully Local** — No cloud, no accounts, your data stays on your machine
- **Download** — Export generated audio as WAV

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
python app.py
```

Open http://127.0.0.1:7860 in your browser.

**First run:** The TTS model (~1.5GB) downloads automatically from HuggingFace.

---

## Usage

1. Click **Add New Document** accordion
2. Upload a `.md` or `.txt` file
3. Select voice, language, and model size
4. Click **Add & Generate Audio**
5. Wait for generation (shown in toast notifications)
6. Use the audio player to listen—adjust speed with the built-in speed button

Your documents and audio persist in the library. Select from the dropdown to switch between them.

---

## Technical Details

### Stack

| Component | Technology |
|-----------|------------|
| TTS Model | Qwen3-TTS (0.6B or 1.7B) |
| UI | Gradio 4.x |
| Audio | soundfile, numpy |
| Text Processing | regex |

### Architecture

```
readaloud/
├── app.py              # Gradio UI, library management
├── tts_engine.py       # Qwen3-TTS model wrapper
├── library.py          # Document/audio persistence
├── text_processor.py   # Markdown parsing, text chunking
├── audio_processor.py  # Audio duration utilities
├── alignment.py        # Timing estimation
└── sync.py             # Sync calculations
```

### How It Works

1. **Upload** — Store document in library
2. **Extract** — Strip markdown formatting, keep readable text
3. **Chunk** — Split at sentence boundaries (~800 chars per chunk)
4. **Generate** — Process each chunk through Qwen3-TTS
5. **Concatenate** — Join audio chunks into single file
6. **Play** — Stream through Gradio audio player

---

## Limitations

- **Markdown/Text only** — No PDF or DOCX support yet
- **No streaming** — Full audio generates before playback
- **Speed limited to 2x** — Gradio's native player limitation

---

## Roadmap

- [ ] Voice cloning from reference audio
- [ ] Extended speed control (up to 3x)
- [ ] Synchronized text highlighting (karaoke mode)
- [ ] PDF support
- [ ] Real-time streaming playback
- [ ] Mobile-friendly UI

---

## Built With

This project was built in a single 7-hour session using AI-augmented development with Claude. The entire codebase—from architecture to working MVP—was produced through iterative prompting and refinement.

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
