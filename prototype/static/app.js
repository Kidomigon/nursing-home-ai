/**
 * Room Companion — Chat Interface
 *
 * AJAX-based chat with typing indicators, auto-scroll,
 * help button intercept, and voice integration.
 */

(function () {
  'use strict';

  const config = window.ROOM_CONFIG;
  if (!config) return;

  const chatMessages = document.getElementById('chat-messages');
  const chatInput = document.getElementById('chat-input');
  const sendBtn = document.getElementById('send-btn');
  const helpBtn = document.getElementById('help-btn');
  const helpOverlay = document.getElementById('help-overlay');
  const helpForm = document.getElementById('help-form');
  const thinkingEl = document.getElementById('thinking-indicator');
  const slowThinkingEl = document.getElementById('slow-thinking');

  let isWaiting = false;
  let thinkingTimer = null;

  // ---- Chat messages ----

  function addMessage(text, sender, options = {}) {
    const wrapper = document.createElement('div');
    wrapper.className = `chat-bubble-wrapper ${sender}`;

    const bubble = document.createElement('div');
    bubble.className = `chat-bubble ${sender}`;
    bubble.textContent = text;

    const time = document.createElement('span');
    time.className = 'chat-time';
    const now = new Date();
    time.textContent = now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

    wrapper.appendChild(bubble);
    wrapper.appendChild(time);
    chatMessages.appendChild(wrapper);
    scrollToBottom();

    // TTS for companion messages
    if (sender === 'companion' && !options.silent && window.Voice) {
      window.Voice.speak(text);
    }

    return bubble;
  }

  function scrollToBottom() {
    requestAnimationFrame(() => {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    });
  }

  function showThinking() {
    if (thinkingEl) thinkingEl.style.display = 'flex';
    scrollToBottom();
    // Show "still thinking" after 10s
    thinkingTimer = setTimeout(() => {
      if (slowThinkingEl) slowThinkingEl.style.display = 'block';
    }, 10000);
  }

  function hideThinking() {
    if (thinkingEl) thinkingEl.style.display = 'none';
    if (slowThinkingEl) slowThinkingEl.style.display = 'none';
    if (thinkingTimer) {
      clearTimeout(thinkingTimer);
      thinkingTimer = null;
    }
  }

  // ---- Send message ----

  async function sendMessage(text) {
    text = (text || '').trim();
    if (!text || isWaiting) return;

    addMessage(text, 'resident', { silent: true });
    chatInput.value = '';
    chatInput.focus();
    isWaiting = true;
    sendBtn.disabled = true;
    showThinking();

    try {
      const resp = await fetch(`/api/room/${config.roomId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });

      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const data = await resp.json();
      hideThinking();
      addMessage(data.response, 'companion');

      if (data.alert_created) {
        showHelpConfirmation(data.severity);
      }
    } catch (err) {
      console.error('Chat error:', err);
      hideThinking();
      addMessage(
        "I'm having trouble connecting right now. The staff are always nearby if you need help.",
        'companion',
        { silent: true }
      );
    } finally {
      isWaiting = false;
      sendBtn.disabled = false;
    }
  }

  // ---- Help button ----

  function showHelpConfirmation(severity) {
    if (!helpOverlay) return;
    const label = helpOverlay.querySelector('.help-overlay-severity');
    if (label && severity) {
      label.textContent = severity === 'emergency' ? 'EMERGENCY' : severity.toUpperCase();
      label.className = `help-overlay-severity severity-${severity}`;
    }
    helpOverlay.classList.add('visible');
    setTimeout(() => {
      helpOverlay.classList.remove('visible');
    }, 3500);
  }

  if (helpBtn && helpForm) {
    helpBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      // Submit via AJAX to show overlay instead of redirect
      try {
        const formData = new FormData(helpForm);
        await fetch(helpForm.action, {
          method: 'POST',
          body: formData,
          redirect: 'manual',
        });
        showHelpConfirmation('emergency');
        addMessage(
          "Help is on the way. A staff member has been notified and will be with you shortly. Please stay where you are.",
          'companion'
        );
      } catch (err) {
        // Fallback: submit the form normally
        helpForm.submit();
      }
    });
  }

  // ---- Input handling ----

  if (sendBtn) {
    sendBtn.addEventListener('click', () => sendMessage(chatInput.value));
  }

  if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage(chatInput.value);
      }
    });
  }

  // ---- Greeting on load ----

  if (config.greeting) {
    addMessage(config.greeting, 'companion', { silent: false });
  }

  // ---- Live clock ----

  const clockEl = document.getElementById('live-clock');
  const dateEl = document.getElementById('live-date');

  function updateClock() {
    const now = new Date();
    if (clockEl) {
      clockEl.textContent = now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    }
    if (dateEl) {
      dateEl.textContent = now.toLocaleDateString([], {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric',
      });
    }
  }

  updateClock();
  setInterval(updateClock, 30000);

  // ---- Expose sendMessage for voice.js ----
  window.RoomChat = { sendMessage };
})();
