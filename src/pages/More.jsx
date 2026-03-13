/**
 * src/pages/More.jsx
 *
 * The "More" tab on mobile — all features not in primary nav.
 * Sections:
 *   1. Log Channel settings
 *   2. Activity Log viewer (with filters + CSV export)
 *   3. Import / Export
 *   4. Inline Mode toggle
 */

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Radio, Download, Upload, RotateCcw, Zap,
  ChevronDown, ChevronUp,
  FileText, RefreshCw
} from "lucide-react"
import { useStore } from "../store"
import { formatDistanceToNow, parseISO } from "date-fns"
import clsx from "clsx"

// ── Section wrapper ────────────────────────────────────────────────────────
function Section({ title, icon: Icon, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="bg-[rgb(var(--surface))] rounded-2xl overflow-hidden
                    border border-[rgb(var(--border))] mb-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full px-4 py-4"
      >
        <div className="flex items-center gap-2">
          <Icon size={16} className="text-accent" />
          <span className="font-semibold text-sm text-[rgb(var(--text))]">
            {title}
          </span>
        </div>
        {open
          ? <ChevronUp size={16} className="text-[rgb(var(--text-muted))]" />
          : <ChevronDown size={16} className="text-[rgb(var(--text-muted))]" />
        }
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-[rgb(var(--border))]"
          >
            <div className="px-4 pb-4 pt-4">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Toggle row ─────────────────────────────────────────────────────────────
function ToggleRow({ label, desc, value, onChange }) {
  return (
    <div className="flex items-center justify-between py-2.5
                    border-b border-[rgb(var(--border))] last:border-0">
      <div>
        <p className="text-sm text-[rgb(var(--text))]">{label}</p>
        {desc && (
          <p className="text-xs text-[rgb(var(--text-muted))] mt-0.5">{desc}</p>
        )}
      </div>
      <button
        onClick={() => onChange(!value)}
        className={clsx(
          "w-11 h-6 rounded-full transition-colors relative flex-shrink-0",
          value ? "bg-accent" : "bg-[rgb(var(--surface-3))]"
        )}
      >
        <motion.div
          animate={{ x: value ? 20 : 2 }}
          transition={{ type: "spring", stiffness: 500, damping: 30 }}
          className="absolute top-1 w-4 h-4 bg-white rounded-full shadow"
        />
      </button>
    </div>
  )
}

// ── Log category toggles ───────────────────────────────────────────────────
const LOG_CATEGORIES = [
  { key: "ban",           label: "🚫 Bans"             },
  { key: "mute",          label: "🔇 Mutes"            },
  { key: "warn",          label: "⚠️ Warnings"         },
  { key: "kick",          label: "👢 Kicks"             },
  { key: "delete",        label: "🗑 Message Deletes"   },
  { key: "join",          label: "👋 Joins"             },
  { key: "leave",         label: "🚪 Leaves"            },
  { key: "raid",          label: "🚨 Raids"             },
  { key: "captcha",       label: "🤖 CAPTCHA Events"   },
  { key: "filter",        label: "🔍 Filter Triggers"  },
  { key: "blocklist",     label: "🚫 Blocklist Hits"   },
  { key: "settings",      label: "⚙️ Settings Changes" },
  { key: "pin",           label: "📌 Pins"              },
  { key: "report",        label: "🚨 Reports"           },
  { key: "note",          label: "📝 Note Access"       },
  { key: "schedule",      label: "📅 Scheduled Sends"  },
  { key: "password",      label: "🔐 Password Events"  },
  { key: "import_export", label: "📥 Import/Export"    },
]

// ── Activity event row ─────────────────────────────────────────────────────
const EVENT_ICONS = {
  ban:            "🚫", mute:       "🔇", warn:    "⚠️",
  kick:           "👢", delete:     "🗑", join:    "👋",
  leave:          "🚪", raid:       "🚨", filter:  "🔍",
  captcha_pass:   "✅", captcha_fail:"❌", pin:    "📌",
  blocklist:      "🚫", settings_change:"⚙️", report:"🚨",
  import:         "📥", export:     "📤", reset:   "🔄",
  inline_query:   "⚡", antiraid_start:"🛡",
}

function EventRow({ event }) {
  const icon = EVENT_ICONS[event.event_type] || "📋"
  return (
    <div className="flex items-start gap-3 py-2.5
                    border-b border-[rgb(var(--border))] last:border-0">
      <span className="text-base flex-shrink-0">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-semibold text-[rgb(var(--text))]
                           uppercase tracking-wide">
            {event.event_type.replace(/_/g, " ")}
          </span>
          {event.target_name && (
            <span className="text-xs text-[rgb(var(--text-muted))]">
              → {event.target_name}
            </span>
          )}
        </div>
        {event.actor_name && (
          <p className="text-xs text-[rgb(var(--text-muted))]">
            By: {event.actor_name}
          </p>
        )}
        <p className="text-xs text-[rgb(var(--text-subtle))] mt-0.5">
          {formatDistanceToNow(parseISO(event.created_at), { addSuffix: true })}
        </p>
      </div>
    </div>
  )
}

// ── Activity log viewer ────────────────────────────────────────────────────
function ActivityLogViewer({ chatId }) {
  const [events,      setEvents]      = useState([])
  const [total,       setTotal]       = useState(0)
  const [loading,     setLoading]     = useState(true)
  const [typeFilter,  setTypeFilter]  = useState("all")
  const [days,        setDays]        = useState(7)
  const { showToast } = useStore()

  const load = async (reset = false) => {
    setLoading(true)
    const params = new URLSearchParams({
      limit: 50,
      days,
      ...(typeFilter !== "all" && { type: typeFilter }),
    })
    try {
      const res  = await fetch(
        `/api/groups/${chatId}/log/activity?${params}`,
        authHeaders()
      )
      const data = await res.json()
      setEvents(reset ? data.rows : [...events, ...data.rows])
      setTotal(data.total)
    } catch (e) {
      showToast("Failed to load activity log", "error")
    }
    setLoading(false)
  }

  useEffect(() => { load(true) }, [chatId, typeFilter, days])

  const exportCSV = () => {
    const params = new URLSearchParams({
      days,
      ...(typeFilter !== "all" && { type: typeFilter })
    })
    window.open(
      `/api/groups/${chatId}/log/activity/export?${params}`,
      "_blank"
    )
  }

  return (
    <div>
      <div className="flex gap-2 mb-3 flex-wrap">
        <select
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
          className="flex-1 bg-[rgb(var(--surface-2))] rounded-xl px-3 py-2
                     text-sm text-[rgb(var(--text))]
                     border border-[rgb(var(--border))]"
        >
          <option value="all">All events</option>
          {["ban","mute","warn","kick","delete","join","leave",
            "raid","captcha_pass","captcha_fail","filter",
            "blocklist","settings_change","pin","report",
            "import","export","reset"].map(t => (
            <option key={t} value={t}>{t.replace(/_/g," ")}</option>
          ))}
        </select>
        <select
          value={days}
          onChange={e => setDays(parseInt(e.target.value))}
          className="bg-[rgb(var(--surface-2))] rounded-xl px-3 py-2
                     text-sm text-[rgb(var(--text))]
                     border border-[rgb(var(--border))]"
        >
          {[1,7,14,30,90].map(d => (
            <option key={d} value={d}>Last {d}d</option>
          ))}
        </select>
        <button
          onClick={exportCSV}
          className="px-3 py-2 bg-[rgb(var(--surface-2))]
                     text-[rgb(var(--text-muted))] rounded-xl
                     border border-[rgb(var(--border))] text-xs
                     flex items-center gap-1.5 hover:text-accent
                     transition-colors"
        >
          <Download size={12} />
          CSV
        </button>
        <button
          onClick={() => load(true)}
          className="px-3 py-2 bg-[rgb(var(--surface-2))]
                     text-[rgb(var(--text-muted))] rounded-xl
                     border border-[rgb(var(--border))]
                     hover:text-accent transition-colors"
        >
          <RefreshCw size={14} />
        </button>
      </div>

      <p className="text-xs text-[rgb(var(--text-muted))] mb-2">
        {total.toLocaleString()} events found
      </p>

      <div className="max-h-96 overflow-y-auto">
        {loading && events.length === 0 ? (
          <div className="flex justify-center py-8">
            <div className="w-6 h-6 border-2 border-accent
                            border-t-transparent rounded-full animate-spin" />
          </div>
        ) : events.length === 0 ? (
          <p className="text-sm text-center text-[rgb(var(--text-muted))]
                        py-6">
            No events found
          </p>
        ) : (
          <>
            {events.map(e => <EventRow key={e.id} event={e} />)}
            {events.length < total && (
              <button
                onClick={() => load(false)}
                className="w-full py-2 text-xs text-accent
                           hover:opacity-80 mt-2"
              >
                Load more ({total - events.length} remaining)
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────
export default function More() {
  const { activeGroupId, showToast } = useStore()
  const chatId = activeGroupId

  const [logSettings,  setLogSettings]  = useState(null)
  const [loading,      setLoading]      = useState(true)

  useEffect(() => {
    if (!chatId) return
    fetch(`/api/groups/${chatId}/log/settings`, authHeaders())
      .then(r => r.json())
      .then(data => { setLogSettings(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [chatId])

  const saveLogSettings = async (updates) => {
    const next = { ...logSettings, ...updates }
    setLogSettings(next)
    await fetch(`/api/groups/${chatId}/log/settings`, {
      method:  "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body:    JSON.stringify(updates),
    })
    showToast("Saved", "success")
  }

  const toggleCategory = (key, val) => {
    saveLogSettings({
      log_categories: { ...logSettings?.log_categories, [key]: val }
    })
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-accent border-t-transparent
                      rounded-full animate-spin" />
    </div>
  )

  return (
    <div className="p-4 max-w-2xl mx-auto pb-24">

      {/* Log Channel */}
      <Section title="Log Channel" icon={Radio} defaultOpen>
        <div className="mb-4">
          <label className="text-xs text-[rgb(var(--text-muted))] mb-1 block">
            Log Channel ID
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="-100123456789"
              defaultValue={logSettings?.log_channel_id || ""}
              onBlur={e => saveLogSettings({
                log_channel_id: e.target.value
                  ? parseInt(e.target.value) : null
              })}
              className="flex-1 bg-[rgb(var(--surface-2))] rounded-xl px-3 py-2
                         text-sm font-mono text-[rgb(var(--text))]
                         border border-[rgb(var(--border))]
                         placeholder-[rgb(var(--text-subtle))]"
            />
          </div>
          <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
            Bot must be admin in the log channel.
            Use /setlog in group for easier setup.
          </p>
        </div>

        <ToggleRow
          label="Include message preview"
          desc="Show deleted message content in delete logs"
          value={!!logSettings?.log_include_preview}
          onChange={v => saveLogSettings({ log_include_preview: v })}
        />
        <ToggleRow
          label="Include user IDs"
          desc="Show Telegram user IDs in log messages"
          value={!!logSettings?.log_include_userid}
          onChange={v => saveLogSettings({ log_include_userid: v })}
        />

        <div className="mt-4">
          <p className="text-xs font-semibold text-[rgb(var(--text-muted))]
                        uppercase tracking-wider mb-3">
            Log Categories
          </p>
          <div className="space-y-0.5">
            {LOG_CATEGORIES.map(({ key, label }) => (
              <div key={key}
                   className="flex items-center justify-between py-2
                              border-b border-[rgb(var(--border))] last:border-0">
                <span className="text-sm text-[rgb(var(--text))]">{label}</span>
                <button
                  onClick={() => toggleCategory(
                    key,
                    !logSettings?.log_categories?.[key]
                  )}
                  className={clsx(
                    "w-10 h-5 rounded-full transition-colors relative",
                    logSettings?.log_categories?.[key] !== false
                      ? "bg-accent"
                      : "bg-[rgb(var(--surface-3))]"
                  )}
                >
                  <motion.div
                    animate={{
                      x: logSettings?.log_categories?.[key] !== false
                        ? 20 : 2
                    }}
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                    className="absolute top-0.5 w-4 h-4 bg-white
                               rounded-full shadow"
                  />
                </button>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* Activity log */}
      <Section title="Activity Log" icon={FileText}>
        {chatId && <ActivityLogViewer chatId={chatId} />}
      </Section>

      {/* Import / Export */}
      <Section title="Import / Export" icon={Download}>
        <p className="text-xs text-[rgb(var(--text-muted))] mb-4">
          Export your group settings as JSON. Import in another group
          to copy everything instantly.
        </p>

        <div className="space-y-2">
          <button
            onClick={() => {
              window.Telegram?.WebApp?.sendData(
                JSON.stringify({ action: "export" })
              )
              showToast("Use /export in your group chat", "info")
            }}
            className="flex items-center gap-3 w-full p-3
                       bg-[rgb(var(--surface-2))] rounded-xl
                       border border-[rgb(var(--border))]
                       hover:border-accent/30 transition-colors"
          >
            <Upload size={18} className="text-accent" />
            <div className="text-left">
              <p className="text-sm font-medium text-[rgb(var(--text))]">
                Export Settings
              </p>
              <p className="text-xs text-[rgb(var(--text-muted))]">
                Download as JSON file — use /export in group
              </p>
            </div>
          </button>

          <button
            onClick={() => {
              window.Telegram?.WebApp?.sendData(
                JSON.stringify({ action: "import_prompt" })
              )
              showToast("Upload JSON file and use /import in group", "info")
            }}
            className="flex items-center gap-3 w-full p-3
                       bg-[rgb(var(--surface-2))] rounded-xl
                       border border-[rgb(var(--border))]
                       hover:border-accent/30 transition-colors"
          >
            <Download size={18} className="text-cyan-400" />
            <div className="text-left">
              <p className="text-sm font-medium text-[rgb(var(--text))]">
                Import Settings
              </p>
              <p className="text-xs text-[rgb(var(--text-muted))]">
                Upload JSON + use /import in group
              </p>
            </div>
          </button>

          <button
            onClick={() => {
              if (!window.confirm(
                "Reset ALL settings? This cannot be undone."
              )) return
              showToast("Use /reset in your group to confirm", "warning")
            }}
            className="flex items-center gap-3 w-full p-3
                       bg-red-500/5 rounded-xl
                       border border-red-500/20
                       hover:border-red-500/40 transition-colors"
          >
            <RotateCcw size={18} className="text-red-400" />
            <div className="text-left">
              <p className="text-sm font-medium text-red-400">
                Reset Settings
              </p>
              <p className="text-xs text-red-400/60">
                Use /reset in group — cannot be undone
              </p>
            </div>
          </button>
        </div>
      </Section>

      {/* Inline mode */}
      <Section title="Inline Mode" icon={Zap}>
        <ToggleRow
          label="Enable inline mode"
          desc="Allow @botname queries from any chat"
          value={!!logSettings?.inline_mode_enabled}
          onChange={v => saveLogSettings({ inline_mode_enabled: v })}
        />
        <div className="mt-3 p-3 bg-[rgb(var(--surface-2))] rounded-xl
                        border border-[rgb(var(--border))]">
          <p className="text-xs font-semibold text-[rgb(var(--text))]
                        mb-2">
            Available inline commands:
          </p>
          {[
            { cmd: "@bot note rules", desc: "Get the #rules note" },
            { cmd: "@bot notes",      desc: "List all notes" },
            { cmd: "@bot stats",      desc: "Group statistics card" },
            { cmd: "@bot time",       desc: "Current group time" },
          ].map(({ cmd, desc }) => (
            <div key={cmd} className="flex items-center gap-2 py-1.5">
              <code className="text-xs text-accent font-mono">{cmd}</code>
              <span className="text-xs text-[rgb(var(--text-muted))]">
                — {desc}
              </span>
            </div>
          ))}
        </div>
      </Section>
    </div>
  )
}
