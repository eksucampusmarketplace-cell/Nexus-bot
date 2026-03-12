/**
 * miniapp/store/index.js
 *
 * Zustand store for the Mini App.
 * Manages global state with vanilla JS.
 *
 * Usage:
 *   import { useStore } from './store/index.js';
 *   const state = useStore.getState();
 *   useStore.subscribe(state => console.log(state));
 *   useStore.setState({ key: value });
 */

// Use global zustand if available from CDN
const zustandGlobal = typeof window !== 'undefined' ? window.zustand : null;
const createStore = zustandGlobal?.createStore || zustandGlobal?.create;

export const useStore = createStore((set, get) => ({
  // ── User & Auth ─────────────────────────────────────────
  initData: '',
  userContext: null,
  
  // ── Active Group ───────────────────────────────────────────
  activeChatId: null,
  activeGroup: null,
  setActiveChatId: (chatId) => set({ activeChatId: chatId }),
  setActiveGroup: (group) => set({ activeGroup: group }),
  
  // ── Navigation ──────────────────────────────────────────────
  activePage: 'dashboard',
  setActivePage: (page) => set({ activePage: page }),
  
  // ── Settings ────────────────────────────────────────────────
  settings: {},
  setSettings: (settings) => set({ settings }),
  updateSetting: (key, value) => set(state => ({ 
    settings: { ...state.settings, [key]: value } 
  })),
  
  // ── Members ────────────────────────────────────────────────
  members: [],
  setMembers: (members) => set({ members }),
  updateMember: (memberId, updates) => set(state => ({
    members: state.members.map(m => 
      m.id === memberId ? { ...m, ...updates } : m
    )
  })),
  removeMember: (memberId) => set(state => ({
    members: state.members.filter(m => m.id !== memberId)
  })),
  
  // ── Logs ───────────────────────────────────────────────────
  logs: [],
  setLogs: (logs) => set({ logs }),
  addLog: (log) => set(state => ({
    logs: [log, ...state.logs].slice(0, 100)
  })),
  
  // ── Stats ───────────────────────────────────────────────────
  stats: {},
  setStats: (stats) => set({ stats }),
  
  // ── Modules ────────────────────────────────────────────────
  modules: {},
  setModules: (modules) => set({ modules }),
  toggleModule: (moduleName, enabled) => set(state => ({
    modules: { ...state.modules, [moduleName]: enabled }
  })),
  
  // ── Automod Rules ───────────────────────────────────────────
  automodRules: [],
  setAutomodRules: (rules) => set({ automodRules: rules }),
  addAutomodRule: (rule) => set(state => ({
    automodRules: [...state.automodRules, rule]
  })),
  updateAutomodRule: (ruleId, updates) => set(state => ({
    automodRules: state.automodRules.map(r =>
      r.id === ruleId ? { ...r, ...updates } : r
    )
  })),
  removeAutomodRule: (ruleId) => set(state => ({
    automodRules: state.automodRules.filter(r => r.id !== ruleId)
  })),
  
  // ── Bulk Selection ───────────────────────────────────────────
  selectedMembers: new Set(),
  toggleMemberSelection: (memberId) => set(state => {
    const newSet = new Set(state.selectedMembers);
    if (newSet.has(memberId)) {
      newSet.delete(memberId);
    } else {
      newSet.add(memberId);
    }
    return { selectedMembers: newSet };
  }),
  clearMemberSelection: () => set({ selectedMembers: new Set() }),
  
  // ── UI State ──────────────────────────────────────────────
  isLoading: false,
  error: null,
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  
  // ── SSE Connection ─────────────────────────────────────────
  sseConnected: false,
  setSseConnected: (connected) => set({ sseConnected: connected }),
}));
