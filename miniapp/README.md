# Nexus Mini App

The Nexus Bot Mini App - a comprehensive group management interface built with Vanilla JS + Zustand.

## 📁 Structure

```
miniapp/
├── styles/
│   ├── tokens.css       # Design system tokens (colors, spacing, typography)
│   ├── layout.css      # Mobile-first responsive layout
│   └── animations.css  # All keyframe animations
├── lib/
│   ├── components.js           # Reusable UI components
│   ├── sse.js                # Real-time SSE client
│   ├── notifications.js       # Notification center
│   ├── group_switcher.js      # Multi-group switcher
│   ├── theme.js              # Theme engine (dark/light + accent)
│   ├── bulk_actions.js       # Bulk member actions
│   ├── rule_templates.js      # Preset automod templates
│   └── mtproto_auth.js       # Telegram MTProto auth
├── src/pages/
│   ├── automod.js            # AutoMod configuration page
│   ├── commands.js           # Commands reference page
│   └── music.js              # Music player control page
├── store/
│   └── index.js              # Zustand store
├── index.html               # Main app entry point
└── package.json
```

## 🎨 Design System

### Tokens (tokens.css)
- Single source of truth for all visual tokens
- Dark theme by default, with light theme support
- Custom accent colors via CSS variables
- Responsive typography scale

### Layout (layout.css)
- Mobile-first approach
- Desktop sidebar navigation (768px+)
- Bottom navigation on mobile
- CSS Grid for responsive layouts
- Two-column panel support

### Components (lib/components.js)
Pure JS factory functions returning DOM elements:
- `Card` - Card container with title/actions
- `Toggle` - Switch component
- `Badge` - Status badges
- `Avatar` - User avatar with initials
- `Skeleton` - Loading placeholder
- `Toast` - Notification toasts
- `Modal` - Centered modal dialog
- `BottomSheet` - Mobile-friendly sheet
- `StatCard` - Statistics display
- `MemberRow` - Member list row with actions
- `RuleRow` - Draggable rule row
- `ProgressBar` - Progress indicator
- `SearchInput` - Search field
- `TabBar` - Tab navigation
- `EmptyState` - Empty state display
- `Spinner` - Loading spinner

## 🔔 Features

### Real-time SSE (lib/sse.js)
- Auto-reconnecting SSE client
- Exponential backoff retry
- Typed event handlers
- Keepalive pings (25s)

### Notification Center (lib/notifications.js)
- In-app notification feed
- Unread badge counter
- BottomSheet on mobile
- Caps at 100 items

### Multi-Group Switcher (lib/group_switcher.js)
- Group dropdown in topbar
- Persists active group
- Updates store on switch
- Syncs with /api/me

### Theme Engine (lib/theme.js)
- Dark/Light toggle
- Custom accent colors
- Syncs with Telegram theme
- Persists in localStorage

### Bulk Actions (lib/bulk_actions.js)
- Floating action bar
- Multi-member selection
- Ban/Mute/Kick/Approve
- Limits to 50 members

### Rule Templates (lib/rule_templates.js)
- One-tap presets
- Gaming, Study, Crypto, Community, etc.
- Bulk settings apply
- Via `/api/groups/{chat_id}/settings/bulk`

## 🌐 Backend

### SSE Endpoint (`/api/events`)
Server-Sent Events for real-time updates:
- `member_join` - New member joined
- `member_leave` - Member left
- `bot_action` - Bot took action
- `settings_change` - Settings updated
- `notification` - System notification
- `stat_update` - Stats changed
- `bulk_action` - Bulk operation complete

### Bulk Actions Endpoint (`/api/groups/{chat_id}/members/bulk`)
Execute actions on multiple members:
- `ban` - Ban users
- `mute` - Mute users
- `kick` - Kick users
- `approve` - Approve users
- `unapprove` - Unapprove users
- `warn` - Warn users

## 💾 Store (Zustand)

Global state management with slices:
- User & Auth context
- Active group/chat ID
- Navigation state
- Settings
- Members list
- Logs
- Stats
- Modules
- Automod rules
- Bulk selection
- UI state (loading, errors)
- SSE connection status

## 🚀 Usage

### Importing Components
```javascript
import { Card, Toggle, Badge } from './lib/components.js';

const card = Card({
  title: 'My Card',
  subtitle: 'Description',
  actions: Toggle({ checked: true, onChange: (v) => console.log(v) })
});
document.body.appendChild(card);
```

### Using the Store
```javascript
import { useStore } from './store/index.js';

// Get state
const state = useStore.getState();
console.log(state.activeChatId);

// Set state
useStore.setState({ activePage: 'members' });

// Subscribe to changes
useStore.subscribe(state => console.log('State changed:', state));
```

### SSE Events
```javascript
import { SSEClient } from './lib/sse.js';

const sse = new SSEClient();
sse.on('member_join', (data) => {
  console.log('New member:', data);
});
sse.connect(chatId);
```

### Theme Customization
```javascript
import { ThemeEngine } from './lib/theme.js';

// Initialize
ThemeEngine.init();

// Toggle theme
ThemeEngine.setTheme('light');

// Set accent
ThemeEngine.setAccent('#ff6b6b');

// Render picker
ThemeEngine.renderPicker(containerEl, (color) => {
  console.log('Accent selected:', color);
});
```

## 📱 Responsive Breakpoints

- **Mobile**: < 768px - Bottom navigation
- **Tablet**: 768px - 1023px - Sidebar + single column
- **Desktop**: 1024px+ - Sidebar + two-column panels

## 🎯 Browser Support

- Chrome 90+
- Safari 15+
- Firefox 88+
- Edge 90+

Requires:
- CSS Grid
- CSS Custom Properties
- EventSource (SSE)
- ResizeObserver

## ⚡ Performance

- Minimal bundle size (Vanilla JS)
- CSS-based animations
- Lazy loading with IntersectionObserver
- Efficient re-renders via Zustand
- SSE for real-time updates

## 🔐 Authentication

Uses Telegram WebApp initData for auth:
- Validated via `/api/auth` endpoints
- MTProto for userbot session export
- Secure token storage in backend

## 🆕 New Features

### Commands Page (`/commands`)
Comprehensive command reference with:
- **Searchable** command database
- **7 categories**: Moderation, Security, Greetings, Music, Fun, Admin Tools, Utilities
- **50+ commands** documented
- Mobile-friendly card layout

### Music Page (`/music`)
Full music player control panel:
- **Now Playing** display with track info
- **Playback controls**: Play, Pause, Skip, Stop
- **Queue visualization** with track list
- **Volume control** slider
- **Quick action** buttons
- **Music settings**: Play mode (all/admins)

### Enhanced Navigation
- **9 pages total**: Dashboard, AutoMod, Members, Music, Commands, Modules, Settings, Logs
- Bottom navigation on mobile
- Sidebar navigation on desktop

## 🌐 Backend API Endpoints

### Music API (`/api/music`)
- `GET /{chat_id}/queue` - Get current queue
- `POST /{chat_id}/command` - Send control commands (play, pause, skip, etc.)
- `PUT /{chat_id}/settings` - Update music settings

### Group Management (`/api/groups`)
- `GET /{chat_id}/members` - List members
- `POST /{chat_id}/members/bulk` - Bulk actions
- `GET /{chat_id}/logs` - Activity logs
- `GET /{chat_id}/analytics` - Statistics and charts
- `PUT /{chat_id}/settings` - Update settings
- `PUT /{chat_id}/settings/bulk` - Bulk settings apply

### Boost API (`/api/groups/{chat_id}/boost`)
- `GET /config` - Boost configuration
- `PUT /config` - Update boost settings
- `GET /stats` - Boost statistics
- `GET /records` - Member boost records
- `POST /credits/request` - Request manual add credit
- `POST /unlock/{user_id}` - Manually unlock member

## 📝 Bot Commands (50+)

### Moderation
/warn, /unwarn, /warns, /mute, /unmute, /ban, /unban, /kick, /purge, /pin, /unpin

### Security
!antispam, !antiflood, !antilink, !captcha, !antiraid, /slowmode, /setflood, /addfilter, /delfilter

### Greetings
/setwelcome, /setgoodbye, /welcome, /goodbye, /setrules, /rules

### Music
/play, /playnow, /pause, /resume, /skip, /stop, /queue, /volume, /loop, /musicmode

### Fun 🎮 NEW
/afk, /back, /poll, /dice, /coin, /choose, /8ball, /roll, /joke, /quote, /roast, /compliment, /calc

### Admin Tools 🆕 NEW
/announce, /pinmessage, /slowmode, /filters, /addfilter, /delfilter, /setflood, /exportsettings, /importsettings, /admininfo, /cleardata

## 🛠️ Implemented Features

- ✅ Advanced Automod Engine
- ✅ Anti-Raid + CAPTCHA + Approval
- ✅ Word Filters
- ✅ Music Player with Queue Management
- ✅ Member Boost System
- ✅ Command Reference
- ✅ Real-time Analytics
- ✅ Bulk Member Actions
- ✅ Settings Import/Export
- ✅ 50+ Bot Commands
