# Music Player Quick Start Guide

## Getting Started with the Music Player

### Prerequisites
- GroupGuard bot must be an admin in the group
- Bot must have permission to send messages
- Audio files or voice messages shared in the group

### Basic Usage

#### 1. Play a Song (Reply Method)
```
1. Someone shares an audio file in the group
2. As an admin, reply to that message with: /play
3. The bot will add it to the queue and play it
```

#### 2. Play a Song (Direct Method)
```
1. Upload an audio file with the message: /play
2. The bot will automatically add it to the queue
```

#### 3. View the Queue
```
Type: /queue

Output:
🎵 Music Queue

   Now Playing:
   Song Title

   Up Next:
   1. Next Song
   2. Another Song
```

#### 4. Skip a Track
```
Type: /skip

The bot will:
⏭️ Skip: Song Title
[Play next track]
```

#### 5. Stop and Clear Queue
```
Type: /stop

The bot will:
⏹️ Music stopped and queue cleared
```

### Using the Mini App

#### 1. Open the Music Tab
1. Open the GroupGuard Mini App (Menu button → Open Panel)
2. Click the "🎵 Music" tab at the bottom

#### 2. View Now Playing
- Shows the current track title and artist
- Large music icon for visual feedback

#### 3. Control Playback
Use the control buttons:
- ⏸️ Pause - Pause the current track
- ⏭️ Skip - Jump to next track
- ▶️ Resume - Resume paused track
- ⏹️ Stop - Stop and clear queue

#### 4. View Queue
See upcoming tracks in the queue list with:
- Track position number
- Track title
- Artist name (if available)

### Interactive Controls

#### Using /nowplaying
```
Type: /nowplaying

The bot will show:
🎵 Now Playing:
Song Title
By: Artist Name
Duration: 180s

[⏸️ Pause] [⏭️ Skip]
[📋 Queue] [⏹️ Stop]
```

Click any button to control playback!

### Tips and Best Practices

#### Queue Management
- Add multiple songs at once by replying with /play to each
- Use /queue to see what's coming up
- Skip unwanted tracks with /skip

#### Voice Messages
- Voice messages work just like audio files
- Reply with /play to add voice messages to queue
- Great for playing recorded messages

#### Group Etiquette
- Consider group members when playing music
- Use /stop when requested
- Keep queue lengths reasonable

### Troubleshooting

#### "No music playing" error
- Solution: Add a track to queue with /play first
- Ensure bot is admin in the group

#### Music doesn't auto-play
- Check that queue has more tracks: /queue
- Try playing next track manually

#### Buttons don't work
- Ensure you clicked a button from the bot's message
- Try using text commands instead

### Advanced Usage

#### Building a Playlist
1. Add first song: /play (reply to audio)
2. Add more songs to queue
3. Let it play through automatically

#### Quick Skip
- Click the "⏭️ Skip" button in /nowplaying
- Or type /skip command

#### Emergency Stop
- Type /stop to immediately stop music
- Clears entire queue

## Command Quick Reference

| Command | Action |
|---------|--------|
| `/play` | Add song to queue (reply or send file) |
| `/skip` | Skip current track |
| `/queue` | View the queue |
| `/stop` | Stop and clear queue |
| `/pause` | Pause playback |
| `/resume` | Resume playback |
| `/nowplaying` | Show current track with controls |

## Support

For issues or questions:
1. Check MUSIC_PLAYER.md for detailed documentation
2. Review troubleshooting section above
3. Test with simple commands first

Enjoy your music! 🎵
