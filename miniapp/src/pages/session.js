/**
 * miniapp/src/pages/session.js
 *
 * String Session Generator page.
 * Uses MtprotoAuth for browser-side auth — credentials never touch the server.
 */

import { Card, EmptyState, showToast } from '../../lib/components.js?v=1.5.0';
import { apiFetch } from '../../lib/api.js?v=1.5.0';

export async function renderSessionPage(container) {
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: 480px; margin: 0 auto;';

  const consent = document.createElement('div');
  consent.innerHTML = `
    <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-5);">
      <div style="font-size:32px;text-align:center;margin-bottom:var(--sp-4);">🔑</div>
      <h2 style="font-size:var(--text-lg);font-weight:var(--fw-bold);margin:0 0 var(--sp-3);text-align:center;">String Session Generator</h2>
      <div style="background:rgba(var(--accent-rgb),0.08);border:1px solid rgba(var(--accent-rgb),0.2);border-radius:var(--r-lg);padding:var(--sp-3);margin-bottom:var(--sp-4);font-size:var(--text-sm);">
        <p style="margin:0 0 var(--sp-2);">✅ Your phone number and OTP go <b>directly to Telegram's servers</b></p>
        <p style="margin:0 0 var(--sp-2);">✅ Nexus <b>never sees</b> your credentials</p>
        <p style="margin:0;">✅ The session string is shown <b>only in your browser</b></p>
      </div>
      <div style="margin-bottom:var(--sp-4);">
        <div style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);">Generate for</div>
        <div style="display:flex;gap:var(--sp-2);">
          <button data-lib="gramjs" style="flex:1;padding:var(--sp-3);border:1px solid var(--accent);border-radius:var(--r-lg);background:var(--accent-dim);color:var(--accent);font-weight:var(--fw-semibold);cursor:pointer;font-size:var(--text-sm);">
            GramJS / Telethon
          </button>
          <button data-lib="pyrogram" style="flex:1;padding:var(--sp-3);border:1px solid var(--border);border-radius:var(--r-lg);background:transparent;color:var(--text-muted);cursor:pointer;font-size:var(--text-sm);">
            Pyrogram
          </button>
        </div>
        <div id="pyrogram-note" style="display:none;font-size:var(--text-xs);color:var(--text-muted);margin-top:var(--sp-2);">
          Pyrogram uses a different session format. We'll convert it server-side (not stored).
        </div>
      </div>
      <button id="consent-btn" class="btn btn-primary" style="width:100%;justify-content:center;">
        Continue →
      </button>
    </div>
  `;
  container.appendChild(consent);

  let selectedLib = 'gramjs';
  consent.querySelectorAll('[data-lib]').forEach(btn => {
    btn.onclick = () => {
      selectedLib = btn.dataset.lib;
      consent.querySelectorAll('[data-lib]').forEach(b => {
        b.style.borderColor = b === btn ? 'var(--accent)' : 'var(--border)';
        b.style.background = b === btn ? 'var(--accent-dim)' : 'transparent';
        b.style.color = b === btn ? 'var(--accent)' : 'var(--text-muted)';
      });
      document.getElementById('pyrogram-note').style.display = selectedLib === 'pyrogram' ? 'block' : 'none';
    };
  });

  consent.querySelector('#consent-btn').onclick = () => {
    consent.remove();
    _renderPhoneStep(container, selectedLib);
  };
}

function _renderPhoneStep(container, library) {
  const card = document.createElement('div');
  card.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-5);';
  card.innerHTML = `
    <div style="font-size:var(--text-sm);font-weight:var(--fw-semibold);margin-bottom:var(--sp-3);">📱 Phone Number</div>
    <input id="phone-input" class="input" type="tel" placeholder="+1234567890" style="margin-bottom:var(--sp-3);">
    <div id="phone-error" style="display:none;color:var(--danger);font-size:var(--text-xs);margin-bottom:var(--sp-2);"></div>
    <button id="send-code-btn" class="btn btn-primary" style="width:100%;justify-content:center;">Send Code</button>
    <p style="font-size:var(--text-xs);color:var(--text-muted);margin-top:var(--sp-3);text-align:center;">
      ⚠️ Requires @mtproto/core to be available. Works in browser only.
    </p>
  `;
  container.appendChild(card);

  card.querySelector('#send-code-btn').onclick = async (e) => {
    e.target.disabled = true;
    e.target.textContent = '⏳ Sending...';
    const phone = card.querySelector('#phone-input').value.trim();
    const errEl = card.querySelector('#phone-error');
    errEl.style.display = 'none';

    if (!phone) {
      errEl.textContent = 'Enter your phone number';
      errEl.style.display = 'block';
      e.target.disabled = false;
      e.target.textContent = 'Send Code';
      return;
    }

    try {
      const { MtprotoAuth } = await import('../../lib/mtproto_auth.js?v=1.5.0');
      const auth = new MtprotoAuth();
      const res = await auth.sendCode(phone);
      if (!res.ok) {
        errEl.textContent = res.error;
        errEl.style.display = 'block';
        e.target.disabled = false;
        e.target.textContent = 'Send Code';
        return;
      }
      card.remove();
      _renderOTPStep(container, auth, phone, library);
    } catch (err) {
      errEl.textContent = 'Failed to initialize MTProto: ' + err.message;
      errEl.style.display = 'block';
      e.target.disabled = false;
      e.target.textContent = 'Send Code';
    }
  };
}

function _renderOTPStep(container, auth, phone, library) {
  const card = document.createElement('div');
  card.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-5);';
  card.innerHTML = `
    <div style="font-size:var(--text-sm);font-weight:var(--fw-semibold);margin-bottom:var(--sp-2);">🔐 Verification Code</div>
    <div style="font-size:var(--text-xs);color:var(--text-muted);margin-bottom:var(--sp-3);">Code sent to ${phone}</div>
    <input id="otp-input" class="input" type="text" placeholder="12345" maxlength="5" style="letter-spacing:8px;font-size:24px;text-align:center;margin-bottom:var(--sp-3);">
    <div id="otp-error" style="display:none;color:var(--danger);font-size:var(--text-xs);margin-bottom:var(--sp-2);"></div>
    <button id="verify-btn" class="btn btn-primary" style="width:100%;justify-content:center;">Verify</button>
  `;
  container.appendChild(card);

  card.querySelector('#verify-btn').onclick = async (e) => {
    e.target.disabled = true;
    e.target.textContent = '⏳ Verifying...';
    const code = card.querySelector('#otp-input').value.trim();
    const errEl = card.querySelector('#otp-error');

    const res = await auth.signIn(code);
    if (!res.ok && res.error === '2FA_REQUIRED') {
      card.remove();
      _render2FAStep(container, auth, library);
      return;
    }
    if (!res.ok) {
      errEl.textContent = res.error;
      errEl.style.display = 'block';
      e.target.disabled = false;
      e.target.textContent = 'Verify';
      return;
    }
    card.remove();
    _showSessionResult(container, res.session_string, library, auth);
  };
}

function _render2FAStep(container, auth, library) {
  const card = document.createElement('div');
  card.style.cssText = 'background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r-xl);padding:var(--sp-5);';
  card.innerHTML = `
    <div style="font-size:var(--text-sm);font-weight:var(--fw-semibold);margin-bottom:var(--sp-3);">🔒 Two-Factor Password</div>
    <input id="pass-input" class="input" type="password" placeholder="Your 2FA password" style="margin-bottom:var(--sp-3);">
    <div id="pass-error" style="display:none;color:var(--danger);font-size:var(--text-xs);margin-bottom:var(--sp-2);"></div>
    <button id="pass-btn" class="btn btn-primary" style="width:100%;justify-content:center;">Verify Password</button>
  `;
  container.appendChild(card);

  card.querySelector('#pass-btn').onclick = async (e) => {
    e.target.disabled = true;
    e.target.textContent = '⏳ Checking...';
    const password = card.querySelector('#pass-input').value;
    const errEl = card.querySelector('#pass-error');

    const res = await auth.check2FA(password);
    if (!res.ok) {
      errEl.textContent = res.error;
      errEl.style.display = 'block';
      e.target.disabled = false;
      e.target.textContent = 'Verify Password';
      return;
    }
    card.remove();
    _showSessionResult(container, res.session_string, library, auth);
  };
}

async function _showSessionResult(container, session, library, auth) {
  let displaySession = session;

  if (library === 'pyrogram') {
    try {
      const res = await apiFetch('/api/session/convert', {
        method: 'POST',
        body: JSON.stringify({ gramjs_session: session }),
      });
      displaySession = res.pyrogram_session || session;
    } catch (_) {
      showToast('Conversion failed, showing GramJS session', 'warning');
    }
  }

  const usageCode = {
    gramjs: `const { TelegramClient } = require("telegram");\nconst { StringSession } = require("telegram/sessions");\n\nconst client = new TelegramClient(\n  new StringSession("${displaySession}"),\n  API_ID, API_HASH, {}\n);\nawait client.connect();`,
    pyrogram: `from pyrogram import Client\n\napp = Client(\n  "my_account",\n  api_id=API_ID,\n  api_hash="API_HASH",\n  session_string="${displaySession}"\n)\n\nasync with app:\n    print(await app.get_me())`,
  };

  const card = document.createElement('div');
  card.style.cssText = 'background:var(--bg-card);border:1px solid var(--success);border-radius:var(--r-xl);padding:var(--sp-5);';
  card.innerHTML = `
    <div style="color:var(--success);font-weight:var(--fw-bold);margin-bottom:var(--sp-3);">✅ Session Generated!</div>
    <div style="background:var(--bg-input);border-radius:var(--r-lg);padding:var(--sp-3);font-family:monospace;font-size:11px;word-break:break-all;max-height:120px;overflow-y:auto;margin-bottom:var(--sp-3);">
      ${displaySession}
    </div>
    <button id="copy-session-btn" class="btn btn-primary" style="width:100%;justify-content:center;margin-bottom:var(--sp-3);">
      📋 Copy Session String
    </button>
    <div style="background:rgba(255,180,0,0.1);border:1px solid rgba(255,180,0,0.3);border-radius:var(--r-lg);padding:var(--sp-3);font-size:var(--text-xs);color:var(--warning);margin-bottom:var(--sp-4);">
      ⚠️ This is your account key. Treat it like a password. Never share it or paste it in a chat.
    </div>
    <div style="font-size:var(--text-xs);font-weight:var(--fw-bold);color:var(--text-muted);text-transform:uppercase;margin-bottom:var(--sp-2);">Usage example</div>
    <pre style="background:var(--bg-input);border-radius:var(--r-lg);padding:var(--sp-3);font-size:11px;overflow-x:auto;white-space:pre-wrap;word-break:break-all;margin:0 0 var(--sp-3);">${usageCode[library]}</pre>
    <button id="new-session-btn" class="btn btn-secondary" style="width:100%;justify-content:center;">Generate another</button>
  `;
  container.appendChild(card);

  card.querySelector('#copy-session-btn').onclick = () => {
    navigator.clipboard.writeText(displaySession).catch(() => {});
    showToast('Session copied!', 'success');
    const btn = card.querySelector('#copy-session-btn');
    btn.textContent = '✓ Copied';
    btn.disabled = true;
  };

  card.querySelector('#new-session-btn').onclick = () => {
    container.innerHTML = '';
    renderSessionPage(container);
  };
}
