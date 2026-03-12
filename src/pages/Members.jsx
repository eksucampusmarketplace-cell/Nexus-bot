/**
 * src/pages/Members.jsx
 */

import { useState, useEffect, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Shield, Users, CheckCircle, XCircle, Zap,
  UserCheck, UserX, Ban, VolumeX,
  ChevronDown, ChevronUp, RefreshCw, AlertTriangle
} from "lucide-react"
import { useStore } from "../store"
import { formatDistanceToNow } from "date-fns"
import clsx from "clsx"

// ── Helper for auth headers ───────────────────────────────────────────────
const authHeaders = () => {
    const initData = window.Telegram?.WebApp?.initData || "";
    return {
        "X-Telegram-Init-Data": initData
    };
};

// ── Section wrapper (reuse from AutoMod) ──────────────────────────────────
function Section({ title, icon: Icon, badge, children, defaultOpen = false }) {
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
          {badge != null && (
            <span className="px-2 py-0.5 bg-accent/10 text-accent text-xs
                             rounded-full font-bold">
              {badge}
            </span>
          )}
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

// ── Toggle ─────────────────────────────────────────────────────────────────
function Toggle({ value, onChange }) {
  return (
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
  )
}

// ── Event feed item ────────────────────────────────────────────────────────
const EVENT_META = {
  join:          { icon: "👋", color: "text-green-400",  bg: "bg-green-400/10"  },
  leave:         { icon: "🚪", color: "text-slate-400",  bg: "bg-slate-400/10"  },
  raid_join:     { icon: "🚨", color: "text-red-400",    bg: "bg-red-400/10"    },
  captcha_pass:  { icon: "✅", color: "text-emerald-400",bg: "bg-emerald-400/10"},
  captcha_fail:  { icon: "❌", color: "text-red-400",    bg: "bg-red-400/10"    },
  ban:           { icon: "🚫", color: "text-red-500",    bg: "bg-red-500/10"    },
  kick:          { icon: "👢", color: "text-orange-400", bg: "bg-orange-400/10" },
  approve:       { icon: "✅", color: "text-cyan-400",   bg: "bg-cyan-400/10"   },
}

function EventItem({ event }) {
  const meta = EVENT_META[event.event_type] || EVENT_META.join
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex items-center gap-3 py-2.5 border-b
                 border-[rgb(var(--border))] last:border-0"
    >
      <div className={clsx(
        "w-7 h-7 rounded-lg flex items-center justify-center text-sm",
        meta.bg
      )}>
        {meta.icon}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-[rgb(var(--text))] truncate">
          {event.full_name || event.username || event.user_id}
        </p>
        <p className="text-xs text-[rgb(var(--text-muted))]">
          {event.event_type.replace("_", " ")} ·{" "}
          {formatDistanceToNow(new Date(event.created_at), { addSuffix: true })}
        </p>
      </div>
      {event.username && (
        <span className="text-xs text-[rgb(var(--text-subtle))]">
          @{event.username}
        </span>
      )}
    </motion.div>
  )
}

// ── Bulk action bar ────────────────────────────────────────────────────────
function BulkActionBar({ selected, onAction, onClear }) {
  if (selected.length === 0) return null
  return (
    <motion.div
      initial={{ y: 80 }}
      animate={{ y: 0 }}
      exit={{ y: 80 }}
      className="fixed bottom-20 md:bottom-6 left-4 right-4 z-30
                 bg-[rgb(var(--surface))] border border-[rgb(var(--border))]
                 rounded-2xl p-3 shadow-2xl flex items-center gap-2"
    >
      <span className="text-sm font-semibold text-[rgb(var(--text))] flex-1">
        {selected.length} selected
      </span>
      <button
        onClick={() => onAction("approve")}
        className="px-3 py-2 bg-green-500/10 text-green-400 rounded-xl
                   text-xs font-bold border border-green-500/20"
      >
        <UserCheck size={14} className="inline mr-1" />
        Approve
      </button>
      <button
        onClick={() => onAction("mute")}
        className="px-3 py-2 bg-amber-500/10 text-amber-400 rounded-xl
                   text-xs font-bold border border-amber-500/20"
      >
        <VolumeX size={14} className="inline mr-1" />
        Mute
      </button>
      <button
        onClick={() => onAction("ban")}
        className="px-3 py-2 bg-red-500/10 text-red-400 rounded-xl
                   text-xs font-bold border border-red-500/20"
      >
        <Ban size={14} className="inline mr-1" />
        Ban
      </button>
      <button
        onClick={onClear}
        className="px-3 py-2 bg-[rgb(var(--surface-2))]
                   text-[rgb(var(--text-muted))] rounded-xl text-xs"
      >
        ✕
      </button>
    </motion.div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────
export default function Members() {
  const { activeGroupId, notifications, showToast } = useStore()
  const chatId  = activeGroupId
  const [events,   setEvents]   = useState([])
  const [approved, setApproved] = useState([])
  const [settings, setSettings] = useState({})
  const [raidStatus, setRaidStatus] = useState(null)
  const [selected, setSelected] = useState([])
  const [loading,  setLoading]  = useState(true)
  const feedRef = useRef(null)

  useEffect(() => {
    if (!chatId) return
    Promise.all([
      fetch(`/api/groups/${chatId}/members/events`, { headers: authHeaders() })
        .then(r => r.json()),
      fetch(`/api/groups/${chatId}/members/approved`, { headers: authHeaders() })
        .then(r => r.json()),
      fetch(`/api/groups/${chatId}/antiraid/status`, { headers: authHeaders() })
        .then(r => r.json()),
    ]).then(([ev, app, raid]) => {
      setEvents(ev)
      setApproved(app)
      setRaidStatus(raid)
      setLoading(false)
    })
  }, [chatId])

  // Push new SSE join/leave events to feed
  useEffect(() => {
    const latest = notifications[0]
    if (!latest) return
    if (["join","leave","raid_join","captcha_pass","captcha_fail"]
        .includes(latest.type)) {
      setEvents(prev => [{
        event_type: latest.type,
        full_name:  latest.title.replace(/^[^\s]+ /, ""),
        username:   latest.body.match(/@(\w+)/)?.[1],
        created_at: new Date().toISOString(),
      }, ...prev].slice(0, 100))

      // Auto-refresh raid status on raid event
      if (latest.type === "raid_join") {
        fetch(`/api/groups/${chatId}/antiraid/status`, { headers: authHeaders() })
          .then(r => r.json())
          .then(setRaidStatus)
      }
    }
  }, [notifications[0]?.id])

  const saveSettings = async (updates) => {
    setSettings(s => ({ ...s, ...updates }))
    await fetch(`/api/groups/${chatId}/antiraid/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(updates),
    })
    showToast("Saved", "success")
  }

  const toggleRaid = async (enable) => {
    await fetch(`/api/groups/${chatId}/antiraid/toggle`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ enable }),
    })
    const status = await fetch(
      `/api/groups/${chatId}/antiraid/status`, { headers: authHeaders() }
    ).then(r => r.json())
    setRaidStatus(status)
    showToast(enable ? "Anti-raid activated" : "Anti-raid deactivated",
              enable ? "warning" : "success")
  }

  const bulkAction = async (action) => {
    await fetch(`/api/groups/${chatId}/members/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ user_ids: selected, action }),
    })
    showToast(`${action} applied to ${selected.length} members`, "success")
    setSelected([])
  }

  const unapprove = async (userId) => {
    await fetch(
      `/api/groups/${chatId}/members/${userId}/approve`,
      { method: "DELETE", headers: authHeaders() }
    )
    setApproved(a => a.filter(m => m.user_id !== userId))
    showToast("Approval removed", "success")
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-accent border-t-transparent
                      rounded-full animate-spin" />
    </div>
  )

  return (
    <div className="p-4 max-w-2xl mx-auto pb-28">

      {/* Active raid banner */}
      {raidStatus?.is_active && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-4 p-4 bg-red-500/10 border border-red-500/30
                     rounded-2xl"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle size={18} className="text-red-400" />
              <div>
                <p className="font-bold text-red-400 text-sm">
                  🚨 Raid in Progress
                </p>
                <p className="text-xs text-red-400/70">
                  {raidStatus.join_count} joins blocked
                </p>
              </div>
            </div>
            <button
              onClick={() => toggleRaid(false)}
              className="px-4 py-2 bg-red-500 text-white rounded-xl
                         text-xs font-bold"
            >
              End Raid
            </button>
          </div>
        </motion.div>
      )}

      {/* Live join feed */}
      <Section title="Live Join Feed" icon={Users}
               badge={events.length} defaultOpen>
        <div className="flex justify-end mb-2">
          <button
            onClick={() =>
              fetch(`/api/groups/${chatId}/members/events`, { headers: authHeaders() })
                .then(r => r.json())
                .then(setEvents)
            }
            className="flex items-center gap-1 text-xs
                       text-[rgb(var(--text-muted))] hover:text-accent"
          >
            <RefreshCw size={12} />
            Refresh
          </button>
        </div>
        <div ref={feedRef} className="max-h-64 overflow-y-auto">
          {events.length === 0 ? (
            <p className="text-sm text-center text-[rgb(var(--text-muted))]
                          py-4">
              No recent activity
            </p>
          ) : (
            events.map((e, i) => <EventItem key={i} event={e} />)
          )}
        </div>
      </Section>

      {/* Anti-raid settings */}
      <Section title="Anti-Raid" icon={Shield}>
        {/* Manual toggle */}
        <div className="flex items-center justify-between pb-3 mb-3
                        border-b border-[rgb(var(--border))]">
          <div>
            <p className="text-sm font-semibold text-[rgb(var(--text))]">
              Manual Anti-Raid
            </p>
            <p className="text-xs text-[rgb(var(--text-muted))]">
              {raidStatus?.is_active ? "Currently active" : "Not active"}
            </p>
          </div>
          <button
            onClick={() => toggleRaid(!raidStatus?.is_active)}
            className={clsx(
              "px-4 py-2 rounded-xl text-xs font-bold transition-colors",
              raidStatus?.is_active
                ? "bg-red-500/10 text-red-400 border border-red-500/20"
                : "bg-accent/10 text-accent border border-accent/20"
            )}
          >
            {raidStatus?.is_active ? "Deactivate" : "Activate"}
          </button>
        </div>

        {/* Auto anti-raid */}
        <div className="flex items-center justify-between py-2.5">
          <p className="text-sm text-[rgb(var(--text))]">Auto Anti-Raid</p>
          <Toggle
            value={settings.auto_antiraid_enabled}
            onChange={v => saveSettings({ auto_antiraid_enabled: v })}
          />
        </div>

        {/* Threshold */}
        <div className="flex items-center justify-between py-2.5">
          <div>
            <p className="text-sm text-[rgb(var(--text))]">
              Trigger threshold
            </p>
            <p className="text-xs text-[rgb(var(--text-muted))]">
              Joins per minute
            </p>
          </div>
          <input
            type="number"
            min={3}
            max={100}
            defaultValue={settings.auto_antiraid_threshold || 15}
            onBlur={e => saveSettings({
              auto_antiraid_threshold: parseInt(e.target.value) || 15
            })}
            className="w-20 bg-[rgb(var(--surface-2))] rounded-lg px-3 py-1.5
                       text-sm text-[rgb(var(--text))] text-right
                       border border-[rgb(var(--border))]"
          />
        </div>

        {/* Mode */}
        <div className="py-2.5">
          <p className="text-sm text-[rgb(var(--text))] mb-2">Raid mode</p>
          <div className="flex gap-2">
            {["restrict", "ban", "captcha"].map(mode => (
              <button
                key={mode}
                onClick={() => saveSettings({ antiraid_mode: mode })}
                className={clsx(
                  "flex-1 py-2 rounded-xl text-xs font-semibold border",
                  "capitalize transition-colors",
                  settings.antiraid_mode === mode
                    ? "bg-accent/10 border-accent/30 text-accent"
                    : "bg-[rgb(var(--surface-2))] border-[rgb(var(--border))]"
                    + " text-[rgb(var(--text-muted))]"
                )}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>

        {/* Duration */}
        <div className="flex items-center justify-between py-2.5">
          <div>
            <p className="text-sm text-[rgb(var(--text))]">
              Auto-end after (mins)
            </p>
            <p className="text-xs text-[rgb(var(--text-muted))]">
              0 = manual unlock
            </p>
          </div>
          <input
            type="number"
            min={0}
            max={1440}
            defaultValue={settings.antiraid_duration_mins || 15}
            onBlur={e => saveSettings({
              antiraid_duration_mins: parseInt(e.target.value)
            })}
            className="w-20 bg-[rgb(var(--surface-2))] rounded-lg px-3 py-1.5
                       text-sm text-[rgb(var(--text))] text-right
                       border border-[rgb(var(--border))]"
          />
        </div>
      </Section>

      {/* CAPTCHA settings */}
      <Section title="CAPTCHA" icon={Shield}>
        <div className="flex items-center justify-between py-2.5
                        border-b border-[rgb(var(--border))] mb-3">
          <p className="text-sm font-semibold text-[rgb(var(--text))]">
            Require CAPTCHA on join
          </p>
          <Toggle
            value={settings.captcha_enabled}
            onChange={v => saveSettings({ captcha_enabled: v })}
          />
        </div>

        {/* Mode selector */}
        <div className="mb-3">
          <p className="text-xs text-[rgb(var(--text-muted))] mb-2">
            CAPTCHA Mode
          </p>
          <div className="grid grid-cols-3 gap-2">
            {[
              { id: "button", label: "🔘 Button", desc: "Tap correct button" },
              { id: "math",   label: "🔢 Math",   desc: "Solve equation"    },
              { id: "text",   label: "🔤 Text",   desc: "Type code phrase"  },
            ].map(({ id, label, desc }) => (
              <button
                key={id}
                onClick={() => saveSettings({ captcha_mode: id })}
                className={clsx(
                  "p-3 rounded-xl border text-center transition-colors",
                  settings.captcha_mode === id
                    ? "bg-accent/10 border-accent/30"
                    : "bg-[rgb(var(--surface-2))] border-[rgb(var(--border))]"
                )}
              >
                <p className="text-sm font-medium text-[rgb(var(--text))]">
                  {label}
                </p>
                <p className="text-xs text-[rgb(var(--text-muted))] mt-0.5">
                  {desc}
                </p>
              </button>
            ))}
          </div>
        </div>

        {/* Timeout */}
        <div className="flex items-center justify-between py-2.5">
          <div>
            <p className="text-sm text-[rgb(var(--text))]">
              Timeout (minutes)
            </p>
            <p className="text-xs text-[rgb(var(--text-muted))]">
              Kick if not verified
            </p>
          </div>
          <input
            type="number"
            min={1}
            max={60}
            defaultValue={settings.captcha_timeout_mins || 5}
            onBlur={e => saveSettings({
              captcha_timeout_mins: parseInt(e.target.value) || 5
            })}
            className="w-20 bg-[rgb(var(--surface-2))] rounded-lg px-3 py-1.5
                       text-sm text-[rgb(var(--text))] text-right
                       border border-[rgb(var(--border))]"
          />
        </div>

        <div className="flex items-center justify-between py-2.5">
          <p className="text-sm text-[rgb(var(--text))]">
            Kick on timeout
          </p>
          <Toggle
            value={settings.captcha_kick_on_timeout}
            onChange={v => saveSettings({ captcha_kick_on_timeout: v })}
          />
        </div>
      </Section>

      {/* Approved members */}
      <Section title="Approved Members" icon={UserCheck}
               badge={approved.length}>
        <p className="text-xs text-[rgb(var(--text-muted))] mb-3">
          Approved members bypass all automod rules.
        </p>

        {approved.length === 0 ? (
          <p className="text-sm text-center text-[rgb(var(--text-muted))]
                        py-3">
            No approved members
          </p>
        ) : (
          <div className="space-y-2">
            {approved.map(m => (
              <div
                key={m.user_id}
                className="flex items-center gap-3 p-3
                           bg-[rgb(var(--surface-2))] rounded-xl"
              >
                <div className="w-8 h-8 rounded-full bg-accent/20 flex
                                items-center justify-center text-accent
                                text-sm font-bold">
                  {(m.username || String(m.user_id))[0]?.toUpperCase()}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-[rgb(var(--text))]">
                    @{m.username || m.user_id}
                  </p>
                  <p className="text-xs text-[rgb(var(--text-muted))]">
                    Approved {formatDistanceToNow(
                      new Date(m.approved_at), { addSuffix: true }
                    )}
                  </p>
                </div>
                <button
                  onClick={() => unapprove(m.user_id)}
                  className="p-2 text-red-400 hover:text-red-300
                             transition-colors"
                >
                  <UserX size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
      </Section>

      {/* Bulk action bar */}
      <AnimatePresence>
        <BulkActionBar
          selected={selected}
          onAction={bulkAction}
          onClear={() => setSelected([])}
        />
      </AnimatePresence>
    </div>
  )
}
