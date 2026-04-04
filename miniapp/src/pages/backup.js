/**
 * miniapp/src/pages/backup.js
 * Task 5 of 12 — Backup page
 * Extracted from index.html renderBackupPage()
 */

import { Card, EmptyState, showToast } from '../../lib/components.js?v=1.6.0';
import { apiFetch } from '../../lib/api.js?v=1.6.0';
import { useStore } from '../../store/index.js?v=1.6.0';

const store = useStore;
const getState = store.getState;

export async function renderBackupPage(container) {
  const state = getState();
  const chatId = state.activeChatId;

  container.innerHTML = '';
  container.style.cssText = 'padding: var(--sp-4); max-width: var(--content-max); margin: 0 auto;';

  if (!chatId) {
    container.appendChild(EmptyState({ icon: '💾', title: 'Select a group', description: 'Choose a group to backup/restore settings.' }));
    return;
  }

  const card = Card({
    title: '💾 Backup & Restore',
    subtitle: 'Export and import group configuration',
    children: `
      <div style="display:flex;flex-direction:column;gap:var(--sp-4);">
        <div>
          <h4 style="margin:0 0 var(--sp-2);font-size:14px;">Export Backup</h4>
          <p style="font-size:13px;color:var(--text-muted);margin:0 0 var(--sp-3);">Download all group settings as a JSON file.</p>
          <button id="export-backup-btn" class="btn btn-primary">📥 Download Backup</button>
        </div>
        <div style="border-top:1px solid var(--border);padding-top:var(--sp-4);">
          <h4 style="margin:0 0 var(--sp-2);font-size:14px;">Restore from Backup</h4>
          <p style="font-size:13px;color:var(--text-muted);margin:0 0 var(--sp-3);">Upload a backup JSON file to restore settings.</p>
          <div style="display:flex;gap:var(--sp-2);">
            <input type="file" id="backup-file" accept=".json" style="flex:1;" />
            <button class="btn btn-secondary" onclick="restoreBackup()">📤 Restore</button>
          </div>
        </div>
      </div>
    `
  });
  container.appendChild(card);

  setTimeout(() => {
    const exportBtn = document.getElementById('export-backup-btn');
    if (exportBtn) {
      exportBtn.addEventListener('click', async () => {
        exportBtn.textContent = '⏳ Preparing...';
        exportBtn.disabled = true;
        try {
          const data = await apiFetch(`/api/groups/${chatId}/backup`);
          const json = JSON.stringify(data, null, 2);
          const blob = new Blob([json], { type: 'application/json' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `nexus-backup-${chatId}-${Date.now()}.json`;
          a.click();
          URL.revokeObjectURL(url);
          showToast('Backup downloaded!', 'success');
        } catch (e) {
          showToast('Failed to export: ' + e.message, 'error');
        } finally {
          exportBtn.textContent = '📥 Download Backup';
          exportBtn.disabled = false;
        }
      });
    }
  }, 100);

  window.restoreBackup = async () => {
    const fileInput = document.getElementById('backup-file');
    if (!fileInput.files || !fileInput.files[0]) {
      showToast('Please select a file', 'error');
      return;
    }
    try {
      const text = await fileInput.files[0].text();
      const data = JSON.parse(text);
      await apiFetch(`/api/groups/${chatId}/restore`, {
        method: 'POST',
        body: data
      });
      showToast('Backup restored successfully!', 'success');
    } catch (err) {
      showToast(err.message || 'Failed to restore', 'error');
    }
  };
}
