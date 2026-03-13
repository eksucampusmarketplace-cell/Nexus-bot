
import { Card, Badge, EmptyState, showToast } from '../../lib/components.js';
import { apiFetch } from '../../lib/api.js';

export async function renderBotsPage(container) {
  container.innerHTML = '<div class="loading-screen">⏳ Loading your bots...</div>';

  try {
    const bots = await apiFetch('/api/bots');
    container.innerHTML = '';

    if (!bots || bots.length === 0) {
      container.appendChild(EmptyState({
        icon: '🤖',
        title: 'No bots found',
        description: 'You haven\'t created any clone bots yet. Create one via the primary bot!'
      }));
      return;
    }

    const grid = document.createElement('div');
    grid.style.cssText = 'display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--sp-4);';
    
    bots.forEach(bot => {
      const botCard = Card({
        title: bot.display_name,
        subtitle: `@${bot.username}`,
        children: `
          <div style="margin-top: var(--sp-2); display: flex; flex-direction: column; gap: var(--sp-2);">
            <div style="display: flex; justify-content: space-between; font-size: var(--text-sm);">
              <span style="color: var(--text-muted);">Status:</span>
              <span>${Badge(bot.status, bot.status === 'active' ? 'success' : 'danger').outerHTML}</span>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: var(--text-sm);">
              <span style="color: var(--text-muted);">Groups:</span>
              <span>${bot.group_limit || 1} limit</span>
            </div>
          </div>
        `,
        actions: null
      });
      grid.appendChild(botCard);
    });

    container.appendChild(grid);

  } catch (error) {
    console.error('[BotsPage] Error:', error);
    container.innerHTML = '';
    container.appendChild(EmptyState({
      icon: '⚠️',
      title: 'Failed to load bots',
      description: error.message
    }));
  }
}
