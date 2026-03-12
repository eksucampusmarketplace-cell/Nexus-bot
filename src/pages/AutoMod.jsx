/**
 * src/pages/AutoMod.jsx
 *
 * Full advanced automod management page.
 *
 * Sections:
 *   1. Rule Templates     — one-tap presets
 *   2. Locks Panel        — all toggles with time window + penalty per rule
 *   3. Drag Rule Priority — @dnd-kit sortable list
 *   4. Silent Times       — 3 slots with time pickers
 *   5. Message Controls   — word/line/char limits, duplicates
 *   6. REGEX Manager      — add/test/remove patterns
 *   7. Necessary Words    — required word list
 *   8. Advanced           — self-destruct, lock admins, unofficial TG
 *   9. Conflict Detector  — live warnings panel
 */

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors
} from "@dnd-kit/core"
import {
  SortableContext, verticalListSortingStrategy,
  useSortable, arrayMove
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import {
  Shield, Clock, AlertTriangle, GripVertical,
  Plus, Trash2, TestTube, ChevronDown, ChevronUp,
  Zap, CheckCircle, XCircle
} from "lucide-react"
import { useStore } from "../store"
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
        {open ? <ChevronUp size={16} className="text-[rgb(var(--text-muted))]" />
               : <ChevronDown size={16} className="text-[rgb(var(--text-muted))]" />}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4 border-t border-[rgb(var(--border))]
                            pt-4">
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Toggle row ─────────────────────────────────────────────────────────────
function ToggleRow({ label, value, onChange, desc }) {
  return (
    <div className="flex items-center justify-between py-2.5">
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

// ── Sortable rule item ─────────────────────────────────────────────────────
function SortableRuleItem({ id, label }) {
  const { attributes, listeners, setNodeRef, transform, transition } =
    useSortable({ id })

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className="flex items-center gap-3 py-2.5 px-3 bg-[rgb(var(--surface-2))]
                 rounded-xl mb-2 border border-[rgb(var(--border))]"
    >
      <div {...attributes} {...listeners} className="cursor-grab">
        <GripVertical size={16} className="text-[rgb(var(--text-subtle))]" />
      </div>
      <span className="text-sm text-[rgb(var(--text))]">{label}</span>
    </div>
  )
}

// ── Template card ──────────────────────────────────────────────────────────
const TEMPLATE_ICONS = {
  Gaming: "🎮", Study: "📚", Crypto: "₿",
  "News Channel Group": "📰", Support: "💬", Strict: "🔒"
}

function TemplateCard({ template, onApply }) {
  const [confirming, setConfirming] = useState(false)
  return (
    <div className="bg-[rgb(var(--surface-2))] rounded-xl p-3
                    border border-[rgb(var(--border))]">
      <div className="text-2xl mb-1">
        {TEMPLATE_ICONS[template.name] || "⚙️"}
      </div>
      <p className="text-sm font-semibold text-[rgb(var(--text))]">
        {template.name}
      </p>
      <p className="text-xs text-[rgb(var(--text-muted))] mt-0.5 mb-3">
        {template.description}
      </p>
      {confirming ? (
        <div className="flex gap-2">
          <button
            onClick={() => { onApply(template.id); setConfirming(false) }}
            className="flex-1 py-1.5 bg-accent text-white text-xs
                       font-bold rounded-lg"
          >
            Apply
          </button>
          <button
            onClick={() => setConfirming(false)}
            className="flex-1 py-1.5 bg-[rgb(var(--surface-3))] text-xs
                       text-[rgb(var(--text-muted))] rounded-lg"
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          onClick={() => setConfirming(true)}
          className="w-full py-1.5 bg-accent/10 text-accent text-xs
                     font-semibold rounded-lg border border-accent/20
                     hover:bg-accent/20 transition-colors"
        >
          Use Template
        </button>
      )}
    </div>
  )
}

// ── Conflict badge ─────────────────────────────────────────────────────────
function ConflictBadge({ conflict }) {
  const colors = {
    contradiction: "bg-red-500/10 border-red-500/30 text-red-400",
    redundant:     "bg-amber-500/10 border-amber-500/30 text-amber-400",
    impossible:    "bg-red-600/10 border-red-600/30 text-red-500",
  }
  return (
    <div className={clsx(
      "flex items-start gap-2 p-3 rounded-xl border mb-2 text-sm",
      colors[conflict.conflict_type] || colors.contradiction
    )}>
      <AlertTriangle size={14} className="flex-shrink-0 mt-0.5" />
      <div>
        <p className="font-medium text-xs uppercase tracking-wide opacity-70">
          {conflict.conflict_type}
        </p>
        <p className="text-xs mt-0.5">{conflict.message}</p>
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────
export default function AutoMod() {
  const { activeGroupId, showToast } = useStore()
  const [data,       setData]       = useState(null)
  const [templates,  setTemplates]  = useState([])
  const [conflicts,  setConflicts]  = useState([])
  const [ruleOrder,  setRuleOrder]  = useState([])
  const [loading,    setLoading]    = useState(true)
  const [regexInput, setRegexInput] = useState("")
  const [regexTest,  setRegexTest]  = useState("")
  const [regexResult,setRegexResult]= useState(null)
  const [newWord,    setNewWord]    = useState("")

  // DnD sensors
  const sensors = useSensors(useSensor(PointerSensor, {
    activationConstraint: { distance: 5 }
  }))

  const chatId = activeGroupId

  useEffect(() => {
    if (!chatId) return
    Promise.all([
      fetch(`/api/groups/${chatId}/automod/advanced`, authHeaders())
        .then(r => r.json()),
      fetch(`/api/groups/${chatId}/automod/templates`, authHeaders())
        .then(r => r.json()),
      fetch(`/api/groups/${chatId}/automod/conflicts`, authHeaders())
        .then(r => r.json()),
    ]).then(([adv, tmpl, conf]) => {
      setData(adv)
      setTemplates(tmpl)
      setConflicts(conf)
      setRuleOrder(adv.rule_order || DEFAULT_RULE_ORDER)
      setLoading(false)
    })
  }, [chatId])

  const save = async (updates) => {
    const next = { ...data, ...updates }
    setData(next)
    await fetch(`/api/groups/${chatId}/automod/advanced`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify(updates),
    })
    // Refresh conflicts
    const conf = await fetch(
      `/api/groups/${chatId}/automod/conflicts`, authHeaders()
    ).then(r => r.json())
    setConflicts(conf)
    showToast("Saved", "success")
  }

  const applyTemplate = async (templateId) => {
    await fetch(`/api/groups/${chatId}/automod/templates/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ template_id: templateId }),
    })
    showToast("Template applied!", "success")
    // Reload
    const adv = await fetch(
      `/api/groups/${chatId}/automod/advanced`, authHeaders()
    ).then(r => r.json())
    setData(adv)
  }

  const handleDragEnd = async (event) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const oldIndex = ruleOrder.indexOf(active.id)
    const newIndex = ruleOrder.indexOf(over.id)
    const newOrder = arrayMove(ruleOrder, oldIndex, newIndex)
    setRuleOrder(newOrder)
    await fetch(`/api/groups/${chatId}/automod/rule-priority`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ order: newOrder }),
    })
  }

  const testRegex = () => {
    try {
      const match = new RegExp(regexInput, "i").test(regexTest)
      setRegexResult(match)
    } catch {
      setRegexResult(null)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-accent border-t-transparent
                      rounded-full animate-spin" />
    </div>
  )

  return (
    <div className="p-4 max-w-2xl mx-auto pb-24">

      {/* Conflict detector banner */}
      {conflicts.length > 0 && (
        <div className="mb-4 p-3 bg-amber-500/10 border border-amber-500/30
                        rounded-2xl">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={16} className="text-amber-400" />
            <p className="text-sm font-semibold text-amber-400">
              {conflicts.length} rule conflict{conflicts.length > 1 ? "s" : ""} detected
            </p>
          </div>
          {conflicts.map((c, i) => <ConflictBadge key={i} conflict={c} />)}
        </div>
      )}

      {/* Templates */}
      <Section title="Rule Templates" icon={Zap} defaultOpen>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          {templates.map(t => (
            <TemplateCard key={t.id} template={t} onApply={applyTemplate} />
          ))}
        </div>
      </Section>

      {/* Silent times */}
      <Section title="Silent Times" icon={Clock}>
        {[1, 2, 3].map(slot => {
          const st = data?.silent_times?.find(s => s.slot === slot) || {}
          return (
            <div key={slot}
                 className="mb-4 p-3 bg-[rgb(var(--surface-2))] rounded-xl">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-[rgb(var(--text))]">
                  Slot {slot}
                </p>
                <button
                  onClick={() => save({
                    silent_times: (data.silent_times || []).map(s =>
                      s.slot === slot
                        ? { ...s, is_active: !s.is_active }
                        : s
                    )
                  })}
                  className={clsx(
                    "text-xs px-2 py-1 rounded-lg font-medium",
                    st.is_active
                      ? "bg-accent/10 text-accent"
                      : "bg-[rgb(var(--surface-3))] text-[rgb(var(--text-muted))]"
                  )}
                >
                  {st.is_active ? "Active" : "Inactive"}
                </button>
              </div>
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="text-xs text-[rgb(var(--text-muted))]">
                    Start
                  </label>
                  <input
                    type="time"
                    defaultValue={st.start_time || "00:00"}
                    onChange={e => save({
                      silent_times: [
                        ...(data.silent_times || []).filter(s => s.slot !== slot),
                        { ...(st || {}), slot, start_time: e.target.value }
                      ]
                    })}
                    className="w-full mt-1 bg-[rgb(var(--surface-3))] rounded-lg
                               px-3 py-2 text-sm text-[rgb(var(--text))]
                               border border-[rgb(var(--border))]"
                  />
                </div>
                <div className="flex-1">
                  <label className="text-xs text-[rgb(var(--text-muted))]">
                    End
                  </label>
                  <input
                    type="time"
                    defaultValue={st.end_time || "08:00"}
                    onChange={e => save({
                      silent_times: [
                        ...(data.silent_times || []).filter(s => s.slot !== slot),
                        { ...(st || {}), slot, end_time: e.target.value }
                      ]
                    })}
                    className="w-full mt-1 bg-[rgb(var(--surface-3))] rounded-lg
                               px-3 py-2 text-sm text-[rgb(var(--text))]
                               border border-[rgb(var(--border))]"
                  />
                </div>
              </div>
            </div>
          )
        })}
      </Section>

      {/* Message controls */}
      <Section title="Message Controls" icon={Shield}>
        {[
          { label: "Min words",    key: "min_words",  desc: "0 = disabled" },
          { label: "Max words",    key: "max_words",  desc: "0 = disabled" },
          { label: "Min lines",    key: "min_lines",  desc: "0 = disabled" },
          { label: "Max lines",    key: "max_lines",  desc: "0 = disabled" },
          { label: "Min chars",    key: "min_chars",  desc: "0 = disabled" },
          { label: "Max chars",    key: "max_chars",  desc: "0 = disabled" },
          { label: "Max duplicates", key: "duplicate_limit",
            desc: "0 = disabled" },
          { label: "Duplicate window (mins)",
            key: "duplicate_window_mins", desc: "" },
        ].map(({ label, key, desc }) => (
          <div key={key} className="flex items-center justify-between py-2.5
                                    border-b border-[rgb(var(--border))]
                                    last:border-0">
            <div>
              <p className="text-sm text-[rgb(var(--text))]">{label}</p>
              {desc && (
                <p className="text-xs text-[rgb(var(--text-muted))]">{desc}</p>
              )}
            </div>
            <input
              type="number"
              min={0}
              defaultValue={data?.[key] || 0}
              onBlur={e => save({ [key]: parseInt(e.target.value) || 0 })}
              className="w-20 bg-[rgb(var(--surface-2))] rounded-lg px-3 py-1.5
                         text-sm text-[rgb(var(--text))] text-right
                         border border-[rgb(var(--border))]"
            />
          </div>
        ))}
      </Section>

      {/* Drag rule priority */}
      <Section title="Rule Priority (Drag to reorder)" icon={GripVertical}>
        <p className="text-xs text-[rgb(var(--text-muted))] mb-3">
          Rules are evaluated top to bottom. First match wins.
        </p>
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={ruleOrder}
            strategy={verticalListSortingStrategy}
          >
            {ruleOrder.map(id => (
              <SortableRuleItem
                key={id}
                id={id}
                label={RULE_LABELS[id] || id}
              />
            ))}
          </SortableContext>
        </DndContext>
      </Section>

      {/* REGEX */}
      <Section title="REGEX Patterns" icon={TestTube}>
        <div className="space-y-3">
          {(data?.regex_patterns || []).map((p, i) => (
            <div key={i}
                 className="flex items-center gap-2 p-3
                            bg-[rgb(var(--surface-2))] rounded-xl">
              <code className="flex-1 text-xs text-accent font-mono truncate">
                {p.pattern}
              </code>
              <span className="text-xs px-2 py-0.5 rounded-lg
                               bg-[rgb(var(--surface-3))]
                               text-[rgb(var(--text-muted))]">
                {p.penalty}
              </span>
              <button
                onClick={async () => {
                  await fetch(`/api/groups/${chatId}/automod/advanced`, {
                    method: "PUT",
                    headers: {
                      "Content-Type": "application/json",
                      ...authHeaders()
                    },
                    body: JSON.stringify({
                      remove_regex: p.pattern
                    }),
                  })
                  showToast("Pattern removed", "success")
                }}
                className="text-red-400 hover:text-red-300 transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}

          {/* Add + test */}
          <div className="p-3 bg-[rgb(var(--surface-2))] rounded-xl space-y-2">
            <input
              placeholder="Pattern: ^\d{10}$"
              value={regexInput}
              onChange={e => setRegexInput(e.target.value)}
              className="w-full bg-[rgb(var(--surface-3))] rounded-lg px-3 py-2
                         text-sm font-mono text-[rgb(var(--text))]
                         border border-[rgb(var(--border))] placeholder-[rgb(var(--text-subtle))]"
            />
            <input
              placeholder="Test string..."
              value={regexTest}
              onChange={e => setRegexTest(e.target.value)}
              className="w-full bg-[rgb(var(--surface-3))] rounded-lg px-3 py-2
                         text-sm text-[rgb(var(--text))]
                         border border-[rgb(var(--border))] placeholder-[rgb(var(--text-subtle))]"
            />
            {regexResult !== null && (
              <div className={clsx(
                "flex items-center gap-2 text-sm",
                regexResult ? "text-green-400" : "text-red-400"
              )}>
                {regexResult
                  ? <CheckCircle size={14} />
                  : <XCircle size={14} />
                }
                {regexResult ? "Match" : "No match"}
              </div>
            )}
            <div className="flex gap-2">
              <button
                onClick={testRegex}
                className="flex-1 py-2 bg-[rgb(var(--surface-3))] rounded-lg
                           text-xs text-[rgb(var(--text-muted))] font-medium"
              >
                Test
              </button>
              <button
                onClick={async () => {
                  if (!regexInput) return
                  await save({ add_regex: regexInput })
                  setRegexInput("")
                  showToast("Pattern added", "success")
                }}
                className="flex-1 py-2 bg-accent text-white rounded-lg
                           text-xs font-bold"
              >
                Add Pattern
              </button>
            </div>
          </div>
        </div>
      </Section>

      {/* Necessary words */}
      <Section title="Necessary Words" icon={Shield}>
        <ToggleRow
          label="Active"
          desc="Every message must contain at least one of these words"
          value={data?.necessary_words_active}
          onChange={v => save({ necessary_words_active: v })}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          {(data?.necessary_words || []).map((w, i) => (
            <div key={i}
                 className="flex items-center gap-1 px-3 py-1.5
                            bg-accent/10 border border-accent/20 rounded-xl">
              <span className="text-sm text-accent">{w}</span>
              <button
                onClick={() => save({
                  necessary_words: data.necessary_words.filter(x => x !== w)
                })}
                className="text-accent/60 hover:text-accent"
              >
                <XCircle size={12} />
              </button>
            </div>
          ))}
        </div>
        <div className="flex gap-2 mt-3">
          <input
            placeholder="Add required word..."
            value={newWord}
            onChange={e => setNewWord(e.target.value)}
            onKeyDown={e => e.key === "Enter" && (() => {
              if (!newWord.trim()) return
              save({
                necessary_words: [
                  ...(data?.necessary_words || []),
                  newWord.trim()
                ]
              })
              setNewWord("")
            })()}
            className="flex-1 bg-[rgb(var(--surface-2))] rounded-xl px-3 py-2
                       text-sm text-[rgb(var(--text))]
                       border border-[rgb(var(--border))]
                       placeholder-[rgb(var(--text-subtle))]"
          />
          <button
            onClick={() => {
              if (!newWord.trim()) return
              save({
                necessary_words: [
                  ...(data?.necessary_words || []),
                  newWord.trim()
                ]
              })
              setNewWord("")
            }}
            className="px-4 py-2 bg-accent text-white rounded-xl text-sm
                       font-bold"
          >
            <Plus size={16} />
          </button>
        </div>
      </Section>

      {/* Advanced */}
      <Section title="Advanced Settings" icon={Shield}>
        <ToggleRow
          label="Self-destruct bot messages"
          desc="Bot messages auto-delete after set time"
          value={data?.self_destruct_enabled}
          onChange={v => save({ self_destruct_enabled: v })}
        />
        {data?.self_destruct_enabled && (
          <div className="flex items-center justify-between py-2">
            <span className="text-sm text-[rgb(var(--text-muted))]">
              Delete after (minutes)
            </span>
            <input
              type="number"
              min={1}
              max={60}
              defaultValue={data.self_destruct_minutes || 2}
              onBlur={e => save({
                self_destruct_minutes: parseInt(e.target.value) || 2
              })}
              className="w-20 bg-[rgb(var(--surface-2))] rounded-lg px-3 py-1.5
                         text-sm text-[rgb(var(--text))] text-right
                         border border-[rgb(var(--border))]"
            />
          </div>
        )}
        <ToggleRow
          label="Lock admins"
          desc="Apply all rules to admins too"
          value={data?.lock_admins}
          onChange={v => save({ lock_admins: v })}
        />
        <ToggleRow
          label="Block unofficial Telegram apps"
          desc="Ban accounts sending via unofficial clients"
          value={data?.unofficial_tg_lock}
          onChange={v => save({ unofficial_tg_lock: v })}
        />
        <ToggleRow
          label="Ban bot inviters"
          desc="Ban whoever adds a bot to the group"
          value={data?.bot_inviter_ban}
          onChange={v => save({ bot_inviter_ban: v })}
        />
        <ToggleRow
          label="REGEX active"
          desc="Apply REGEX pattern checks"
          value={data?.regex_active}
          onChange={v => save({ regex_active: v })}
        />
      </Section>
    </div>
  )
}

// ── Constants ──────────────────────────────────────────────────────────────

const DEFAULT_RULE_ORDER = [
  "link","website","username","hashtag","photo","video",
  "sticker","gif","forward","forward_channel","text","voice",
  "audio","file","software","poll","slash","no_caption",
  "emoji_only","emoji","game","english","arabic_farsi",
  "reply","external_reply","bot","unofficial_tg","spoiler"
]

const RULE_LABELS = {
  link:             "🔗 Telegram Links",
  website:          "🌐 External Websites",
  username:         "@ Usernames",
  hashtag:          "# Hashtags",
  photo:            "📷 Photos",
  video:            "🎬 Videos",
  sticker:          "🎭 Stickers",
  gif:              "GIF Animations",
  forward:          "↩️ Forwarded Messages",
  forward_channel:  "📢 Forwards from Channels",
  text:             "💬 Text Messages",
  voice:            "🎤 Voice Messages",
  audio:            "🎵 Audio Files",
  file:             "📄 Files",
  software:         "📱 APK/Software",
  poll:             "📊 Polls",
  slash:            "/ Bot Commands",
  no_caption:       "🖼 Posts without Caption",
  emoji_only:       "😀 Emoji-only Messages",
  emoji:            "😊 Any Emoji",
  game:             "🎮 Games",
  english:          "🔤 English Text",
  arabic_farsi:     "عربی Arabic/Farsi",
  reply:            "↩ Replies",
  external_reply:   "↩ External Replies",
  bot:              "🤖 Bot Additions",
  unofficial_tg:    "📱 Unofficial Telegram",
  spoiler:          "|| Spoilers",
}
