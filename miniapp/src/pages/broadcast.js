import { Card, showToast, StatCard, EmptyState, Badge, ProgressBar } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

export async function renderBroadcastPage(container) {
    const state = useStore.getState();
    const botInfo = state.userContext?.bot_info;
    const isOwner = state.userContext?.role === 'owner';

    container.innerHTML = `
        <div style="padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto; display: flex; flex-direction: column; gap: var(--sp-4);">
            <div class="page-header">
                <h1 class="text-2xl font-bold">📢 Broadcast</h1>
                <p class="text-sm text-muted">Send mass messages to your users and groups.</p>
            </div>
            
            <div id="broadcast-form-container"></div>
            <div id="broadcast-history-container"></div>
        </div>
    `;

    if (!botInfo) {
        document.getElementById('broadcast-form-container').appendChild(EmptyState({
            icon: '🤖',
            title: 'No Bot Found',
            description: 'You need a bot to use the broadcast feature.'
        }));
        return;
    }

    renderBroadcastForm(document.getElementById('broadcast-form-container'), botInfo, isOwner);
    renderBroadcastHistory(document.getElementById('broadcast-history-container'), botInfo.id);
}

function renderBroadcastForm(container, botInfo, isOwner) {
    const formCard = Card({
        title: 'New Broadcast',
        children: `
            <div style="display: flex; flex-direction: column; gap: var(--sp-4);">
                <div>
                    <label class="block text-xs font-bold text-muted uppercase mb-1">Target Audience</label>
                    <select id="broadcast-target" class="input">
                        <option value="pms">Direct Messages (PMs)</option>
                        <option value="groups">Groups</option>
                        <option value="all">Both (PMs + Groups)</option>
                    </select>
                </div>
                
                <div>
                    <label class="block text-xs font-bold text-muted uppercase mb-1">Message Content</label>
                    <textarea id="broadcast-content" class="input" style="min-height: 120px; resize: vertical;" placeholder="Type your message here... HTML supported."></textarea>
                </div>

                ${isOwner ? `
                <div style="padding: var(--sp-3); background: rgba(var(--accent-rgb), 0.1); border-radius: var(--r-md); border: 1px solid rgba(var(--accent-rgb), 0.2);">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <input type="checkbox" id="broadcast-include-clones">
                        <label for="broadcast-include-clones" class="text-sm">Include all clone bots</label>
                    </div>
                </div>
                ` : ''}

                <button id="send-broadcast-btn" class="btn btn-primary" style="justify-content: center;">
                    🚀 Start Broadcast
                </button>
            </div>
        `
    });
    
    container.appendChild(formCard);

    document.getElementById('send-broadcast-btn').onclick = async () => {
        const targetType = document.getElementById('broadcast-target').value;
        const content = document.getElementById('broadcast-content').value;
        const includeClones = document.getElementById('broadcast-include-clones')?.checked || false;

        if (!content) {
            showToast('Please enter message content', 'error');
            return;
        }

        try {
            document.getElementById('send-broadcast-btn').disabled = true;
            document.getElementById('send-broadcast-btn').textContent = '⌛ Starting...';

            let result;
            if (includeClones) {
                result = await apiFetch('/api/broadcast/global', {
                    method: 'POST',
                    body: JSON.stringify({
                        target_type: targetType,
                        content: content,
                        include_clones: true
                    })
                });
                showToast(`Global broadcast started: ${result.tasks.length} tasks created`, 'success');
            } else {
                result = await apiFetch('/api/broadcast', {
                    method: 'POST',
                    body: JSON.stringify({
                        bot_id: botInfo.id,
                        target_type: targetType,
                        content: content
                    })
                });
                showToast(`Broadcast started for ${result.total_targets} targets`, 'success');
            }

            document.getElementById('broadcast-content').value = '';
            renderBroadcastHistory(document.getElementById('broadcast-history-container'), botInfo.id);
        } catch (e) {
            showToast(e.message || 'Failed to start broadcast', 'error');
        } finally {
            document.getElementById('send-broadcast-btn').disabled = false;
            document.getElementById('send-broadcast-btn').textContent = '🚀 Start Broadcast';
        }
    };
}

async function renderBroadcastHistory(container, botId) {
    container.innerHTML = '<div style="text-align: center; padding: 20px;">Loading history...</div>';
    
    try {
        const history = await apiFetch(`/api/broadcast/bot/${botId}`);
        container.innerHTML = '';
        
        if (history.length === 0) {
            container.appendChild(Card({
                title: 'Broadcast History',
                children: EmptyState({ icon: '📜', title: 'No history yet' })
            }));
            return;
        }

        const listContainer = document.createElement('div');
        listContainer.style.display = 'flex';
        listContainer.style.flexDirection = 'column';

        history.forEach(h => {
            const item = document.createElement('div');
            item.style.cssText = 'padding: var(--sp-3); border-bottom: 1px solid var(--border);';
            
            const header = document.createElement('div');
            header.style.cssText = 'display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;';
            header.innerHTML = `<span class="text-sm font-semibold">${h.target_type.toUpperCase()}</span>`;
            header.appendChild(Badge(h.status, getStatusVariant(h.status)));
            
            item.appendChild(header);
            
            const content = document.createElement('div');
            content.className = 'text-xs text-muted mb-2';
            content.style.cssText = 'white-space: nowrap; overflow: hidden; text-overflow: ellipsis;';
            content.textContent = h.content;
            item.appendChild(content);
            
            const footer = document.createElement('div');
            footer.style.cssText = 'display: flex; justify-content: space-between; align-items: center;';
            footer.innerHTML = `
                <span class="text-xs text-muted">${new Date(h.created_at).toLocaleString()}</span>
                <span class="text-xs font-medium">
                    ✅ ${h.sent_count} / ❌ ${h.failed_count} (Total: ${h.total_targets})
                </span>
            `;
            item.appendChild(footer);
            
            if (h.status === 'running') {
                const progress = ProgressBar(h.sent_count + h.failed_count, h.total_targets);
                progress.style.marginTop = '8px';
                item.appendChild(progress);
                
                // Poll for updates if running
                setTimeout(() => {
                    const activePage = useStore.getState().activePage;
                    if (activePage === 'broadcast') {
                        renderBroadcastHistory(document.getElementById('broadcast-history-container'), botId);
                    }
                }, 5000);
            }
            
            listContainer.appendChild(item);
        });

        container.appendChild(Card({
            title: 'Recent Broadcasts',
            children: listContainer
        }));
    } catch (e) {
        container.innerHTML = `<div style="color: var(--danger); text-align: center; padding: 20px;">Failed to load history: ${e.message}</div>`;
    }
}

function getStatusVariant(status) {
    switch (status) {
        case 'completed': return 'success';
        case 'running': return 'warning';
        case 'failed': return 'danger';
        case 'pending': return 'default';
        case 'cancelled': return 'default';
        default: return 'default';
    }
}
