/**
 * miniapp/lib/rule_templates.js
 *
 * One-tap group presets.
 * Each template sets a bundle of automod rules at once.
 * Applied via PUT /api/groups/{chat_id}/settings/bulk
 */

export const RULE_TEMPLATES = [
  {
    id:          'gaming',
    name:        '🎮 Gaming Group',
    description: 'Allow media, memes, voice. Block links and spam.',
    settings: {
      lock_link: true, lock_website: true,
      lock_channel: true,
      antiflood: true, antiflood_limit: 8, antiflood_action: 'mute',
      warn_enabled: true, warn_max: 3, warn_action: 'mute_1h',
    },
  },
  {
    id:          'study',
    name:        '📚 Study / Academic',
    description: 'Text and files only. No media spam. Strict flood control.',
    settings: {
      lock_sticker: true, lock_gif: true,
      lock_voice: false, lock_document: false,
      antiflood: true, antiflood_limit: 5, antiflood_action: 'mute',
      min_words: 3,
      warn_enabled: true, warn_max: 2, warn_action: 'ban_24h',
    },
  },
  {
    id:          'crypto',
    name:        '₿ Crypto / Trading',
    description: 'Anti-shill, anti-spam. No unofficial Telegram, no userbots.',
    settings: {
      lock_link: true, lock_username: true,
      lock_unofficial_tg: true, lock_userbots: true,
      lock_bot: true, lock_bot_inviter: true,
      duplicate_limit: 1,
      antiflood: true, antiflood_limit: 6, antiflood_action: 'ban',
      warn_enabled: true, warn_max: 2, warn_action: 'ban_permanent',
      captcha_enabled: true,
    },
  },
  {
    id:          'community',
    name:        '🏘 Community / General',
    description: 'Balanced defaults. Good for most groups.',
    settings: {
      lock_link: false, lock_unofficial_tg: true,
      lock_userbots: true, lock_bot: true,
      antiflood: true, antiflood_limit: 10, antiflood_action: 'mute',
      warn_enabled: true, warn_max: 5, warn_action: 'mute_12h',
      welcome: true, rules: true,
    },
  },
  {
    id:          'announcement',
    name:        '📢 Announcement Only',
    description: 'Only admins can post. Everyone else is read-only.',
    settings: {
      lock_text: true, lock_photo: true,
      lock_video: true, lock_sticker: true,
      lock_document: true, lock_voice: true,
      lock_gif: true, lock_forward: true,
    },
  },
  {
    id:          'strict',
    name:        '🔒 Strict / Zero Tolerance',
    description: 'Everything locked except plain text. Max enforcement.',
    settings: {
      lock_link: true, lock_website: true,
      lock_username: true, lock_forward: true,
      lock_photo: true, lock_video: true,
      lock_sticker: true, lock_gif: true,
      lock_voice: true, lock_document: true,
      lock_unofficial_tg: true, lock_userbots: true,
      lock_bot: true, lock_bot_inviter: true,
      lock_porn: true, lock_hashtag: true,
      antiflood: true, antiflood_limit: 5, antiflood_action: 'ban',
      warn_enabled: true, warn_max: 1, warn_action: 'ban_permanent',
      captcha_enabled: true,
    },
  },
];


export async function applyTemplate(chatId, templateId) {
  const template = RULE_TEMPLATES.find(t => t.id === templateId);
  if (!template) throw new Error('Template not found');

  const { apiFetch } = await import('./api.js?v=1.6.0');
  return apiFetch(`/api/groups/${chatId}/settings/bulk`, {
    method: 'PUT',
    body: { settings: template.settings },
  });
}
