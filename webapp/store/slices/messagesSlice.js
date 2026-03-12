// store/slices/messagesSlice.js

const MESSAGE_CATALOG = {
  start_private: {
    label: "👋 Welcome Message (DM)",
    description: "Shown when a user starts the bot in private chat.",
    variables: [
      { key: "{first_name}", desc: "User's first name" },
      { key: "{clone_name}", desc: "This bot's name" },
    ],
    requiredVars: [],
  },
  help: {
    label: "📚 Help Message",
    description: "Shown when any user sends /help.",
    variables: [
      { key: "{clone_name}", desc: "This bot's name" },
      { key: "{main_bot}", desc: "Main support bot username" },
    ],
    requiredVars: [],
  },
  member_muted:    { label: "🔇 Mute Notification",      variables: ["{first_name}","{group_name}","{reason}","{duration}"], requiredVars:["{reason}"] },
  member_banned:   { label: "🚫 Ban Notification",        variables: ["{first_name}","{group_name}","{reason}"],              requiredVars:["{reason}"] },
  warn_dm:         { label: "⚠️ Warning Notification",    variables: ["{first_name}","{group_name}","{reason}","{warn_count}","{warn_limit}"], requiredVars:["{warn_count}","{warn_limit}"] },
  channel_gate:    { label: "📢 Channel Gate Message",    variables: ["{first_name}","{channel_name}","{channel_link}"],      requiredVars:["{channel_link}"] },
  boost_gate:      { label: "🚀 Boost Gate Message",      variables: ["{first_name}","{required}","{current}","{remaining}","{link}","{bar}"], requiredVars:["{remaining}","{link}"] },
  boost_unlocked:  { label: "🎉 Boost Unlocked Message",  variables: ["{first_name}","{group_name}"],                         requiredVars:[] },
};

// Sample values for live preview
const SAMPLE_VALUES = {
  first_name: "Alex",
  clone_name: "ExampleBot",
  group_name: "My Awesome Group",
  main_bot: "NexusBot",
  bot_name: "Nexus",
  reason: "Spam",
  duration: "1 hour",
  warn_count: "2",
  warn_limit: "3",
  channel_name: "Our Channel",
  channel_link: "t.me/example",
  required: "5",
  current: "3",
  remaining: "2",
  link: "t.me/+xxxxxxxx",
  bar: "████░░"
};

export const createMessagesSlice = (set, get) => ({
  messages: {},           // { [key]: { body, isCustom } }
  messagesLoading: false,
  messagesSaving: false,
  editingKey: null,       // which message is open in editor
  draftBody: "",          // current editor content

  fetchMessages: async (chatId) => {
    set({ messagesLoading: true });
    try {
      const res = await fetch(`/api/groups/${chatId}/messages`, {
        headers: authHeaders()
      });
      const data = await res.json();
      set({ messages: data, messagesLoading: false });
    } catch (e) {
      console.error("Failed to fetch messages:", e);
      set({ messagesLoading: false });
    }
  },

  openEditor: (key) => {
    const current = get().messages[key]?.body || "";
    set({ editingKey: key, draftBody: current });
  },

  closeEditor: () => set({ editingKey: null, draftBody: "" }),

  setDraft: (text) => set({ draftBody: text }),

  saveMessage: async (chatId, key) => {
    set({ messagesSaving: true });
    const body = get().draftBody.trim();
    try {
      await fetch(`/api/groups/${chatId}/messages/${key}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ body }),
      });
      set(state => ({
        messages: { ...state.messages, [key]: { body, isCustom: true } },
        messagesSaving: false,
        editingKey: null,
      }));
    } catch (e) {
      console.error("Failed to save message:", e);
      set({ messagesSaving: false });
    }
  },

  resetMessage: async (chatId, key) => {
    try {
      await fetch(`/api/groups/${chatId}/messages/${key}`, {
        method: "DELETE", headers: authHeaders()
      });
      set(state => ({
        messages: { ...state.messages, [key]: { body: "", isCustom: false } },
        editingKey: null,
      }));
    } catch (e) {
      console.error("Failed to reset message:", e);
    }
  },

  getPreview: (body, botName = "Nexus") => {
    // Replace variables with sample values
    let preview = body;
    for (const [key, value] of Object.entries(SAMPLE_VALUES)) {
      preview = preview.replace(new RegExp(`{${key}}`, 'g'), value);
    }
    // Always append footer
    preview += `\n\n⚡ Powered by ${botName}`;
    return preview;
  },

  MESSAGE_CATALOG,
  SAMPLE_VALUES,
});

// Helper to get auth headers (assumes authStore exists)
function authHeaders() {
  if (typeof authStore !== 'undefined' && authStore.getState?.().token) {
    return { 'Authorization': `Bearer ${authStore.getState().token}` };
  }
  return {};
}
