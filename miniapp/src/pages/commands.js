/**
 * miniapp/src/pages/commands.js
 *
 * Commands reference page for the Mini App.
 * Shows all available bot commands organized by category.
 *
 * Dependencies:
 *   - lib/components.js (Card, EmptyState)
 *   - store/index.js (useStore)
 */

import { Card, EmptyState } from '../lib/components.js';
import { useStore } from '../store/index.js';

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
      { cmd: '/warn', args: '<reason>', desc: 'Warn a user (reply to message)' },
      { cmd: '/unwarn', args: '', desc: 'Remove a warning from user' },
      { cmd: '/warns', args: '', desc: 'Show warnings for a user' },
      { cmd: '/mute', args: '<duration>', desc: 'Mute a user' },
      { cmd: '/unmute', args: '', desc: 'Unmute a user' },
      { cmd: '/ban', args: '<reason>', desc: 'Ban a user from group' },
      { cmd: '/unban', args: '', desc: 'Unban a user' },
      { cmd: '/kick', args: '<reason>', desc: 'Kick a user from group' },
      { cmd: '/purge', args: '<count>', desc: 'Delete recent messages (max 100)' },
      { cmd: '/pin', args: '', desc: 'Pin a message (reply to message)' },
      { cmd: '/unpin', args: '', desc: 'Unpin the pinned message' },
    ]
  },
  {
    id: 'security',
    title: '🔒 Security',
    description: 'Anti-spam and security features',
    icon: '🔒',
    commands: [
      { cmd: '!antispam', args: '', desc: 'Toggle anti-spam' },
      { cmd: '!antiflood', args: '', desc: 'Toggle anti-flood' },
      { cmd: '!antilink', args: '', desc: 'Toggle anti-link' },
      { cmd: '!captcha', args: '', desc: 'Toggle CAPTCHA verification' },
      { cmd: '!antiraid', args: '', desc: 'Toggle anti-raid mode' },
      { cmd: '/slowmode', args: '<seconds>', desc: 'Set slow mode (0-300)' },
      { cmd: '/setflood', args: '<number>', desc: 'Set flood message limit' },
      { cmd: '/addfilter', args: '<word>', desc: 'Add word filter' },
      { cmd: '/delfilter', args: '<word>', desc: 'Remove word filter' },
    ]
  },
  {
    id: 'greetings',
    title: '👋 Greetings',
    description: 'Welcome and goodbye messages',
    icon: '👋',
    commands: [
      { cmd: '/setwelcome', args: '<message>', desc: 'Set welcome message' },
      { cmd: '/setgoodbye', args: '<message>', desc: 'Set goodbye message' },
      { cmd: '/setrules', args: '<rules>', desc: 'Set group rules' },
      { cmd: '/welcome', args: '', desc: 'Preview welcome message' },
      { cmd: '/goodbye', args: '', desc: 'Preview goodbye message' },
      { cmd: '/rules', args: '', desc: 'Show group rules' },
      { cmd: '/resetwelcome', args: '', desc: 'Reset welcome to default' },
      { cmd: '/resetgoodbye', args: '', desc: 'Reset goodbye to default' },
    ]
  },
  {
    id: 'music',
    title: '🎵 Music',
    description: 'Music playback commands',
    icon: '🎵',
    commands: [
      { cmd: '/play', args: '<url/query>', desc: 'Play music or add to queue' },
      { cmd: '/playnow', args: '<url>', desc: 'Play immediately, skip queue' },
      { cmd: '/pause', args: '', desc: 'Pause playback' },
      { cmd: '/resume', args: '', desc: 'Resume playback' },
      { cmd: '/skip', args: '', desc: 'Skip current track' },
      { cmd: '/stop', args: '', desc: 'Stop and clear queue' },
      { cmd: '/queue', args: '', desc: 'Show music queue' },
      { cmd: '/volume', args: '<0-200>', desc: 'Set volume level' },
      { cmd: '/loop', args: '', desc: 'Toggle loop mode' },
      { cmd: '/musicmode', args: 'all|admins', desc: 'Set who can use music' },
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
      { cmd: '/poll', args: '<question>', desc: 'Create a poll' },
      { cmd: '/dice', args: '', desc: 'Roll a dice' },
      { cmd: '/coin', args: '', desc: 'Flip a coin' },
      { cmd: '/choose', args: 'opt1|opt2', desc: 'Randomly choose between options' },
      { cmd: '/8ball', args: '<question>', desc: 'Magic 8-ball' },
      { cmd: '/roll', args: '<max>', desc: 'Roll random number' },
      { cmd: '/joke', args: '', desc: 'Get a random joke' },
      { cmd: '/quote', args: '', desc: 'Get an inspirational quote' },
      { cmd: '/roast', args: '', desc: 'Playful roast (reply to someone)' },
      { cmd: '/compliment', args: '', desc: 'Give a compliment' },
      { cmd: '/calc', args: '<expression>', desc: 'Simple calculator' },
    ]
  },
  {
    id: 'admin',
    title: '⚡ Admin Tools',
    description: 'Advanced administration tools',
    icon: '⚡',
    commands: [
      { cmd: '/announce', args: '<message>', desc: 'Send announcement' },
      { cmd: '/pinmessage', args: '<text>', desc: 'Pin custom message' },
      { cmd: '/admininfo', args: '', desc: 'Show detailed group info' },
      { cmd: '/exportsettings', args: '', desc: 'Export settings as JSON' },
      { cmd: '/importsettings', args: '<json>', desc: 'Import settings' },
      { cmd: '/filters', args: '', desc: 'List word filters' },
    ]
  },
  {
    id: 'utilities',
    title: '🔧 Utilities',
    description: 'General utility commands',
    icon: '🔧',
    commands: [
      { cmd: '/panel', args: '', desc: 'Open mini app panel' },
      { cmd: '/help', args: '', desc: 'Show help message' },
      { cmd: '/id', args: '', desc: 'Get chat and user IDs' },
      { cmd: '/info', args: '', desc: 'Show group information' },
      { cmd: '/admins', args: '', desc: 'List group admins' },
      { cmd: '/stats', args: '', desc: 'Show group statistics' },
      { cmd: '/report', args: '', desc: 'Report a message' },
    ]
  }
];

/**
 * Render the Commands reference page
 * @param {HTMLElement} container - Container element to render into
 */
export function renderCommandsPage(container) {
  const chatId = store.getState().activeChatId;
  
  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({
      icon: '👆',
      title: 'Select a group',
      description: 'Choose a group to see available commands'
    }));
    return;
  }

  // Search box
  const searchContainer = document.createElement('div');
  searchContainer.style.cssText = 'margin-bottom: var(--sp-4);';
  searchContainer.innerHTML = `
    <input 
      type="text" 
      id="cmd-search" 
      placeholder="🔍 Search commands..."
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

  // Render all categories initially
  renderCategories(contentContainer, COMMAND_CATEGORIES);

  // Add search functionality
  const searchInput = searchContainer.querySelector('#cmd-search');
  searchInput.addEventListener('input', (e) => {
    const query = e.target.value.toLowerCase();
    if (query) {
      const filtered = filterCommands(query);
      renderSearchResults(contentContainer, filtered, query);
    } else {
      renderCategories(contentContainer, COMMAND_CATEGORIES);
    }
  });
}

function filterCommands(query) {
  const results = [];
  
  COMMAND_CATEGORIES.forEach(cat => {
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

function renderCategories(container, categories) {
  container.innerHTML = '';
  
  categories.forEach(category => {
    const categoryHtml = `
      <div class="command-category" style="margin-bottom: var(--sp-4);">
        <div style="
          display: flex;
          align-items: center;
          gap: var(--sp-2);
          margin-bottom: var(--sp-3);
          padding-bottom: var(--sp-2);
          border-bottom: 1px solid var(--border);
        ">
          <span style="font-size: 24px;">${category.icon}</span>
          <div>
            <div style="font-weight: var(--fw-semibold); font-size: var(--text-base); color: var(--text-primary);">
              ${category.title}
            </div>
            <div style="font-size: var(--text-xs); color: var(--text-muted);">
              ${category.description}
            </div>
          </div>
        </div>
        <div class="commands-list">
          ${category.commands.map(cmd => renderCommandRow(cmd)).join('')}
        </div>
      </div>
    `;
    
    const div = document.createElement('div');
    div.innerHTML = categoryHtml;
    container.appendChild(div.firstElementChild);
  });
}

function renderSearchResults(container, results, query) {
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
  
  renderCategories(container, results);
}

function renderCommandRow(cmd) {
  return `
    <div class="command-row" style="
      display: flex;
      align-items: flex-start;
      gap: var(--sp-3);
      padding: var(--sp-3);
      background: var(--bg-surface);
      border-radius: var(--r-lg);
      margin-bottom: var(--sp-2);
      border: 1px solid var(--border);
    ">
      <div style="flex-shrink: 0;">
        <code style="
          background: var(--accent-dim);
          color: var(--accent);
          padding: var(--sp-1) var(--sp-2);
          border-radius: var(--r-md);
          font-size: var(--text-xs);
          font-weight: var(--fw-semibold);
        ">${escapeHtml(cmd.cmd)}</code>
        ${cmd.args ? `<span style="color: var(--text-muted); font-size: var(--text-xs); margin-left: var(--sp-1);">${escapeHtml(cmd.args)}</span>` : ''}
      </div>
      <div style="color: var(--text-secondary); font-size: var(--text-sm);">
        ${escapeHtml(cmd.desc)}
      </div>
    </div>
  `;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
