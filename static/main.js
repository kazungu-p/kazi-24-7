/* static/js/main.js
   Messaging + Notifications helper
   - Requires: base.html injects window.__CSRF_TOKEN (you already added this)
   - Uses: /messages/send, /messages/unread_count, /notifications/count, /notifications/mark-read
*/

(function () {
  'use strict';

  // ---- Helpers ----
  function csrfToken() {
    return window.__CSRF_TOKEN || (document.querySelector('meta[name=csrf-token]') && document.querySelector('meta[name=csrf-token]').content) || '';
  }

  async function postJSON(url, payload) {
    const res = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken()
      },
      body: JSON.stringify(payload || {})
    });

    const ct = res.headers.get('content-type') || '';
    const isJson = ct.includes('application/json');

    if (!res.ok) {
      let bodyText = '';
      try { bodyText = isJson ? JSON.stringify(await res.json()) : await res.text(); } catch (e) { bodyText = '[unreadable]'; }
      throw new Error(`Request failed ${res.status}: ${bodyText}`);
    }
    return isJson ? await res.json() : null;
  }

  async function getJSON(url) {
    const res = await fetch(url, { credentials: 'same-origin', headers: { 'Accept': 'application/json' }});
    if (!res.ok) throw new Error(`GET ${url} failed ${res.status}`);
    return await res.json();
  }

  // ---- API wrappers ----
  async function sendMessage(recipientId, body) {
    return await postJSON('/messages/send', { recipient_id: recipientId, body: body });
  }

  async function markNotificationsRead(ids) {
    // ids: array of ids or empty to mark all
    const payload = Array.isArray(ids) ? { ids: ids } : {};
    return await postJSON('/notifications/mark-read', payload);
  }

  async function fetchBadges() {
    const [m, n] = await Promise.allSettled([
      getJSON('/messages/unread_count'),
      getJSON('/notifications/count')
    ]);

    const messagesCount = (m.status === 'fulfilled' && m.value && typeof m.value.count === 'number') ? m.value.count : 0;
    const notificationsCount = (n.status === 'fulfilled' && n.value && typeof n.value.count === 'number') ? n.value.count : 0;
    updateBadgeUI(messagesCount, notificationsCount);
  }

  // ---- UI updates ----
  function updateBadgeUI(messagesCount, notificationsCount) {
    const mb = document.getElementById('messages-badge');
    const nb = document.getElementById('notifications-badge');
    function setBadge(el, count) {
      if (!el) return;
      if (count && count > 0) {
        el.style.display = 'inline-block';
        el.textContent = count > 99 ? '99+' : String(count);
      } else {
        el.style.display = 'none';
        el.textContent = '';
      }
    }
    setBadge(mb, messagesCount);
    setBadge(nb, notificationsCount);

    // Also update any page-local top-messages-badge
    const topMB = document.getElementById('top-messages-badge');
    if (topMB) setBadge(topMB, messagesCount);
  }

  // Mark a single notification item in the DOM as read
  function markNotificationDOMRead(id) {
    const el = document.querySelector(`.notification-item[data-id="${id}"]`);
    if (!el) return;
    el.classList.remove('notification-unread');
    el.setAttribute('data-read', 'true');

    // if there's a .badge inside, remove it
    const badge = el.querySelector('.notification-badge');
    if (badge) badge.remove();
  }

  // Update conversation preview for a recipient (when you send a message)
  function updateConversationPreview(recipientId, lastMessageText) {
    const conv = document.querySelector(`.conversation-item[data-other-id="${recipientId}"]`);
    if (!conv) return;
    const lastEl = conv.querySelector('.conversation-last');
    if (lastEl) lastEl.textContent = lastMessageText;
    // Move conversation to top if you want:
    const parent = conv.parentElement;
    if (parent) {
      parent.prepend(conv);
    }
  }

  // Append new message to message thread if messages list exists
  function appendMessageToThread(message) {
    // message: { id, sender_id, recipient_id, body, created_at, read, sender_name }
    const list = document.getElementById('messagesList') || document.querySelector('.messages-list');
    if (!list) return;

    const isSent = (message.sender_id === window.__CURRENT_USER_ID); // you can expose CURRENT_USER_ID from template if desired
    const wrapper = document.createElement('div');
    wrapper.className = isSent ? 'message-bubble message-sent mb-2' : 'message-bubble message-recv mb-2';
    wrapper.innerHTML = `<div>${escapeHtml(message.body)}</div><div class="small text-muted mt-1">${new Date(message.created_at).toLocaleString()}</div>`;
    list.appendChild(wrapper);
    // scroll into view
    wrapper.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }

  // Simple HTML escape
  function escapeHtml(s) {
    if (!s) return '';
    return s.replace(/[&<>"']/g, function (m) { return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]); });
  }

  // ---- Event bindings & public API ----
  document.addEventListener('DOMContentLoaded', function () {
    // Expose to window
    window.appAPI = window.appAPI || {};
    window.appAPI.sendMessage = async function(recipientId, body) {
      const res = await sendMessage(recipientId, body);
      // res should include message object
      if (res && res.status === 'ok' && res.message) {
        appendMessageToThread(res.message);
        updateConversationPreview(recipientId, res.message.body);
        // Refresh badges shortly after sending
        setTimeout(fetchBadges, 400);
        return res;
      }
      return res;
    };
    window.appAPI.markNotificationsRead = async function(ids) {
      await markNotificationsRead(ids);
      if (Array.isArray(ids) && ids.length) {
        ids.forEach(id => markNotificationDOMRead(id));
      } else {
        // marked all: remove unread look from all items
        document.querySelectorAll('.notification-item.notification-unread').forEach(el => {
          el.classList.remove('notification-unread');
          el.setAttribute('data-read', 'true');
          const badge = el.querySelector('.notification-badge');
          if (badge) badge.remove();
        });
      }
      // refresh badges
      setTimeout(fetchBadges, 150);
    };

    // Bind message form if exists (AJAX)
    const msgForm = document.getElementById('message-form');
    if (msgForm) {
      msgForm.addEventListener('submit', async function (ev) {
        ev.preventDefault();
        const btn = msgForm.querySelector('button[type="submit"]');
        const recipientInput = msgForm.querySelector('input[name="recipient_id"]');
        const bodyInput = msgForm.querySelector('textarea[name="body"]');
        const recipient = recipientInput ? recipientInput.value : null;
        const body = bodyInput ? bodyInput.value.trim() : '';

        if (!recipient || !body) {
          alert('Please enter a message.');
          return;
        }

        try {
          if (btn) { btn.disabled = true; btn.innerHTML = '<span class="loading-spinner" aria-hidden="true"></span> Sending'; }
          const res = await window.appAPI.sendMessage(Number(recipient), body);
          // Clear textarea on success
          if (bodyInput) bodyInput.value = '';
        } catch (err) {
          console.error('Send message error', err);
          alert('Failed to send message: ' + (err.message || err));
        } finally {
          if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-send"></i> Send'; }
        }
      });
    }

    // Bind notification item clicks (delegate)
    document.body.addEventListener('click', function (ev) {
      const ni = ev.target.closest('.notification-item');
      if (!ni) return;
      // if it contains a data-target-url, navigate after marking read
      const nid = ni.getAttribute('data-id');
      const target = ni.getAttribute('data-target-url');
      const isRead = ni.getAttribute('data-read') === 'true';

      if (isRead) {
        if (target) location.href = target;
        return;
      }

      // prevent default anchor if any
      ev.preventDefault();

      // mark this notification as read, then navigate
      window.appAPI.markNotificationsRead([Number(nid)]).then(() => {
        if (target) location.href = target;
      }).catch(err => {
        console.error('Mark notification read failed', err);
        alert('Failed to mark notification read: ' + (err.message || err));
      });
    });

    // Poll badges every 20s and update immediately on load
    fetchBadges();
    setInterval(fetchBadges, 20000);

    // Optional: if conversation list or notifications are updated elsewhere, expose a refresh function
    window.appAPI.refreshBadges = fetchBadges;
  });

})();