/**
 * Room Companion — Voice Input (STT) & Output (TTS)
 *
 * - TTS via server-side edge-tts (POST /api/tts → MP3 → <audio>)
 * - STT via Web Speech Recognition API
 * - Mode-aware speech rate (server adjusts for memory support)
 * - Mute toggle, pulsing mic indicator
 */

(function () {
  'use strict';

  const config = window.ROOM_CONFIG;
  if (!config) return;

  // ---- TTS (server-side) ----

  let muted = false;
  let currentAudio = null;
  let audioQueue = [];
  let isPlaying = false;
  let userHasInteracted = false;

  // Chrome blocks autoplay until user interacts with the page.
  // Track first interaction, then play any queued greeting audio.
  function onFirstInteraction() {
    if (userHasInteracted) return;
    userHasInteracted = true;
    document.removeEventListener('click', onFirstInteraction);
    document.removeEventListener('keydown', onFirstInteraction);
    // If greeting was queued before interaction, play it now
    if (audioQueue.length > 0 && !isPlaying) {
      playNext();
    }
  }
  document.addEventListener('click', onFirstInteraction);
  document.addEventListener('keydown', onFirstInteraction);

  async function speak(text) {
    if (!text || muted) return;

    // Queue it
    audioQueue.push(text);
    // Only auto-play if user has interacted (Chrome autoplay policy)
    if (!isPlaying && userHasInteracted) {
      playNext();
    }
  }

  async function playNext() {
    if (audioQueue.length === 0) {
      isPlaying = false;
      return;
    }

    isPlaying = true;
    const text = audioQueue.shift();

    try {
      const resp = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text, mode: config.mode }),
      });

      if (!resp.ok) throw new Error(`TTS HTTP ${resp.status}`);

      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      currentAudio = new Audio(url);

      currentAudio.onended = () => {
        URL.revokeObjectURL(url);
        currentAudio = null;
        playNext();
      };

      currentAudio.onerror = (e) => {
        console.error('[Voice] Audio playback error:', e);
        URL.revokeObjectURL(url);
        currentAudio = null;
        playNext();
      };

      if (!muted) {
        try {
          await currentAudio.play();
        } catch (playErr) {
          console.warn('[Voice] Autoplay blocked, will retry after interaction:', playErr.message);
          // Re-queue the text for later
          audioQueue.unshift(text);
          isPlaying = false;
        }
      } else {
        playNext();
      }
    } catch (err) {
      console.error('[Voice] TTS fetch error:', err);
      isPlaying = false;
      playNext();
    }
  }

  // Mute toggle
  const muteBtn = document.getElementById('mute-btn');
  if (muteBtn) {
    muteBtn.addEventListener('click', () => {
      muted = !muted;
      muteBtn.classList.toggle('muted', muted);
      muteBtn.setAttribute('aria-label', muted ? 'Unmute voice' : 'Mute voice');
      muteBtn.querySelector('.mute-icon').textContent = muted ? '\u{1F507}' : '\u{1F50A}';
      // Stop current playback if muting
      if (muted && currentAudio) {
        currentAudio.pause();
        currentAudio = null;
        audioQueue = [];
        isPlaying = false;
      }
    });
  }

  // ---- STT (browser-side, unchanged) ----

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const micBtn = document.getElementById('mic-btn');
  const chatInput = document.getElementById('chat-input');
  const micIndicator = document.getElementById('mic-indicator');

  let recognition = null;
  let listening = false;

  if (SpeechRecognition && micBtn && chatInput) {
    recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = true;
    recognition.continuous = false;

    recognition.onresult = (event) => {
      let transcript = '';
      for (let i = 0; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      chatInput.value = transcript.trim();
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      setListening(false);
    };

    recognition.onend = () => {
      if (listening) {
        setListening(false);
        // Auto-send if we got text
        const text = chatInput.value.trim();
        if (text && window.RoomChat) {
          window.RoomChat.sendMessage(text);
        }
      }
    };

    micBtn.addEventListener('click', () => {
      if (listening) {
        recognition.stop();
        setListening(false);
      } else {
        try {
          recognition.start();
          setListening(true);
        } catch (err) {
          console.error('Could not start recognition:', err);
          setListening(false);
        }
      }
    });
  } else if (micBtn) {
    micBtn.disabled = true;
    micBtn.title = 'Voice input not supported in this browser';
  }

  function setListening(on) {
    listening = on;
    if (micBtn) {
      micBtn.classList.toggle('listening', on);
      micBtn.setAttribute('aria-label', on ? 'Stop listening' : 'Start voice input');
    }
    if (micIndicator) {
      micIndicator.classList.toggle('active', on);
    }
  }

  // ---- Expose for app.js ----

  window.Voice = { speak };
})();
