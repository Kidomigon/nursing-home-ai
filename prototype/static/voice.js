/**
 * Room Companion — Voice Input (STT) & Output (TTS)
 *
 * - Text-to-Speech via Web Speech Synthesis API
 * - Speech-to-Text via Web Speech Recognition API
 * - Mode-aware speech rate (slower for memory support)
 * - Mute toggle, pulsing mic indicator
 */

(function () {
  'use strict';

  const config = window.ROOM_CONFIG;
  if (!config) return;

  // ---- TTS ----

  const synth = window.speechSynthesis;
  let ttsVoice = null;
  let muted = false;
  const speechRate = config.mode === 'memory_support' ? 0.85 : 1.0;

  // Pick a calm English voice when voices load
  function selectVoice() {
    const voices = synth.getVoices();
    // Prefer a female English voice for warmth
    const preferred = ['Samantha', 'Karen', 'Victoria', 'Google UK English Female', 'Microsoft Zira'];
    for (const name of preferred) {
      const v = voices.find(v => v.name.includes(name));
      if (v) { ttsVoice = v; return; }
    }
    // Fallback: first English voice
    ttsVoice = voices.find(v => v.lang.startsWith('en')) || voices[0] || null;
  }

  if (synth) {
    synth.onvoiceschanged = selectVoice;
    selectVoice();
  }

  function speak(text) {
    if (!synth || muted || !text) return;
    // Cancel any ongoing speech
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = speechRate;
    utterance.pitch = 1.0;
    utterance.volume = 0.9;
    if (ttsVoice) utterance.voice = ttsVoice;
    synth.speak(utterance);
  }

  // Mute toggle
  const muteBtn = document.getElementById('mute-btn');
  if (muteBtn) {
    muteBtn.addEventListener('click', () => {
      muted = !muted;
      muteBtn.classList.toggle('muted', muted);
      muteBtn.setAttribute('aria-label', muted ? 'Unmute voice' : 'Mute voice');
      muteBtn.querySelector('.mute-icon').textContent = muted ? '\u{1F507}' : '\u{1F50A}';
      if (muted && synth) synth.cancel();
    });
  }

  // ---- STT ----

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
