// Simple voice input using Web Speech API
// Fills the question textarea on the room page.

(function () {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const supportNote = document.getElementById('voice-support-note');
  const button = document.getElementById('voice-btn');
  const textarea = document.getElementById('question-input');
  const banner = document.getElementById('voice-banner');
  const bannerText = document.getElementById('voice-banner-text');

  if (!button || !textarea) return;

  if (!SpeechRecognition) {
    if (supportNote) {
      supportNote.textContent = 'Voice input not supported in this browser.';
    }
    button.disabled = true;
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.interimResults = true;
  recognition.continuous = false;

  let listening = false;
  let autoSendEnabled = false;

  const autoSendCheckbox = document.getElementById('auto-send-voice');
  if (autoSendCheckbox) {
    autoSendCheckbox.addEventListener('change', () => {
      autoSendEnabled = autoSendCheckbox.checked;
    });
  }

  function setListeningState(isOn) {
    listening = isOn;
    if (isOn) {
      button.textContent = 'Listening... (tap to stop)';
      button.classList.add('btn-listening');
      if (supportNote) supportNote.textContent = 'Speak clearly. Your words will appear in the box.';
    } else {
      button.textContent = '🎤 Speak';
      button.classList.remove('btn-listening');
      if (supportNote) supportNote.textContent = '';
    }
  }

  recognition.onresult = (event) => {
    let text = '';
    for (let i = 0; i < event.results.length; i++) {
      text += event.results[i][0].transcript;
    }
    textarea.value = text.trim();
  };

  recognition.onerror = (event) => {
    console.error('Speech recognition error:', event.error);
    if (supportNote) supportNote.textContent = 'Voice error: ' + event.error;
    setListeningState(false);
  };

  recognition.onend = () => {
    // Called when recognition stops naturally
    if (listening) {
      setListeningState(false);
      // Auto-submit if enabled and we have some text
      if (autoSendEnabled && textarea.value.trim()) {
        const form = textarea.closest('form');
        if (form) form.submit();
      }
    }
  };

  button.addEventListener('click', (e) => {
    e.preventDefault();
    if (listening) {
      recognition.stop();
      setListeningState(false);
    } else {
      try {
        recognition.start();
        setListeningState(true);
      } catch (err) {
        console.error('Could not start recognition:', err);
        setListeningState(false);
      }
    }
  });
})();
