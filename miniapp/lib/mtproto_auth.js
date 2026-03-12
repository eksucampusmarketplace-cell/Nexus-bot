/**
 * miniapp/lib/mtproto_auth.js
 *
 * Browser-side Telegram MTProto authentication.
 * Runs entirely on the user's device — auth IP = their phone IP.
 *
 * Exports:
 *   MtprotoAuth class with methods:
 *     sendCode(phone)          → { phone_code_hash }
 *     signIn(phone, hash, code) → { session_string } or { error: '2FA_REQUIRED' }
 *     check2FA(password)        → { session_string }
 *     generateQR()              → { qr_url, login_token } — poll checkQR()
 *     checkQR(login_token)      → { session_string } or { pending: true }
 *     exportSession()           → base64 session string compatible with Pyrogram
 *
 * All methods return { ok: true, ...data } or { ok: false, error: string }
 * Never throws — all exceptions caught and returned as error strings.
 */

import MTProto from '@mtproto/core';

const API_ID   = import.meta.env.VITE_TG_API_ID;
const API_HASH = import.meta.env.VITE_TG_API_HASH;
// These are the SAME api_id/api_hash used by your Pyrogram clients
// Safe to expose in frontend — Telegram API ID is not secret

export class MtprotoAuth {
  constructor() {
    this.mtproto = new MTProto({
      api_id:   parseInt(API_ID),
      api_hash: API_HASH,
    });
    this._phone      = '';
    this._phone_hash = '';
    this._password   = null;
  }


  async sendCode(phone) {
    /**
     * Step 1 of phone auth.
     * Sends OTP to the phone number via Telegram.
     * FROM USER'S BROWSER IP — zero server involvement.
     */
    this._phone = phone.trim().replace(/\s/g, '');
    try {
      const result = await this.mtproto.call('auth.sendCode', {
        phone_number:   this._phone,
        api_id:         parseInt(API_ID),
        api_hash:       API_HASH,
        settings:       { _: 'codeSettings' },
      });
      this._phone_hash = result.phone_code_hash;
      return { ok: true, phone_code_hash: result.phone_code_hash };
    } catch (e) {
      if (e.error_code === 61 && e.error_message === 'MIGRATE') {
        // DC migration — MTProto handles this automatically, retry
        return this.sendCode(phone);
      }
      return { ok: false, error: _mapError(e) };
    }
  }


  async signIn(code) {
    /**
     * Step 2 of phone auth.
     * Verify OTP code.
     * Returns session_string if success.
     * Returns { ok: false, error: '2FA_REQUIRED' } if account has 2FA.
     */
    try {
      const result = await this.mtproto.call('auth.signIn', {
        phone_number:    this._phone,
        phone_code_hash: this._phone_hash,
        phone_code:      code.trim(),
      });

      if (result._ === 'auth.authorizationSignUpRequired') {
        return { ok: false, error: 'This account does not exist. Use an existing Telegram account.' };
      }

      const session = await this._exportSession();
      return { ok: true, session_string: session, user: _extractUser(result.user) };

    } catch (e) {
      if (e.error_message === 'SESSION_PASSWORD_NEEDED') {
        return { ok: false, error: '2FA_REQUIRED' };
      }
      return { ok: false, error: _mapError(e) };
    }
  }


  async check2FA(password) {
    /**
     * 2FA password check.
     * Called when signIn returns 2FA_REQUIRED.
     */
    try {
      // Get SRP parameters
      const passwordInfo = await this.mtproto.call('account.getPassword', {});

      // Compute SRP answer using MTProto library's built-in SRP
      const { A, M1 } = await this.mtproto.crypto.computeSRP(
        passwordInfo,
        password
      );

      const result = await this.mtproto.call('auth.checkPassword', {
        password: {
          _:           'inputCheckPasswordSRP',
          srp_id:      passwordInfo.srp_id,
          A,
          M1,
        },
      });

      const session = await this._exportSession();
      return { ok: true, session_string: session, user: _extractUser(result.user) };

    } catch (e) {
      if (e.error_message === 'PASSWORD_HASH_INVALID') {
        return { ok: false, error: 'Wrong password. Try again.' };
      }
      return { ok: false, error: _mapError(e) };
    }
  }


  async generateQR() {
    /**
     * Start QR code login.
     * Returns QR URL to render as QR code image.
     * Poll checkQR() every 5s until scanned.
     */
    try {
      const result = await this.mtproto.call('auth.exportLoginToken', {
        api_id:        parseInt(API_ID),
        api_hash:      API_HASH,
        except_ids:    [],
      });

      // Encode token as tg://login?token=... URL
      const tokenB64 = btoa(String.fromCharCode(...result.token));
      const qr_url   = `tg://login?token=${tokenB64}`;

      this._qr_token  = result.token;
      this._qr_expiry = Date.now() + (result.expires * 1000);

      return {
        ok:          true,
        qr_url,
        login_token: tokenB64,
        expires_in:  result.expires,
      };
    } catch (e) {
      return { ok: false, error: _mapError(e) };
    }
  }


  async checkQR() {
    /**
     * Check if QR has been scanned.
     * Returns { ok: true, session_string } if scanned.
     * Returns { ok: true, pending: true } if still waiting.
     * Returns { ok: false, error: 'QR_EXPIRED' } if expired.
     */
    if (Date.now() > this._qr_expiry) {
      return { ok: false, error: 'QR_EXPIRED' };
    }

    try {
      const result = await this.mtproto.call('auth.importLoginToken', {
        token: this._qr_token,
      });

      if (result._ === 'auth.loginTokenSuccess') {
        const session = await this._exportSession();
        return { ok: true, session_string: session, user: _extractUser(result.authorization.user) };
      }

      return { ok: true, pending: true };
    } catch (e) {
      if (e.error_message === 'AUTH_TOKEN_EXPIRED') {
        return { ok: false, error: 'QR_EXPIRED' };
      }
      if (e.error_message === 'AUTH_TOKEN_INVALID') {
        return { ok: true, pending: true };
      }
      return { ok: false, error: _mapError(e) };
    }
  }


  async _exportSession() {
    /**
     * Export session data in a format compatible with Pyrogram.
     * Returns base64-encoded JSON that backend converts to
     * a valid Pyrogram StringSession.
     *
     * Backend validates this via /api/auth/validate-session
     * before storing it.
     */
    const authKey  = await this.mtproto.storage.get('authKey');
    const dcId     = await this.mtproto.storage.get('dcId');
    const userId   = await this.mtproto.storage.get('userId');

    const sessionData = {
      dc_id:    dcId   || 2,
      auth_key: authKey ? Array.from(authKey) : [],
      user_id:  userId || 0,
      api_id:   parseInt(API_ID),
    };

    return btoa(JSON.stringify(sessionData));
  }
}


// ── Helpers ────────────────────────────────────────────────────────────────

function _mapError(e) {
  const msg = e?.error_message || e?.message || String(e);
  const MAP = {
    'PHONE_NUMBER_INVALID':    'Invalid phone number. Include country code (e.g. +234...).',
    'PHONE_CODE_INVALID':      'Wrong code. Check the message Telegram sent you.',
    'PHONE_CODE_EXPIRED':      'Code expired. Request a new one.',
    'PHONE_NUMBER_BANNED':     'This phone number is banned on Telegram.',
    'TOO_MANY_REQUESTS':       'Too many attempts. Wait a few minutes.',
    'FLOOD_WAIT':              'Too many attempts. Wait before trying again.',
    'PASSWORD_HASH_INVALID':   'Wrong 2FA password.',
    'AUTH_TOKEN_EXPIRED':      'QR code expired. Generate a new one.',
  };
  return MAP[msg] || `Telegram error: ${msg}`;
}

function _extractUser(user) {
  if (!user) return null;
  return {
    id:         user.id,
    first_name: user.first_name || '',
    last_name:  user.last_name  || '',
    username:   user.username   || '',
  };
}
