/**
 * Audio utilities for microphone capture and playback.
 * Handles WebRTC media streams, PCM encoding, and Web Audio API.
 */

export class AudioRecorder {
  private mediaStream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private isRecording = false;
  private onAudioData: ((audioData: Float32Array) => void) | null = null;

  /**
   * Start recording from microphone.
   * @param onAudioData Callback for audio chunks (Float32Array PCM)
   */
  async start(onAudioData: (audioData: Float32Array) => void): Promise<void> {
    if (this.isRecording) {
      console.warn('Already recording');
      return;
    }

    this.onAudioData = onAudioData;

    // Request microphone access
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      // Create audio context
      this.audioContext = new AudioContext({ sampleRate: 16000 });
      this.source = this.audioContext.createMediaStreamSource(this.mediaStream);

      // Create script processor for audio data
      // Buffer size: 4096 samples = ~256ms @ 16kHz
      this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);

      this.processor.onaudioprocess = (e) => {
        if (!this.isRecording) return;

        const inputData = e.inputBuffer.getChannelData(0);
        if (this.onAudioData) {
          this.onAudioData(inputData);
        }
      };

      // Connect nodes
      // Note: processor must be connected to destination for onaudioprocess to fire
      // But we use a gain node set to 0 to prevent audio feedback
      this.source.connect(this.processor);
      const gainNode = this.audioContext.createGain();
      gainNode.gain.value = 0; // Mute the output to prevent feedback
      this.processor.connect(gainNode);
      gainNode.connect(this.audioContext.destination);

      this.isRecording = true;
      console.log('Audio recording started');
    } catch (error) {
      console.error('Failed to start recording:', error);
      throw error;
    }
  }

  /**
   * Stop recording and release resources.
   */
  stop(): void {
    if (!this.isRecording) return;

    this.isRecording = false;

    // Disconnect and cleanup
    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }

    if (this.source) {
      this.source.disconnect();
      this.source = null;
    }

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    console.log('Audio recording stopped');
  }

  getIsRecording(): boolean {
    return this.isRecording;
  }
}

/**
 * Convert Float32Array PCM to base64-encoded Int16Array (16-bit PCM).
 * Backend expects 16-bit PCM, but microphone gives Float32 (-1.0 to 1.0).
 */
export function float32ToInt16Base64(float32Array: Float32Array): string {
  const int16Array = new Int16Array(float32Array.length);

  for (let i = 0; i < float32Array.length; i++) {
    // Clamp to [-1.0, 1.0] and convert to 16-bit int
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }

  // Convert to base64
  const bytes = new Uint8Array(int16Array.buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Audio player with queue for streaming playback.
 * Handles base64-encoded audio chunks from backend.
 */
export class AudioPlayer {
  private audioElement: HTMLAudioElement | null = null;
  private mediaSource: MediaSource | null = null;
  private sourceBuffer: SourceBuffer | null = null;
  private queue: Uint8Array[] = [];
  private isPlaying = false;
  private onComplete: (() => void) | null = null;
  private isFinalized = false;

  constructor() {
    this.audioElement = new Audio();
    this.audioElement.preload = 'auto';
    this.audioElement.addEventListener('ended', () => {
      this.isPlaying = false;
      if (this.onComplete) {
        this.onComplete();
      }
    });

    this.resetStream();
  }

  resetStream(): void {
    this.isPlaying = false;
    this.isFinalized = false;
    this.queue = [];

    if (this.audioElement) {
      this.audioElement.pause();
      this.audioElement.currentTime = 0;
    }

    if (this.sourceBuffer && this.sourceBuffer.updating) {
      try {
        this.sourceBuffer.abort();
      } catch (e) {
        // ignore
      }
    }

    this.sourceBuffer = null;
    this.mediaSource = new MediaSource();
    if (this.audioElement) {
      this.audioElement.src = URL.createObjectURL(this.mediaSource);
    }

    this.mediaSource.addEventListener('sourceopen', () => {
      if (!this.mediaSource) return;
      try {
        this.sourceBuffer = this.mediaSource.addSourceBuffer('audio/mpeg');
        this.sourceBuffer.mode = 'sequence';
        this.sourceBuffer.addEventListener('updateend', () => {
          this.flushQueue();
          if (this.isFinalized && this.queue.length === 0 && this.sourceBuffer && !this.sourceBuffer.updating) {
            try {
              this.mediaSource?.endOfStream();
            } catch (e) {
              // ignore
            }
          }
        });
      } catch (e) {
        console.error('Failed to create SourceBuffer:', e);
      }
    });
  }

  /**
   * Add audio chunk to queue and start playback if not already playing.
   * @param base64Audio Base64-encoded audio data (MP3 from ElevenLabs)
   */
  async addChunk(base64Audio: string): Promise<void> {
    if (!base64Audio || !this.mediaSource) return;

    const binaryString = atob(base64Audio);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }

    this.queue.push(bytes);
    this.flushQueue();

    if (!this.isPlaying && this.audioElement) {
      try {
        await this.audioElement.play();
        this.isPlaying = true;
      } catch (e) {
        console.warn('Audio playback failed to start:', e);
      }
    }
  }

  finalize(): void {
    this.isFinalized = true;
    this.flushQueue();
  }

  private flushQueue(): void {
    if (!this.sourceBuffer || !this.mediaSource) return;
    if (this.sourceBuffer.updating) return;
    if (this.queue.length === 0) return;

    const next = this.queue.shift()!;
    try {
      const buffer = next.buffer.slice(next.byteOffset, next.byteOffset + next.byteLength) as ArrayBuffer;
      this.sourceBuffer.appendBuffer(buffer);
    } catch (e) {
      console.error('Failed to append audio buffer:', e);
    }
  }

  /**
   * Stop playback immediately and clear queue.
   * Does NOT trigger onComplete callback.
   */
  stop(): void {
    this.resetStream();
  }

  /**
   * Set callback for when playback completes.
   */
  setOnComplete(callback: () => void): void {
    this.onComplete = callback;
  }

  getIsPlaying(): boolean {
    return this.isPlaying;
  }

  getQueueLength(): number {
    return this.queue.length;
  }
}
