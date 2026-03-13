# Nexus Bot - Complete Command & Configuration Guide

## 📚 Overview

This guide provides comprehensive documentation for all Nexus Bot commands and deep configuration options. For the full interactive experience, use the **Mini App** (via `/panel` command) which provides visual controls for all settings.

---

## 🚀 Getting Started

1. **Add bot to your group** and make it admin
2. **Send /panel** or click the "Open Panel" button to access the Mini App
3. Use the Mini App for deep configuration of all features
4. Refer to this guide for command syntax and usage

---

## 📱 Using the Mini App for Deep Configuration

The Mini App provides comprehensive configuration options that go far beyond simple commands:

### Available Pages:
- **Dashboard** - Overview of group stats and quick actions
- **Commands** - Complete command reference with descriptions
- **AutoMod** - Configure anti-spam, anti-flood, word filters, regex patterns, and more
- **Members** - View and manage group members with trust scores
- **Music** - Control music playback and queue management
- **Modules** - Enable/disable feature modules
- **Settings** - Bot settings and preferences
- **Logs** - View recent bot actions

---

## 🛡️ Moderation Commands

### Basic Moderation
| Command | Usage | Description |
|---------|--------|-------------|
| `/warn` | `/warn [reason]` | Warn a user (reply to their message) |
| `/unwarn` | `/unwarn` | Remove a warning from a user |
| `/warns` | `/warns` | Show warnings for a user |
| `/mute` | `/mute [duration]` | Mute a user (e.g., `10m`, `1h`, `1d`) |
| `/unmute` | `/unmute` | Unmute a user |
| `/ban` | `/ban [reason]` | Ban a user from group (reply to message) |
| `/unban` | `/unban` | Unban a user |
| `/kick` | `/kick [reason]` | Kick a user from group (reply to message) |
| `/purge` | `/purge [count]` | Delete recent messages (max 100) |
| `/kickme` | `/kickme` | Kick yourself from the group |

### Pin Management
| Command | Usage | Description |
|---------|--------|-------------|
| `/pin` | `/pin [silent]` | Pin the replied message (add "silent" for no notification) |
| `/unpin` | `/unpin` | Unpin the current pinned message |
| `/unpinall` | `/unpinall` | Unpin all messages in the group |
| `/repin` | `/repin` | Re-pin the last pinned message |
| `/editpin` | `/editpin [text]` | Edit the pinned message text |
| `/delpin` | `/delpin` | Delete the pinned message |

---

## 🔒 Security & AutoMod Commands

### Toggle Commands (Prefix-based)
| Command | Usage | Description |
|---------|--------|-------------|
| `!antispam` | `!antispam` | Enable anti-spam protection |
| `!!antispam` | `!!antispam` | Disable anti-spam protection |
| `!antiflood` | `!antiflood` | Enable anti-flood (blocks rapid messages) |
| `!!antiflood` | `!!antiflood` | Disable anti-flood |
| `!antilink` | `!antilink` | Enable anti-link (blocks external links) |
| `!!antilink` | `!!antilink` | Disable anti-link |
| `!captcha` | `!captcha` | Enable CAPTCHA verification for new members |
| `!!captcha` | `!!captcha` | Disable CAPTCHA |
| `!antiraid` | `!antiraid` | Enable anti-raid mode (auto-kick join floods) |
| `!!antiraid` | `!!antiraid` | Disable anti-raid |

### Deep Configuration (Mini App Only)
Use the **AutoMod page** in the Mini App to configure:
- Flood limits (messages per minute)
- Anti-spam thresholds
- Word filters (blocked keywords)
- Regex patterns (advanced pattern matching)
- User exemption lists
- Custom action rules (warn/mute/kick)
- Priority order for rules
- CAPTCHA settings (timeout, difficulty)
- Anti-raid settings (join rate limits)

### Other Security Commands
| Command | Usage | Description |
|---------|--------|-------------|
| `/slowmode` | `/slowmode [seconds]` | Set slow mode delay (0-300s, 0 = off) |
| `/setflood` | `/setflood [number]` | Set flood message limit |
| `/setpassword` | `/setpassword [word]` | Set group password for new members |
| `/clearpassword` | `/clearpassword` | Remove group password |
| `/addfilter` | `/addfilter [word]` | Add a word to the filter list |
| `/delfilter` | `/delfilter [word]` | Remove a word from filter list |
| `/filters` | `/filters` | List all active word filters |

---

## 👋 Greetings & Messages

| Command | Usage | Description |
|---------|--------|-------------|
| `/setwelcome` | `/setwelcome [message]` | Set welcome message for new members |
| `/setgoodbye` | `/setgoodbye [message]` | Set goodbye message for leavers |
| `/setrules` | `/setrules [rules]` | Set group rules |
| `/welcome` | `/welcome` | Preview the welcome message |
| `/goodbye` | `/goodbye` | Preview the goodbye message |
| `/rules` | `/rules` | Show group rules |
| `/resetwelcome` | `/resetwelcome` | Reset welcome to default |
| `/resetgoodbye` | `/resetgoodbye` | Reset goodbye to default |
| `/resetrules` | `/resetrules` | Reset rules to default |

### Message Variables
Use these variables in welcome/goodbye messages:
- `{first_name}` - User's first name
- `{username}` - User's username
- `{group_name}` - Group name
- `{member_count}` - Current member count

---

## 🎵 Music Commands

| Command | Usage | Description |
|---------|--------|-------------|
| `/play` | `/play [url/query]` | Play music or add to queue |
| `/playnow` | `/playnow [url]` | Play immediately, skip the queue |
| `/pause` | `/pause` | Pause playback |
| `/resume` | `/resume` | Resume playback |
| `/skip` | `/skip` | Skip current track |
| `/stop` | `/stop` | Stop and clear queue |
| `/queue` | `/queue` | Show current music queue |
| `/volume` | `/volume [0-200]` | Set volume level (default: 100) |
| `/loop` | `/loop` | Toggle loop current track |
| `/musicmode` | `/musicmode [all\|admins]` | Set who can use music commands |

### Supported Music Sources
- YouTube (URL or search query)
- SoundCloud (URL only)
- Spotify (URL only - requires Spotify Premium)
- Direct audio files
- Voice messages

---

## 🎮 Fun Commands

| Command | Usage | Description |
|---------|--------|-------------|
| `/afk` | `/afk [reason]` | Set AFK status |
| `/back` | `/back` | Clear AFK status |
| `/poll` | `/poll [question]` | Create a yes/no poll |
| `/dice` | `/dice` | Roll a dice |
| `/coin` | `/coin` | Flip a coin |
| `/choose` | `/choose opt1\|opt2` | Randomly choose between options |
| `/8ball` | `/8ball [question]` | Magic 8-ball response |
| `/roll` | `/roll [max]` | Roll random number (1 to max) |
| `/joke` | `/joke` | Get a random joke |
| `/quote` | `/quote` | Get an inspirational quote |
| `/roast` | `/roast` | Playful roast (reply to someone) |
| `/compliment` | `/compliment` | Give a compliment (reply to someone) |
| `/calc` | `/calc [expression]` | Simple calculator (e.g., `5 + 3`) |

---

## ⚡ Admin Tools

| Command | Usage | Description |
|---------|--------|-------------|
| `/announce` | `/announce [message]` | Send announcement to group |
| `/pinmessage` | `/pinmessage [text]` | Create and pin custom message |
| `/admininfo` | `/admininfo` | Show detailed group information |
| `/exportsettings` | `/exportsettings` | Export settings as JSON |
| `/importsettings` | `/importsettings [json]` | Import settings from JSON |
| `/backup` | `/backup` | Create group backup |
| `/cleardata` | `/cleardata` | Clear bot data for group |
| `/admintimeout` | `/admintimeout [user] [mins]` | Timeout a user temporarily |

---

## 📢 Channel Management

| Command | Usage | Description |
|---------|--------|-------------|
| `/channelpost` | `/channelpost [message]` | Post to linked channel |
| `/schedulepost` | `/schedulepost [time] [message]` | Schedule a channel post |
| `/approvepost` | `/approvepost` | Approve scheduled post |
| `/cancelpost` | `/cancelpost` | Cancel scheduled post |
| `/editpost` | `/editpost [id] [message]` | Edit scheduled post |
| `/deletepost` | `/deletepost [id]` | Delete scheduled post |

---

## ⭐ Economy Commands

| Command | Usage | Description |
|---------|--------|-------------|
| `/redeem` | `/redeem [code]` | Redeem a promo code |
| `/referral` | `/referral` | Get referral link and stats |
| `/mystars` | `/mystars` | Show Stars balance and purchases |

---

## 👥 Public Commands (All Members)

| Command | Usage | Description |
|---------|--------|-------------|
| `/rules` | `/rules` | Show group rules |
| `/time` | `/time` | Show current group time |
| `/id` | `/id` | Get your user ID and chat ID |
| `/report` | `/report [reason]` | Report a message to admins (reply to message) |
| `/adminlist` | `/adminlist` | List all group admins |
| `/staff` | `/staff` | Alias for /adminlist |
| `/invitelink` | `/invitelink` | Get group invite link |
| `/groupinfo` | `/groupinfo` | Show group statistics and features |
| `/kickme` | `/kickme` | Kick yourself from group |

---

## 🔧 Utility Commands

| Command | Usage | Description |
|---------|--------|-------------|
| `/panel` | `/panel` | Open Mini App management panel |
| `/help` | `/help` | Show help message with command list |
| `/info` | `/info` | Show basic group information |
| `/admins` | `/admins` | List group admins (alias) |
| `/stats` | `/stats` | Show group statistics |
| `/privacy` | `/privacy` | View privacy policy |

---

## 🔧 Deep Configuration via Mini App

### AutoMod Page
Configure these advanced options:
- **Anti-Flood**: Set messages per minute threshold, action (warn/mute/kick)
- **Anti-Spam**: Configure spam detection sensitivity
- **Anti-Link**: Allow/block specific domains, configure regex patterns
- **Word Filters**: Add/remove blocked words, set case sensitivity
- **Regex Patterns**: Advanced pattern matching with custom responses
- **Rule Priority**: Set which rules take precedence
- **Exemptions**: Whitelist users/groups from specific rules
- **CAPTCHA**: Configure timeout, attempts, custom messages

### Modules Page
Enable/disable feature modules:
- Anti-Flood
- Anti-Spam
- Anti-Link
- CAPTCHA
- Welcome Messages
- Rules Display
- Music
- And more...

### Settings Page
Configure:
- Bot appearance (theme colors)
- Language preferences
- Notification settings
- Admin permissions
- And more...

---

## 💡 Tips

1. **Use the Mini App** for complex configurations - it's much easier than memorizing all commands
2. **Reply to messages** for moderation commands (/warn, /ban, /kick)
3. **Use time units** for durations: `10s`, `5m`, `2h`, `1d`
4. **Test filters** before enabling them in production
5. **Backup your settings** using /exportsettings before making major changes
6. **Check the AutoMod page** to see which rules are active and in what order

---

## 🆘 Need Help?

- Send `/help` in any chat for quick reference
- Use `/panel` to open the Mini App for visual configuration
- Check the **Commands** page in the Mini App for complete documentation
- Join the support group for assistance

---

⚡ **Powered by Nexus**
