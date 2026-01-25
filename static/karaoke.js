/**
 * KaraokeSync - Real-time text highlighting synchronized with audio playback
 */
class KaraokeSync {
    constructor(containerId, audioId) {
        this.container = document.getElementById(containerId);
        this.audioElement = null;
        this.audioId = audioId;
        this.timingData = null;
        this.speed = 1.0;
        this.isPlaying = false;
        this.animationFrameId = null;
        this.highlightColor = '#FFD700';
        this.fontSize = 20;
        this.cardStyle = 'bubble';

        // Bind methods
        this.updateDisplay = this.updateDisplay.bind(this);
        this.onAudioTimeUpdate = this.onAudioTimeUpdate.bind(this);
        this.onAudioPlay = this.onAudioPlay.bind(this);
        this.onAudioPause = this.onAudioPause.bind(this);
    }

    /**
     * Initialize with timing data
     */
    init(timingDataJson, speed = 1.0) {
        if (typeof timingDataJson === 'string') {
            this.timingData = JSON.parse(timingDataJson);
        } else {
            this.timingData = timingDataJson;
        }
        this.speed = speed;

        // Find audio element (Gradio wraps it)
        this.findAudioElement();

        if (this.timingData && this.timingData.sentences) {
            this.renderInitialState();
        }
    }

    /**
     * Find the audio element in Gradio's component
     */
    findAudioElement() {
        // Try to find audio by traversing Gradio's structure
        const audioComponents = document.querySelectorAll('audio');
        for (const audio of audioComponents) {
            // Look for the audio element in our target component
            if (audio.closest(`#${this.audioId}`) ||
                audio.closest('[data-testid="audio"]')) {
                this.audioElement = audio;
                this.attachAudioListeners();
                return;
            }
        }

        // Fallback: use first audio element
        if (audioComponents.length > 0) {
            this.audioElement = audioComponents[0];
            this.attachAudioListeners();
        }
    }

    /**
     * Attach listeners to audio element
     */
    attachAudioListeners() {
        if (!this.audioElement) return;

        this.audioElement.addEventListener('play', this.onAudioPlay);
        this.audioElement.addEventListener('pause', this.onAudioPause);
        this.audioElement.addEventListener('ended', this.onAudioPause);
        this.audioElement.addEventListener('timeupdate', this.onAudioTimeUpdate);
        this.audioElement.addEventListener('seeked', this.onAudioTimeUpdate);
    }

    /**
     * Remove audio listeners
     */
    detachAudioListeners() {
        if (!this.audioElement) return;

        this.audioElement.removeEventListener('play', this.onAudioPlay);
        this.audioElement.removeEventListener('pause', this.onAudioPause);
        this.audioElement.removeEventListener('ended', this.onAudioPause);
        this.audioElement.removeEventListener('timeupdate', this.onAudioTimeUpdate);
        this.audioElement.removeEventListener('seeked', this.onAudioTimeUpdate);
    }

    /**
     * Audio play handler
     */
    onAudioPlay() {
        this.isPlaying = true;
        this.startSync();
    }

    /**
     * Audio pause handler
     */
    onAudioPause() {
        this.isPlaying = false;
        this.stopSync();
    }

    /**
     * Audio time update handler
     */
    onAudioTimeUpdate() {
        if (!this.isPlaying) {
            // Update display even when paused (for seeking)
            this.updateDisplay();
        }
    }

    /**
     * Start the synchronization loop
     */
    startSync() {
        if (this.animationFrameId) return;

        const loop = () => {
            this.updateDisplay();
            if (this.isPlaying) {
                this.animationFrameId = requestAnimationFrame(loop);
            }
        };
        this.animationFrameId = requestAnimationFrame(loop);
    }

    /**
     * Stop the synchronization loop
     */
    stopSync() {
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
    }

    /**
     * Set playback speed
     */
    setSpeed(speed) {
        this.speed = speed;
        if (this.audioElement) {
            this.audioElement.playbackRate = speed;
        }
    }

    /**
     * Set highlight color
     */
    setHighlightColor(color) {
        this.highlightColor = color;
        document.documentElement.style.setProperty('--highlight-color', color);
        this.updateDisplay();
    }

    /**
     * Set font size
     */
    setFontSize(size) {
        this.fontSize = size;
        document.documentElement.style.setProperty('--karaoke-font-size', size + 'px');
    }

    /**
     * Set card style
     */
    setCardStyle(style) {
        this.cardStyle = style;
        if (this.container) {
            this.container.setAttribute('data-card-style', style);
        }
        this.updateDisplay();
    }

    /**
     * Render initial state before playback
     */
    renderInitialState() {
        if (!this.container || !this.timingData) return;

        const sentences = this.timingData.sentences;
        if (!sentences || sentences.length === 0) return;

        this.renderState({
            currentSentenceIndex: 0,
            currentWordIndex: null,
            previousSentence: null,
            currentSentence: sentences[0],
            nextSentence: sentences.length > 1 ? sentences[1] : null,
            sentenceProgress: 0,
            totalProgress: 0
        });
    }

    /**
     * Update the display based on current playback time
     */
    updateDisplay() {
        if (!this.container || !this.timingData || !this.audioElement) return;

        const currentTime = this.audioElement.currentTime;
        const state = this.calculateDisplayState(currentTime);
        this.renderState(state);
    }

    /**
     * Calculate display state for a given time
     */
    calculateDisplayState(currentTime) {
        const sentences = this.timingData.sentences;
        const audioDuration = this.timingData.audio_duration;

        if (!sentences || sentences.length === 0) {
            return null;
        }

        // Find current sentence
        let currentSentenceIndex = null;
        for (let i = 0; i < sentences.length; i++) {
            if (currentTime >= sentences[i].start && currentTime < sentences[i].end) {
                currentSentenceIndex = i;
                break;
            }
        }

        // Handle edge cases
        if (currentSentenceIndex === null) {
            if (currentTime < sentences[0].start) {
                currentSentenceIndex = 0;
            } else if (currentTime >= sentences[sentences.length - 1].end) {
                currentSentenceIndex = sentences.length - 1;
            } else {
                // Between sentences
                for (let i = 0; i < sentences.length - 1; i++) {
                    if (currentTime >= sentences[i].end && currentTime < sentences[i + 1].start) {
                        currentSentenceIndex = i + 1;
                        break;
                    }
                }
            }
        }

        const currentSentence = sentences[currentSentenceIndex];
        const previousSentence = currentSentenceIndex > 0 ? sentences[currentSentenceIndex - 1] : null;
        const nextSentence = currentSentenceIndex < sentences.length - 1 ? sentences[currentSentenceIndex + 1] : null;

        // Calculate sentence progress
        const sentDuration = currentSentence.end - currentSentence.start;
        let sentenceProgress = sentDuration > 0 ? (currentTime - currentSentence.start) / sentDuration : 0;
        sentenceProgress = Math.max(0, Math.min(1, sentenceProgress));

        // Find current word
        let currentWordIndex = null;
        const words = currentSentence.words || [];
        for (let i = 0; i < words.length; i++) {
            if (currentTime >= words[i].start && currentTime < words[i].end) {
                currentWordIndex = i;
                break;
            }
        }

        // Total progress
        const totalProgress = audioDuration > 0 ? currentTime / audioDuration : 0;

        return {
            currentSentenceIndex,
            currentWordIndex,
            previousSentence,
            currentSentence,
            nextSentence,
            sentenceProgress,
            totalProgress,
            currentTime
        };
    }

    /**
     * Render the display state
     */
    renderState(state) {
        if (!this.container || !state) return;

        const html = `
            <div class="karaoke-wrapper" data-card-style="${this.cardStyle}">
                ${state.previousSentence ? this.renderSentenceCard(state.previousSentence, 'previous', state.currentTime) : ''}
                ${this.renderSentenceCard(state.currentSentence, 'current', state.currentTime, state.sentenceProgress)}
                ${state.nextSentence ? this.renderSentenceCard(state.nextSentence, 'next', state.currentTime) : ''}
                ${this.renderProgressBar(state.totalProgress)}
            </div>
        `;

        this.container.innerHTML = html;
    }

    /**
     * Render a sentence card
     */
    renderSentenceCard(sentence, position, currentTime, progress = 0) {
        const words = sentence.words || [];
        const wordsHtml = words.map((word, idx) => {
            const wordState = this.getWordState(word, currentTime);
            return this.renderWord(word, wordState);
        }).join(' ');

        const progressBar = position === 'current' ?
            `<div class="sentence-progress-bar">
                <div class="sentence-progress-fill" style="width: ${progress * 100}%"></div>
            </div>` : '';

        return `
            <div class="sentence-card ${position}">
                <div class="sentence-text">${wordsHtml}</div>
                ${progressBar}
            </div>
        `;
    }

    /**
     * Get word state (past/current/future)
     */
    getWordState(word, currentTime) {
        if (currentTime < word.start) {
            return { state: 'future', progress: 0 };
        } else if (currentTime >= word.end) {
            return { state: 'past', progress: 1 };
        } else {
            const duration = word.end - word.start;
            const progress = duration > 0 ? (currentTime - word.start) / duration : 0;
            return { state: 'current', progress };
        }
    }

    /**
     * Render a single word
     */
    renderWord(word, wordState) {
        let style = '';
        if (wordState.state === 'current') {
            const progressPct = Math.round(wordState.progress * 100);
            style = `background: linear-gradient(90deg, ${this.highlightColor} ${progressPct}%, transparent ${progressPct}%);`;
        }

        return `<span class="word ${wordState.state}" style="${style}" data-start="${word.start}" data-end="${word.end}">${word.word}</span>`;
    }

    /**
     * Render the total progress bar
     */
    renderProgressBar(progress) {
        return `
            <div class="total-progress-bar">
                <div class="total-progress-fill" style="width: ${progress * 100}%"></div>
            </div>
        `;
    }

    /**
     * Seek to a specific sentence
     */
    seekToSentence(sentenceIndex) {
        if (!this.audioElement || !this.timingData) return;

        const sentences = this.timingData.sentences;
        if (sentenceIndex >= 0 && sentenceIndex < sentences.length) {
            this.audioElement.currentTime = sentences[sentenceIndex].start;
        }
    }

    /**
     * Cleanup
     */
    destroy() {
        this.stopSync();
        this.detachAudioListeners();
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

// Global instance
let karaokeSync = null;

/**
 * Initialize karaoke sync from Gradio
 */
function initKaraoke(containerId, audioId, timingDataJson, speed) {
    if (karaokeSync) {
        karaokeSync.destroy();
    }
    karaokeSync = new KaraokeSync(containerId, audioId);
    karaokeSync.init(timingDataJson, speed);
    return karaokeSync;
}

/**
 * Update speed
 */
function setKaraokeSpeed(speed) {
    if (karaokeSync) {
        karaokeSync.setSpeed(speed);
    }
}

/**
 * Update highlight color
 */
function setKaraokeHighlightColor(color) {
    if (karaokeSync) {
        karaokeSync.setHighlightColor(color);
    }
}

/**
 * Update font size
 */
function setKaraokeFontSize(size) {
    if (karaokeSync) {
        karaokeSync.setFontSize(size);
    }
}

/**
 * Update card style
 */
function setKaraokeCardStyle(style) {
    if (karaokeSync) {
        karaokeSync.setCardStyle(style);
    }
}

/**
 * Re-find audio element (useful after Gradio re-renders)
 */
function refreshKaraokeAudio() {
    if (karaokeSync) {
        karaokeSync.findAudioElement();
    }
}

/**
 * Seek to sentence by index
 */
function seekToSentence(index) {
    if (karaokeSync) {
        karaokeSync.seekToSentence(index);
    }
}
