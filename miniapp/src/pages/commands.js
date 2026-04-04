/**
 * miniapp/src/pages/commands.js
 *
 * Commands reference page with per-command toggling.
 * Shows all available bot commands organized by category,
 * with toggles to enable/disable each command for the group.
 */

import { Card, EmptyState, Toggle, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';
import { t } from '../../lib/i18n.js?v=1.6.0';

/**
 * Command aliases - shorthand versions of commands
 */
const COMMAND_ALIASES = {
  '/w': '/warn', '/uw': '/unwarn', '/m': '/mute', '/um': '/unmute',
  '/tm': '/tmute', '/b': '/ban', '/ub': '/unban', '/tb': '/tban',
  '/k': '/kick', '/p': '/purge', '/d': '/del', '/s': '/lock',
  '/r': '/rules', '/n': '/note', '/gn': '/note', '/sn': '/notes',
  '/i': '/info', '/wi': '/info', '/ci': '/groupinfo',
  '/ws': '/warns', '/wl': '/warnlimit', '/wa': '/warnmode',
  '/post': '/channelpost', '/sched': '/schedulepost',
  '/ap': '/approvepost', '/cp': '/cancelpost',
  '/ep': '/editpost', '/dp': '/deletepost',
  '/sw': '/setwelcome', '/sg': '/setgoodbye', '/sr': '/setrules',
  '/rw': '/resetwelcome', '/rg': '/resetgoodbye', '/rr': '/resetrules',
  '/sc': '/captcha', '/raidmode': '/antiraid',
  '/clearwarns': '/resetwarns', '/pinner': '/pin', '/unpinner': '/unpin',
};

const store = useStore;

/**
 * Command categories and their commands
 */
const COMMAND_CATEGORIES = [
  {
    id: 'moderation',
    title: '🛡️ Moderation',
    description: 'Essential moderation commands',
    icon: '🛡️',
    commands: [
      { cmd: '/warn', args: '<reason>', desc: 'Warn a user (reply to their message)' },
      { cmd: '/unwarn', args: '', desc: 'Remove a warning from user (reply to their message)' },
      { cmd: '/warns', args: '[@username]', desc: 'Show warnings for a user (reply or mention)' },
      { cmd: '/resetwarns', args: '[@user|reply]', desc: 'Clear all warnings for a user' },
      { cmd: '/warnmode', args: '<mute|kick|ban|tban>', desc: 'Set action when max warns reached' },
      { cmd: '/warnlimit', args: '<1-10>', desc: 'Set max warnings before action' },
      { cmd: '/mute', args: '<duration>', desc: 'Mute a user - reply to message or use /mute @user 1h' },
      { cmd: '/unmute', args: '', desc: 'Unmute a user (reply or /unmute @user)' },
      { cmd: '/smute', args: '[@user|reply] [reason]', desc: 'Silent mute (no notification)' },
      { cmd: '/restrict', args: '[@user|reply] [reason]', desc: 'Restrict user (no media, can still text)' },
      { cmd: '/unrestrict', args: '[@user|reply]', desc: 'Remove restrictions from user' },
      { cmd: '/ban', args: '<reason>', desc: 'Ban a user - reply to message or /ban @user reason' },
      { cmd: '/unban', args: '<user_id>', desc: 'Unban a user by user ID (/unban 123456789)' },
      { cmd: '/kick', args: '<reason>', desc: 'Kick a user - reply to message or /kick @user' },
      { cmd: '/skick', args: '[@user|reply] [reason]', desc: 'Silent kick (no notification)' },
      { cmd: '/purge', args: '<count> [all]', desc: 'Delete recent messages. /purge 50 or /purge 50 all' },
      { cmd: '/delall', args: '[@user|reply]', desc: 'Delete all messages from user (last 24h)' },
      { cmd: '/purgeme', args: '<count>', desc: 'Delete your own messages only' },
      { cmd: '/title', args: '[@user|reply] <title>', desc: 'Set custom admin title' },
      { cmd: '/kickme', args: '', desc: 'Kick yourself from the group' },
    ]
  },
  {
    id: 'security',
    title: '🔒 Security',
    description: 'Anti-spam and security features',
    icon: '🔒',
    commands: [
      { cmd: '!antispam', args: '', desc: 'Toggle anti-spam protection' },
      { cmd: '!antiflood', args: '', desc: 'Toggle anti-flood (rapid messages)' },
      { cmd: '!antilink', args: '', desc: 'Toggle anti-link (block links)' },
      { cmd: '!captcha', args: '', desc: 'Toggle CAPTCHA verification' },
      { cmd: '!antiraid', args: '', desc: 'Toggle anti-raid mode' },
      { cmd: '/slowmode', args: '<seconds>', desc: 'Set slow mode delay (0-300s)' },
      { cmd: '/setflood', args: '<number>', desc: 'Set flood message limit' },
      { cmd: '/filter', args: '<keyword> <response>', desc: 'Add keyword auto-reply' },
      { cmd: '/filters', args: '', desc: 'List all keyword filters' },
      { cmd: '/stop', args: '<keyword>', desc: 'Remove a keyword filter' },
      { cmd: '/stopall', args: '', desc: 'Remove all keyword filters' },
      { cmd: '/blacklist', args: '<word>', desc: 'Add word to blacklist (auto-delete messages)' },
      { cmd: '/unblacklist', args: '<word>', desc: 'Remove word from blacklist' },
      { cmd: '/blacklistmode', args: '<delete|warn|mute|ban>', desc: 'Set action when blacklisted word is sent' },
    ]
  },
  {
    id: 'notes',
    title: '📝 Notes',
    description: 'Save and retrieve content snippets',
    icon: '📝',
    commands: [
      { cmd: '/savenote', args: '<name> [text]', desc: 'Save a note. Reply to any message to save media.' },
      { cmd: '/note', args: '<name>', desc: 'Retrieve a saved note' },
      { cmd: '/notes', args: '', desc: 'List all saved notes for this group' },
      { cmd: '/delnote', args: '<name>', desc: 'Delete a saved note' },
    ]
  },
  {
    id: 'greetings',
    title: '👋 Greetings',
    description: 'Welcome and goodbye messages',
    icon: '👋',
    commands: [
      { cmd: '/setwelcome', args: '<message>', desc: 'Set welcome message for new members' },
      { cmd: '/setgoodbye', args: '<message>', desc: 'Set goodbye message' },
      { cmd: '/setrules', args: '<rules>', desc: 'Set group rules' },
      { cmd: '/welcome', args: '', desc: 'Preview welcome message' },
      { cmd: '/goodbye', args: '', desc: 'Preview goodbye message' },
      { cmd: '/rules', args: '', desc: 'Show group rules' },
      { cmd: '/resetwelcome', args: '', desc: 'Reset welcome to default' },
      { cmd: '/resetgoodbye', args: '', desc: 'Reset goodbye to default' },
      { cmd: '/resetrules', args: '', desc: 'Reset rules to default' },
      { cmd: '/setup', args: '', desc: 'Re-run the setup wizard for this group' },
    ]
  },
  {
    id: 'engagement',
    title: '⭐ Engagement',
    description: 'XP, reputation, and badges',
    icon: '⭐',
    commands: [
      { cmd: '/rank', args: '[@user]', desc: 'Show XP rank card' },
      { cmd: '/top', args: '', desc: 'XP leaderboard' },
      { cmd: '/leaderboard', args: '', desc: 'XP leaderboard (alias)' },
      { cmd: '/levels', args: '', desc: 'Show level progression' },
      { cmd: '/rep', args: '@user [reason]', desc: 'Give +1 reputation' },
      { cmd: '/repboard', args: '', desc: 'Reputation leaderboard' },
      { cmd: '/profile', args: '[@user]', desc: 'Full member profile' },
      { cmd: '/checkin', args: '', desc: 'Daily check-in for XP' },
      { cmd: '/badges', args: '[@user]', desc: 'Show earned badges' },
      { cmd: '/givexp', args: '@user <amount>', desc: 'Admin: give XP' },
      { cmd: '/removexp', args: '@user <amount>', desc: 'Admin: remove XP' },
      { cmd: '/doublexp', args: '<hours>', desc: 'Admin: start double XP event' },
      { cmd: '/network', args: '', desc: 'Show network status' },
      { cmd: '/joinnetwork', args: '<code>', desc: 'Join a network' },
      { cmd: '/createnetwork', args: '<name>', desc: 'Create a network' },
      { cmd: '/networktop', args: '', desc: 'Network leaderboard' },
    ]
  },
  {
    id: 'fun',
    title: '🎮 Fun & Games',
    description: 'Fun commands for everyone',
    icon: '🎮',
    commands: [
      { cmd: '/afk', args: '<reason>', desc: 'Set AFK status' },
      { cmd: '/back', args: '', desc: 'Clear AFK status' },
      { cmd: '/poll', args: '<question>', desc: 'Create a yes/no poll' },
      { cmd: '/dice', args: '', desc: 'Roll a dice' },
      { cmd: '/coin', args: '', desc: 'Flip a coin' },
      { cmd: '/choose', args: 'opt1|opt2', desc: 'Randomly choose between options' },
      { cmd: '/8ball', args: '<question>', desc: 'Magic 8-ball response' },
      { cmd: '/roll', args: '<max>', desc: 'Roll random number (1-max)' },
      { cmd: '/joke', args: '', desc: 'Get a random joke' },
      { cmd: '/quote', args: '', desc: 'Get an inspirational quote' },
      { cmd: '/roast', args: '', desc: 'Playful roast (reply to someone)' },
      { cmd: '/compliment', args: '', desc: 'Give a compliment (reply to someone)' },
      { cmd: '/calc', args: '<expression>', desc: 'Simple calculator (e.g., 5 + 3)' },
    ]
  },
  {
    id: 'admin',
    title: '⚡ Admin Tools',
    description: 'Advanced administration tools',
    icon: '⚡',
    commands: [
      { cmd: '/announce', args: '<message>', desc: 'Send announcement to group' },
      { cmd: '/export', args: '', desc: 'Export group settings as JSON file' },
      { cmd: '/import', args: '', desc: 'Import settings from JSON (reply to file)' },
      { cmd: '/reset', args: '', desc: 'Reset all group settings to defaults' },
      { cmd: '/copysettings', args: '<chat_id>', desc: 'Copy settings from another group' },
      { cmd: '/setlog', args: '<channel_id>', desc: 'Set log channel for moderation events' },
      { cmd: '/unsetlog', args: '', desc: 'Remove log channel' },
      { cmd: '/logchannel', args: '', desc: 'Show current log channel info' },
      { cmd: '/personality', args: '[tone]', desc: 'Set bot personality tone' },
      { cmd: '/autodelete', args: '<seconds>', desc: 'Auto-delete bot messages after delay' },
      { cmd: '/autorole', args: '', desc: 'Configure auto-role for new members' },
    ]
  },
  {
    id: 'pins',
    title: '📌 Pin Management',
    description: 'Advanced pin management commands',
    icon: '📌',
    commands: [
      { cmd: '/pin', args: '[silent]', desc: 'Pin replied message (silent=no notify)' },
      { cmd: '/unpin', args: '', desc: 'Unpin current pinned message' },
      { cmd: '/unpinall', args: '', desc: 'Unpin all messages in group' },
      { cmd: '/repin', args: '', desc: 'Re-pin the last pinned message' },
      { cmd: '/editpin', args: '<text>', desc: 'Edit the pinned message text' },
      { cmd: '/delpin', args: '', desc: 'Delete the pinned message' },
    ]
  },
  {
    id: 'channel',
    title: '📢 Channel Management',
    description: 'Channel posting and scheduling',
    icon: '📢',
    commands: [
      { cmd: '/channelpost', args: '<message>', desc: 'Post to linked channel' },
      { cmd: '/schedulepost', args: '<time> <message>', desc: 'Schedule a channel post' },
      { cmd: '/approvepost', args: '', desc: 'Approve scheduled post' },
      { cmd: '/cancelpost', args: '', desc: 'Cancel scheduled post' },
      { cmd: '/editpost', args: '<post_id> <message>', desc: 'Edit scheduled post' },
      { cmd: '/deletepost', args: '<post_id>', desc: 'Delete scheduled post' },
    ]
  },
  {
    id: 'economy',
    title: '⭐ Economy',
    description: 'Stars economy system',
    icon: '⭐',
    commands: [
      { cmd: '/redeem', args: '<code>', desc: 'Redeem a promo code' },
      { cmd: '/referral', args: '', desc: 'Get referral link and stats' },
      { cmd: '/mystars', args: '', desc: 'Show Stars balance and purchases' },
    ]
  },
  {
    id: 'public',
    title: '👥 Public Commands',
    description: 'Commands for all group members',
    icon: '👥',
    commands: [
      { cmd: '/rules', args: '', desc: 'Show group rules' },
      { cmd: '/time', args: '', desc: 'Show current group time' },
      { cmd: '/id', args: '', desc: 'Get your user ID and chat ID' },
      { cmd: '/report', args: '<reason>', desc: 'Report a message to admins (reply)' },
      { cmd: '/adminlist', args: '', desc: 'List all group admins' },
      { cmd: '/staff', args: '', desc: 'Alias for /adminlist' },
      { cmd: '/invitelink', args: '', desc: 'Get group invite link' },
      { cmd: '/groupinfo', args: '', desc: 'Show group statistics and features' },
    ]
  },
  {
    id: 'utilities',
    title: '🔧 Utilities',
    description: 'General utility commands',
    icon: '🔧',
    commands: [
      { cmd: '/panel', args: '', desc: 'Open mini app management panel' },
      { cmd: '/help', args: '', desc: 'Show help message with command list' },
      { cmd: '/info', args: '', desc: 'Show basic group information' },
      { cmd: '/admins', args: '', desc: 'List group admins (alias for /adminlist)' },
      { cmd: '/stats', args: '', desc: 'Show group statistics' },
      { cmd: '/privacy', args: '', desc: 'View privacy policy in mini app' },
    ]
  },
  {
    id: 'scheduling',
    title: '⏰ Scheduling',
    description: 'Schedule messages and events',
    icon: '⏰',
    commands: [
      { cmd: '/schedule', args: '<time> <message>', desc: 'Schedule a message for later' },
    ]
  },
  {
    id: 'verification',
    title: '🔐 Verification',
    description: 'Member verification and passwords',
    icon: '🔐',
    commands: [
      { cmd: '/setpassword', args: '<password>', desc: 'Set group password for new members' },
      { cmd: '/clearpassword', args: '', desc: 'Remove group password' },
    ]
  },
  {
    id: 'community',
    title: '🗳️ Community',
    description: 'Voting and community features',
    icon: '🗳️',
    commands: [
      { cmd: '/vote', args: '<question>', desc: 'Start a community vote' },
      { cmd: '/votekick', args: '', desc: 'Start a vote to kick a user (reply)' },
      { cmd: '/votesettings', args: '', desc: 'Configure community vote settings' },
      { cmd: '/votestats', args: '', desc: 'Show voting statistics' },
    ]
  },
  {
    id: 'history',
    title: '📜 Name History',
    description: 'Track member name changes',
    icon: '📜',
    commands: [
      { cmd: '/history', args: '[@user]', desc: 'Show name change history' },
      { cmd: '/historyoptout', args: '', desc: 'Opt out of name tracking' },
      { cmd: '/historyoptin', args: '', desc: 'Opt back in to name tracking' },
      { cmd: '/historydelete', args: '', desc: 'Delete your name history' },
    ]
  },
  {
    id: 'language',
    title: '🌐 Language',
    description: 'Language settings',
    icon: '🌐',
    commands: [
      { cmd: '/lang', args: '<code>', desc: 'Set your personal language' },
      { cmd: '/grouplang', args: '<code>', desc: 'Set group language (admin)' },
      { cmd: '/languages', args: '', desc: 'Show available languages' },
    ]
  }
];

/**
 * Render the Commands reference page with per-command toggling
 * @param {HTMLElement} container - Container element to render into
 */
export async function renderCommandsPage(container) {
  const state = store.getState();
  const chatId = state.activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId && state.groups && state.groups.length > 0) {
    state.setActiveChatId(state.groups[0].chat_id);
  }

  const finalChatId = store.getState().activeChatId;
  const settings = store.getState().settings || {};

  if (!finalChatId) {
    container.appendChild(EmptyState({
      icon: '👆',
      title: t('select_group', 'Select a group'),
      description: t('commands_select_group', 'Choose a group to see available commands')
    }));
    return;
  }

  // Load command toggle states from API
  let commandStates = {};
  try {
    const res = await apiFetch(`/api/groups/${finalChatId}/commands/states`);
    commandStates = res || {};
  } catch (e) {
    console.debug('Command states not available, all enabled by default');
  }

  const activeCategories = [...COMMAND_CATEGORIES];
  if (settings.booster_enabled === true) {
    activeCategories.push({
      id: 'booster',
      title: '🚀 Booster',
      description: 'Channel and member booster commands',
      icon: '🚀',
      commands: [
        { cmd: '/booststats', args: '', desc: 'Show boost requirements and progress' },
        { cmd: '/myboost', args: '', desc: 'Check your personal boost status' },
        { cmd: '/grantboost', args: '<user_id>', desc: 'Manually grant access to a user' },
        { cmd: '/revokeboost', args: '<user_id>', desc: 'Revoke manually granted access' },
        { cmd: '/setboost', args: '<count>', desc: 'Set required invite count' },
        { cmd: '/resetboost', args: '<user_id>', desc: 'Reset boost record for a user' },
      ]
    });
  }

  // Header with description
  const header = document.createElement('div');
  header.style.cssText = 'margin-bottom: var(--sp-6);';
  header.innerHTML = `
    <div style="
      background: linear-gradient(135deg, rgba(var(--accent-rgb), 0.1), rgba(var(--accent-rgb), 0.05));
      border: 1px solid rgba(var(--accent-rgb), 0.2);
      border-radius: var(--r-xl);
      padding: var(--sp-5);
      margin-bottom: var(--sp-4);
    ">
      <div style="font-size: 24px; margin-bottom: var(--sp-2);">📚 <b>${t('commands_title', 'Complete Command Reference')}</b></div>
      <div style="color: var(--text-secondary); font-size: var(--text-sm); line-height: 1.6;">
        All available bot commands with detailed descriptions and usage examples.
        <br><br>
        <b>💡 Usage Tip:</b> Most moderation commands work by <b>replying</b> to a user's message, or you can use @username (e.g., <code>/ban @spammer</code>)
        <br><br>
        <b>📦 Modules vs 🛡️ AutoMod:</b>
        <br>• <b>Modules</b> = Simple on/off toggles for features (Welcome, Rules, Captcha)
        <br>• <b>AutoMod</b> = Deep configuration with thresholds, actions, regex patterns, word filters, and rule priorities
        <br><br>
        <b>🔧 Deep Configuration:</b> Use the AutoMod, Settings, and Modules pages for advanced options beyond simple commands.
        <br><br>
        <b>🔄 Command Toggling:</b> Use the toggle switches to enable or disable individual commands for this group. Disabled commands will not respond.
      </div>
    </div>
  `;
  container.appendChild(header);

  // Search box
  const searchContainer = document.createElement('div');
  searchContainer.style.cssText = 'margin-bottom: var(--sp-4);';
  searchContainer.innerHTML = `
    <input
      type="text"
      id="cmd-search"
      placeholder="🔍 ${t('commands_search', 'Search commands...')}"
      class="input"
      style="
        width: 100%;
        padding: var(--sp-3) var(--sp-4);
        background: var(--bg-input);
        border: 1px solid var(--border);
        border-radius: var(--r-lg);
        color: var(--text-primary);
        font-size: var(--text-base);
      "
    >
  `;
  container.appendChild(searchContainer);

  // Commands content
  const contentContainer = document.createElement('div');
  contentContainer.id = 'commands-content';
  container.appendChild(contentContainer);

  // Render all active categories with toggles
  renderCategories(contentContainer, activeCategories, commandStates, finalChatId);

  // Search functionality
  const searchInput = searchContainer.querySelector('#cmd-search');
  searchInput.addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase();
    if (query) {
      const filtered = filterCommands(query, activeCategories);
      renderSearchResults(contentContainer, filtered, query, commandStates, finalChatId);
    } else {
      renderCategories(contentContainer, activeCategories, commandStates, finalChatId);
    }
  });
}

function filterCommands(query, categories) {
  const results = [];
  
  categories.forEach(cat => {
    const matchingCmds = cat.commands.filter(cmd => 
      cmd.cmd.toLowerCase().includes(query) ||
      cmd.desc.toLowerCase().includes(query) ||
      cat.title.toLowerCase().includes(query)
    );
    
    if (matchingCmds.length > 0) {
      results.push({
        ...cat,
        commands: matchingCmds
      });
    }
  });
  
  return results;
}

function renderCategories(container, categories, commandStates, chatId) {
  container.innerHTML = '';
  categories.forEach(category => {
    const catEl = document.createElement('div');
    catEl.className = 'command-category';
    catEl.style.cssText = 'margin-bottom: var(--sp-4);';

    // Category header with bulk toggle
    const catHeader = document.createElement('div');
    catHeader.style.cssText = 'display:flex;align-items:center;gap:var(--sp-2);margin-bottom:var(--sp-3);padding-bottom:var(--sp-2);border-bottom:1px solid var(--border);';

    const catInfo = document.createElement('div');
    catInfo.style.cssText = 'flex:1;';
    catInfo.innerHTML = `
      <div style="display:flex;align-items:center;gap:var(--sp-2);">
        <span style="font-size:24px;">${category.icon}</span>
        <div>
          <div style="font-weight:var(--fw-semibold);font-size:var(--text-base);color:var(--text-primary);">${category.title}</div>
          <div style="font-size:var(--text-xs);color:var(--text-muted);">${category.description}</div>
        </div>
      </div>
    `;
    catHeader.appendChild(catInfo);

    // Category-level toggle (toggles all commands in category)
    const allEnabled = category.commands.every(cmd => {
      const key = cmd.cmd.replace(/^[!\/]/, '');
      return commandStates[key] !== false;
    });
    const catToggleWrap = document.createElement('div');
    catToggleWrap.style.cssText = 'flex-shrink:0;';
    catToggleWrap.appendChild(Toggle({
      checked: allEnabled,
      onChange: async (val) => {
        const updates = {};
        category.commands.forEach(cmd => {
          const key = cmd.cmd.replace(/^[!\/]/, '');
          updates[key] = val;
          commandStates[key] = val;
        });
        catEl.querySelectorAll('.cmd-toggle-wrap').forEach(wrap => {
          const toggle = wrap.querySelector('input[type="checkbox"]');
          if (toggle) toggle.checked = val;
        });
        catEl.querySelectorAll('.command-row').forEach(row => {
          row.style.opacity = val ? '1' : '0.5';
        });
        try {
          await apiFetch(`/api/groups/${chatId}/commands/states`, {
            method: 'PUT',
            body: updates
          });
          showToast(`${val ? t('enabled', 'Enabled') : t('disabled', 'Disabled')} ${t('all', 'all')} ${category.title.replace(/^[^\s]+\s/, '')} ${t('commands', 'commands')}`, 'success');
        } catch (e) {
          showToast(t('commands_update_failed', 'Failed to update commands'), 'error');
        }
      }
    }));
    catHeader.appendChild(catToggleWrap);
    catEl.appendChild(catHeader);

    // Command list
    const cmdList = document.createElement('div');
    cmdList.className = 'commands-list';
    category.commands.forEach(cmd => {
      cmdList.appendChild(renderCommandRow(cmd, commandStates, chatId));
    });
    catEl.appendChild(cmdList);
    container.appendChild(catEl);
  });
}

function renderSearchResults(container, results, query, commandStates, chatId) {
  container.innerHTML = '';
  if (results.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: var(--sp-8);">
        <div style="font-size: 48px; margin-bottom: var(--sp-4);">🔍</div>
        <div style="color: var(--text-muted);">No commands found for "${escapeHtml(query)}"</div>
      </div>
    `;
    return;
  }
  const header = document.createElement('div');
  header.style.cssText = 'margin-bottom: var(--sp-4); color: var(--text-muted); font-size: var(--text-sm);';
  header.textContent = `Found ${results.reduce((acc, cat) => acc + cat.commands.length, 0)} commands`;
  container.appendChild(header);
  renderCategories(container, results, commandStates, chatId);
}

function renderCommandRow(cmd, commandStates, chatId) {
  const key = cmd.cmd.replace(/^[!\/]/, '');
  const isEnabled = commandStates[key] !== false;

  const row = document.createElement('div');
  row.className = 'command-row';
  row.style.cssText = `display:flex;align-items:center;gap:var(--sp-3);padding:var(--sp-3);background:var(--bg-surface);border-radius:var(--r-lg);margin-bottom:var(--sp-2);border:1px solid var(--border);opacity:${isEnabled ? '1' : '0.5'};transition:opacity 0.2s;`;

  const cmdInfo = document.createElement('div');
  cmdInfo.style.cssText = 'flex:1;min-width:0;';
  const aliases = Object.entries(COMMAND_ALIASES)
    .filter(([, target]) => target === cmd.cmd)
    .map(([alias]) => alias);
  const aliasHtml = aliases.length > 0
    ? `<span style="color:var(--text-muted);font-size:var(--text-xs);margin-left:var(--sp-1);">(${aliases.map(a => escapeHtml(a)).join(', ')})</span>`
    : '';
  cmdInfo.innerHTML = `
    <div style="display:flex;align-items:center;gap:var(--sp-1);flex-wrap:wrap;">
      <code style="background:var(--accent-dim);color:var(--accent);padding:var(--sp-1) var(--sp-2);border-radius:var(--r-md);font-size:var(--text-xs);font-weight:var(--fw-semibold);">${escapeHtml(cmd.cmd)}</code>
      ${cmd.args ? `<span style="color:var(--text-muted);font-size:var(--text-xs);">${escapeHtml(cmd.args)}</span>` : ''}
      ${aliasHtml}
    </div>
    <div style="color:var(--text-secondary);font-size:var(--text-sm);margin-top:2px;">${escapeHtml(cmd.desc)}</div>
  `;
  row.appendChild(cmdInfo);

  // Per-command toggle
  const toggleWrap = document.createElement('div');
  toggleWrap.className = 'cmd-toggle-wrap';
  toggleWrap.style.cssText = 'flex-shrink:0;';
  toggleWrap.appendChild(Toggle({
    checked: isEnabled,
    onChange: async (val) => {
      commandStates[key] = val;
      row.style.opacity = val ? '1' : '0.5';
      try {
        await apiFetch(`/api/groups/${chatId}/commands/states`, {
          method: 'PUT',
          body: { [key]: val }
        });
        showToast(`${cmd.cmd} ${val ? t('enabled', 'enabled') : t('disabled', 'disabled')}`, 'success');
      } catch (e) {
        showToast(t('commands_toggle_failed', 'Failed to toggle command'), 'error');
      }
    }
  }));
  row.appendChild(toggleWrap);

  return row;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
