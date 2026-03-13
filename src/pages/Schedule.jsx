/**
 * src/pages/Schedule.jsx
 *
 * Sections:
 *   1. Timeline view       — all scheduled tasks on a visual timeline
 *   2. New message form    — full scheduler with all schedule types
 *   3. Active schedules    — list with pause/delete controls
 *   4. Reports             — admin report inbox
 */

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Calendar, Clock, Plus, Pause, Play, Trash2,
  ChevronDown, ChevronUp, AlertCircle, CheckCircle,
  Send, Pin, Repeat
} from "lucide-react"
import { useStore } from "../store"
import { format, formatDistanceToNow, parseISO } from "date-fns"
import clsx from "clsx"

const SCHEDULE_TYPES = [
  { id: "once",     label: "Once",     icon: "1️⃣", desc: "Send at specific time"      },
  { id: "interval", label: "Interval", icon: "🔄", desc: "Every X minutes"             },
  { id: "daily",    label: "Daily",    icon: "📅", desc: "Same time every day"         },
  { id: "weekly",   label: "Weekly",   icon: "🗓",  desc: "Specific days of the week"  },
  { id: "cron",     label: "Cron",     icon: "⚙️", desc: "Advanced cron expression"   },
]

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

function authHeaders() {
  const token = window.Telegram?.WebApp?.initData || ""
  return token ? { Authorization: `tma ${token}` } : {}
}

function Section({ title, icon: Icon, badge, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="bg-[rgb(var(--surface))] rounded-2xl overflow-hidden border border-[rgb(var(--border))] mb-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center justify-between w-full px-4 py-4"
      >
        <div className="flex items-center gap-2">
          <Icon size={16} className="text-accent" />
          <span className="font-semibold text-sm text-[rgb(var(--text))]">{title}</span>
          {badge != null && (
            <span className="px-2 py-0.5 bg-accent/10 text-accent text-xs rounded-full font-bold">
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

function TimelineBar({ messages }) {
  if (!messages.length) return (
    <p className="text-sm text-center text-[rgb(var(--text-muted))] py-4">
      No scheduled messages
    </p>
  )

  return (
    <div className="relative">
      <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-[rgb(var(--border))]" />
      <div className="space-y-3">
        {messages.map((m) => (
          <div key={m.id} className="flex items-start gap-4 pl-10 relative">
            <div className={clsx(
              "absolute left-3 top-1.5 w-2.5 h-2.5 rounded-full border-2 border-[rgb(var(--surface))]",
              m.is_active ? "bg-accent" : "bg-[rgb(var(--border))]"
            )} />
            <div className="flex-1 min-w-0 pb-3 border-b border-[rgb(var(--border))] last:border-0">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium text-[rgb(var(--text))] truncate">
                  {(m.content || "").slice(0, 40) || "(media)"}
                </p>
                <span className={clsx(
                  "text-xs px-2 py-0.5 rounded-full flex-shrink-0",
                  m.is_active
                    ? "bg-green-500/10 text-green-400"
                    : "bg-[rgb(var(--surface-3))] text-[rgb(var(--text-muted))]"
                )}>
                  {m.schedule_type}
                </span>
              </div>
              <p className="text-xs text-[rgb(var(--text-muted))] mt-0.5">
                {m.next_send_at
                  ? `Next: ${formatDistanceToNow(parseISO(m.next_send_at), { addSuffix: true })}`
                  : "Paused"
                }
                {m.send_count > 0 && ` · ${m.send_count} sent`}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function NewScheduleForm({ chatId, onCreated, onCancel }) {
  const [type,         setType]         = useState("once")
  const [content,      setContent]      = useState("")
  const [scheduledAt,  setScheduledAt]  = useState("")
  const [intervalMins, setIntervalMins] = useState(60)
  const [timeOfDay,    setTimeOfDay]    = useState("09:00")
  const [daysOfWeek,   setDaysOfWeek]   = useState([1])
  const [cronExpr,     setCronExpr]     = useState("0 9 * * 1-5")
  const [maxSends,     setMaxSends]     = useState(0)
  const [pinAfter,     setPinAfter]     = useState(false)
  const [saving,       setSaving]       = useState(false)
  const { showToast } = useStore()

  const toggleDay = (d) => {
    setDaysOfWeek(prev =>
      prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d].sort()
    )
  }

  const save = async () => {
    if (!content.trim()) return
    if (type === "once" && !scheduledAt) return
    if (type === "weekly" && daysOfWeek.length === 0) return
    setSaving(true)
    try {
      const res = await fetch(`/api/groups/${chatId}/scheduled`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          content,
          schedule_type:  type,
          scheduled_at:   type === "once" ? scheduledAt : undefined,
          interval_mins:  type === "interval" ? intervalMins : undefined,
          time_of_day:    ["daily", "weekly"].includes(type) ? timeOfDay : undefined,
          days_of_week:   type === "weekly" ? daysOfWeek : undefined,
          cron_expr:      type === "cron" ? cronExpr : undefined,
          max_sends:      maxSends,
          pin_after_send: pinAfter,
        }),
      })
      if (!res.ok) throw new Error(await res.text())
      showToast("Scheduled!", "success")
      onCreated()
    } catch {
      showToast("Failed to schedule", "error")
    }
    setSaving(false)
  }

  return (
    <div className="p-3 bg-[rgb(var(--surface-2))] rounded-xl border border-accent/20 space-y-3">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-1.5">
        {SCHEDULE_TYPES.map(t => (
          <button
            key={t.id}
            onClick={() => setType(t.id)}
            className={clsx(
              "p-2 rounded-xl border text-center transition-colors",
              type === t.id
                ? "bg-accent/10 border-accent/30"
                : "bg-[rgb(var(--surface-3))] border-[rgb(var(--border))]"
            )}
          >
            <div className="text-lg">{t.icon}</div>
            <p className="text-xs font-medium text-[rgb(var(--text))] mt-0.5">{t.label}</p>
          </button>
        ))}
      </div>

      {type === "once" && (
        <div>
          <label className="text-xs text-[rgb(var(--text-muted))] mb-1 block">Send at</label>
          <input
            type="datetime-local"
            value={scheduledAt}
            onChange={e => setScheduledAt(e.target.value)}
            className="w-full bg-[rgb(var(--surface-3))] rounded-xl px-3 py-2 text-sm text-[rgb(var(--text))] border border-[rgb(var(--border))]"
          />
        </div>
      )}

      {type === "interval" && (
        <div>
          <label className="text-xs text-[rgb(var(--text-muted))] mb-1 block">Every (minutes)</label>
          <input
            type="number"
            min={1}
            value={intervalMins}
            onChange={e => setIntervalMins(parseInt(e.target.value) || 60)}
            className="w-full bg-[rgb(var(--surface-3))] rounded-xl px-3 py-2 text-sm text-[rgb(var(--text))] border border-[rgb(var(--border))]"
          />
        </div>
      )}

      {["daily", "weekly"].includes(type) && (
        <div>
          <label className="text-xs text-[rgb(var(--text-muted))] mb-1 block">Time of day</label>
          <input
            type="time"
            value={timeOfDay}
            onChange={e => setTimeOfDay(e.target.value)}
            className="w-full bg-[rgb(var(--surface-3))] rounded-xl px-3 py-2 text-sm text-[rgb(var(--text))] border border-[rgb(var(--border))]"
          />
        </div>
      )}

      {type === "weekly" && (
        <div>
          <label className="text-xs text-[rgb(var(--text-muted))] mb-1 block">Days of week</label>
          <div className="flex gap-1.5 flex-wrap">
            {DAYS.map((d, i) => (
              <button
                key={i}
                onClick={() => toggleDay(i)}
                className={clsx(
                  "px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors",
                  daysOfWeek.includes(i)
                    ? "bg-accent text-white"
                    : "bg-[rgb(var(--surface-3))] text-[rgb(var(--text-muted))]"
                )}
              >
                {d}
              </button>
            ))}
          </div>
        </div>
      )}

      {type === "cron" && (
        <div>
          <label className="text-xs text-[rgb(var(--text-muted))] mb-1 block">Cron expression</label>
          <input
            value={cronExpr}
            onChange={e => setCronExpr(e.target.value)}
            placeholder="0 9 * * 1-5"
            className="w-full bg-[rgb(var(--surface-3))] rounded-xl px-3 py-2 text-sm font-mono text-[rgb(var(--text))] border border-[rgb(var(--border))]"
          />
          <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
            {cronExpr} = weekdays at 9 AM
          </p>
        </div>
      )}

      <div>
        <label className="text-xs text-[rgb(var(--text-muted))] mb-1 block">Message content</label>
        <textarea
          value={content}
          onChange={e => setContent(e.target.value)}
          rows={3}
          placeholder="Message text. Supports {variables} and [buttons](buttonurl://...)"
          className="w-full bg-[rgb(var(--surface-3))] rounded-xl px-3 py-2 text-sm text-[rgb(var(--text))] font-mono resize-none border border-[rgb(var(--border))] placeholder-[rgb(var(--text-subtle))]"
        />
      </div>

      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-xs text-[rgb(var(--text-muted))]">Max sends (0 = ∞)</label>
          <input
            type="number"
            min={0}
            value={maxSends}
            onChange={e => setMaxSends(parseInt(e.target.value) || 0)}
            className="w-16 bg-[rgb(var(--surface-3))] rounded-lg px-2 py-1 text-xs text-[rgb(var(--text))] text-right border border-[rgb(var(--border))]"
          />
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <div
            onClick={() => setPinAfter(!pinAfter)}
            className={clsx(
              "w-8 h-4 rounded-full transition-colors relative",
              pinAfter ? "bg-accent" : "bg-[rgb(var(--surface-3))]"
            )}
          >
            <motion.div
              animate={{ x: pinAfter ? 16 : 2 }}
              transition={{ type: "spring", stiffness: 500, damping: 30 }}
              className="absolute top-0.5 w-3 h-3 bg-white rounded-full"
            />
          </div>
          <span className="text-xs text-[rgb(var(--text-muted))]">Pin after send</span>
        </label>
      </div>

      <div className="flex gap-2 justify-end">
        <button
          onClick={onCancel}
          className="px-4 py-2 text-xs text-[rgb(var(--text-muted))] bg-[rgb(var(--surface-3))] rounded-xl"
        >
          Cancel
        </button>
        <button
          onClick={save}
          disabled={saving || !content.trim()}
          className="px-4 py-2 text-xs font-bold text-white bg-accent rounded-xl disabled:opacity-50 flex items-center gap-1.5"
        >
          <Send size={12} />
          {saving ? "Scheduling..." : "Schedule"}
        </button>
      </div>
    </div>
  )
}

function ScheduledRow({ msg, onPause, onDelete }) {
  const typeConfig = SCHEDULE_TYPES.find(t => t.id === msg.schedule_type)

  return (
    <div className="p-3 bg-[rgb(var(--surface-2))] rounded-xl border border-[rgb(var(--border))]">
      <div className="flex items-start gap-3">
        <div className="text-xl flex-shrink-0">{typeConfig?.icon || "📨"}</div>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-[rgb(var(--text))] truncate">
            {(msg.content || "").slice(0, 60) || "(media)"}
          </p>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <span className="text-xs text-[rgb(var(--text-muted))]">{typeConfig?.label}</span>
            {msg.next_send_at && (
              <span className="text-xs text-[rgb(var(--text-muted))]">
                · Next: {formatDistanceToNow(parseISO(msg.next_send_at), { addSuffix: true })}
              </span>
            )}
            {msg.send_count > 0 && (
              <span className="text-xs text-[rgb(var(--text-muted))]">· {msg.send_count} sent</span>
            )}
            {msg.pin_after_send && (
              <span className="flex items-center gap-0.5 text-xs text-cyan-400">
                <Pin size={9} /> Pin
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-1 flex-shrink-0">
          <button
            onClick={() => onPause(msg.id)}
            className="p-1.5 text-[rgb(var(--text-muted))] hover:text-accent transition-colors"
          >
            {msg.is_active ? <Pause size={14} /> : <Play size={14} />}
          </button>
          <button
            onClick={() => onDelete(msg.id)}
            className="p-1.5 text-[rgb(var(--text-muted))] hover:text-red-400 transition-colors"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Schedule() {
  const { activeGroupId, showToast } = useStore()
  const chatId = activeGroupId

  const [messages,    setMessages]    = useState([])
  const [reports,     setReports]     = useState([])
  const [loading,     setLoading]     = useState(true)
  const [showNewForm, setShowNewForm] = useState(false)

  const load = async () => {
    if (!chatId) return
    try {
      const [msgsRes, repsRes] = await Promise.all([
        fetch(`/api/groups/${chatId}/scheduled`, { headers: authHeaders() }),
        fetch(`/api/groups/${chatId}/reports`,   { headers: authHeaders() }),
      ])
      const msgs = msgsRes.ok ? await msgsRes.json() : []
      const reps = repsRes.ok ? await repsRes.json() : []
      setMessages(Array.isArray(msgs) ? msgs : [])
      setReports(Array.isArray(reps) ? reps : [])
    } catch {
      setMessages([])
      setReports([])
    }
    setLoading(false)
  }

  useEffect(() => { if (chatId) load() }, [chatId])

  const pauseMsg = async (id) => {
    await fetch(`/api/groups/${chatId}/scheduled/${id}/pause`, {
      method: "POST",
      headers: authHeaders(),
    })
    setMessages(prev => prev.map(m =>
      m.id === id ? { ...m, is_active: !m.is_active } : m
    ))
  }

  const deleteMsg = async (id) => {
    await fetch(`/api/groups/${chatId}/scheduled/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    })
    setMessages(prev => prev.filter(m => m.id !== id))
    showToast("Deleted", "success")
  }

  const reviewReport = async (id, status) => {
    await fetch(`/api/groups/${chatId}/reports/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ status }),
    })
    setReports(prev => prev.map(r => r.id === id ? { ...r, status } : r))
    showToast(`Report ${status}`, "success")
  }

  const openReports = reports.filter(r => r.status === "open")

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
    </div>
  )

  return (
    <div className="p-4 max-w-2xl mx-auto pb-24">

      <Section title="Schedule Timeline" icon={Calendar}
               badge={messages.filter(m => m.is_active).length} defaultOpen>
        <TimelineBar messages={messages} />
      </Section>

      <Section title="Scheduled Messages" icon={Repeat} badge={messages.length}>
        <div className="space-y-2 mb-3">
          {messages.map(m => (
            <ScheduledRow key={m.id} msg={m} onPause={pauseMsg} onDelete={deleteMsg} />
          ))}
          {messages.length === 0 && !showNewForm && (
            <p className="text-sm text-center text-[rgb(var(--text-muted))] py-2">
              No scheduled messages
            </p>
          )}
        </div>

        <AnimatePresence>
          {showNewForm && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden mb-3"
            >
              <NewScheduleForm
                chatId={chatId}
                onCreated={() => { setShowNewForm(false); load() }}
                onCancel={() => setShowNewForm(false)}
              />
            </motion.div>
          )}
        </AnimatePresence>

        <button
          onClick={() => setShowNewForm(true)}
          className="flex items-center gap-2 w-full py-2.5 px-3 bg-accent/10 border border-accent/20 rounded-xl text-accent text-sm font-semibold hover:bg-accent/20 transition-colors"
        >
          <Plus size={16} />
          New Scheduled Message
        </button>
      </Section>

      <Section title="Reports" icon={AlertCircle}
               badge={openReports.length > 0 ? openReports.length : undefined}>
        {reports.length === 0 ? (
          <p className="text-sm text-center text-[rgb(var(--text-muted))] py-2">No reports</p>
        ) : (
          <div className="space-y-2">
            {reports.map(r => (
              <div
                key={r.id}
                className={clsx(
                  "p-3 rounded-xl border",
                  r.status === "open"
                    ? "bg-amber-500/5 border-amber-500/20"
                    : "bg-[rgb(var(--surface-2))] border-[rgb(var(--border))]"
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={clsx(
                        "text-xs px-1.5 py-0.5 rounded font-medium",
                        r.status === "open"
                          ? "bg-amber-500/20 text-amber-400"
                          : "bg-[rgb(var(--surface-3))] text-[rgb(var(--text-muted))]"
                      )}>
                        #{r.id} {r.status}
                      </span>
                    </div>
                    <p className="text-xs text-[rgb(var(--text-muted))] mt-1">
                      Reason: {r.reason || "None"}
                    </p>
                  </div>
                  {r.status === "open" && (
                    <div className="flex gap-1.5 flex-shrink-0">
                      <button
                        onClick={() => reviewReport(r.id, "reviewed")}
                        className="px-2 py-1 bg-green-500/10 text-green-400 text-xs rounded-lg border border-green-500/20"
                      >
                        Reviewed
                      </button>
                      <button
                        onClick={() => reviewReport(r.id, "dismissed")}
                        className="px-2 py-1 bg-[rgb(var(--surface-3))] text-[rgb(var(--text-muted))] text-xs rounded-lg"
                      >
                        Dismiss
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  )
}
