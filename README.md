# ReadAloud

**Local-first text-to-speech reader with voice cloning, powered by Qwen3-TTS.**

Convert your documents to natural-sounding speech. Upload a markdown file, optionally clone any voice from a short sample, and listen at your preferred speed (0.5x - 3x).

---

## Why This Exists

I built this in 3 days to demonstrate a thesis: **AI-augmented development delivers orders of magnitude efficiency improvements over traditional hand-coding.**

But the motivation goes deeper.

### The Parallel Journey

In 2017, I discovered 樊登读书—a Chinese app where the founder summarizes books in 45-minute audio tracks. I was hooked. One book became ten, became a hundred, became finishing all 300+ books on the platform. My listening speed climbed: 1x → 2x → 3x. Chinese is more information-dense than English; I was processing faster than I ever could by reading.

When that platform couldn't satisfy my pace, I moved to 得到 and consumed another 3000+ books. Then Audible. Then podcasts. Audio became my primary channel for information.

Then I watched [Cliff Weitzman's interview](https://youtu.be/yfALZJcurZw)—the founder of Speechify—and felt recognition. His journey with dyslexia, his father reading Harry Potter onto cassette tapes, learning English through 22 listens of the audiobook, consuming 100 books a year for 16 years. Different starting points, same destination: audio as the unlock.

### The Technical Moment

In January 2026, Qwen released [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)—open-source, voice cloning, 10 languages, runs locally. The core technology that powers premium TTS services became freely available overnight.

This project is what happens when personal resonance meets technical timing.

---

## Features

- **Markdown Support** — Upload .md files, automatically extract readable text
- **Voice Cloning** — Clone any voice from a 5-30 second sample
- **10 Languages** — English, Chinese, Japanese, Korean, French, German, Spanish, Portuguese, Russian, Italian
- **Speed Control** — 0.5x to 3x playback speed
- **Fully Local** — No cloud, no accounts, your data stays on your machine
- **Download** — Export generated audio as WAV

---

## Quick Start

### Prerequisites

- Python 3.10+
- ~8GB RAM (for 0.6B model) or ~16GB (for 1.7B model)

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

**First run:** The TTS model (~1.5GB) downloads automatically from HuggingFace. This takes a few minutes depending on your connection.

---

## Usage

### Basic (Default Voice)

1. Click "Upload .md File" and select your document
2. Review the text preview
3. Select language
4. Click "Generate Audio"
5. Listen and adjust speed as needed

### Voice Cloning

1. Upload your document
2. Select "Clone from Reference"
3. Upload a clear audio sample (5-30 seconds)
4. Type the **exact** transcript of what's spoken in the sample
5. Generate audio—it will speak in the cloned voice

**Tips for good voice cloning:**
- Use clear audio with minimal background noise
- 10-20 seconds works best
- Transcript must match exactly
- Same language as your document works best

---

## Technical Details

### Stack

| Component | Technology |
|-----------|------------|
| TTS Model | Qwen3-TTS-12Hz-0.6B-Base |
| UI | Gradio 4.x |
| Audio Processing | pydub, librosa, soundfile |
| Text Processing | regex, markdown |

### How It Works

1. **Text Extraction** — Strip markdown formatting, keep readable content
2. **Chunking** — Split at sentence boundaries (max ~800 chars per chunk)
3. **Voice Prompt** — If cloning, create voice embedding from reference
4. **Generation** — Process each chunk through Qwen3-TTS
5. **Concatenation** — Join audio chunks seamlessly
6. **Post-processing** — Apply speed adjustment via sample rate manipulation

### Model Options

| Model | Size | RAM | Quality | Speed |
|-------|------|-----|---------|-------|
| 0.6B | ~1.5GB | ~8GB | Good | Fast |
| 1.7B | ~4GB | ~16GB | Better | Slower |

---

## Limitations

- **Markdown only** — PDF/DOCX support planned
- **No streaming** — Full audio generates before playback
- **Speed via resampling** — Extreme speeds (0.5x, 3x) may sound unnatural
- **No text highlighting sync** — Audio-only, no visual tracking

---

## Roadmap

- [ ] PDF support
- [ ] Real-time streaming playback
- [ ] Synchronized text highlighting
- [ ] Audio caching (don't regenerate same content)
- [ ] Multiple saved voices
- [ ] Mobile-friendly UI

---

## Built With

This project was built using AI-augmented development with Claude. The entire codebase was produced in a single session through iterative prompting and refinement.

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
[GitHub](https://github.com/powerpig99) | [Email](mailto:jingliang@gmail.com)

*Building at the intersection of AI, learning, and human potential.*
