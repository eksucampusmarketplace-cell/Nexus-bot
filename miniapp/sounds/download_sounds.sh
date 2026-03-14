#!/bin/bash
# Sound downloader for Nexus Bot games
# Downloads royalty-free sounds from free sources
# All sounds are: free for commercial use, under 200KB, MP3 format

set -e

echo "=============================================="
echo "  🎵 Nexus Bot - Game Sounds Downloader"
echo "=============================================="
echo ""
echo "This script downloads free sounds from:"
echo "  - Pixabay.com (CC0 license)"
echo "  - Mixkit.co (free license)"
echo ""
echo "All sounds are:"
echo "  ✓ Free for commercial use"
echo "  ✓ Under 200KB each"
echo "  ✓ MP3 format"
echo "  ✓ Appropriate for all ages"
echo ""

# Base directory
SOUNDS_DIR="$(dirname "$0")"
cd "$SOUNDS_DIR"

# Create directories
mkdir -p general trivia dice cards strategy math word

# Function to download with curl
download_sound() {
    local url="$1"
    local output="$2"
    local description="$3"

    if [ -f "$output" ]; then
        echo "  ✓ $description (already exists)"
        return 0
    fi

    echo "  📥 Downloading: $description..."
    if curl -sL "$url" -o "$output" --max-time 30; then
        local size=$(stat -f%z "$output" 2>/dev/null || stat -c%s "$output" 2>/dev/null || echo "0")
        if [ "$size" -gt 100 ]; then
            echo "  ✓ Downloaded: $description (${size} bytes)"
            return 0
        else
            echo "  ✗ Failed: $description (too small, probably error page)"
            rm -f "$output"
            return 1
        fi
    else
        echo "  ✗ Failed: $description (download error)"
        rm -f "$output"
        return 1
    fi
}

echo ""
echo "📁 General Sounds"
echo "-----------------"

# General UI sounds - using placeholder URLs
# In production, replace with actual URLs from Pixabay/Mixkit

echo "  Note: Replace placeholder URLs with actual sound URLs from:"
echo "  - https://pixabay.com/sound-effects/"
echo "  - https://mixkit.co/free-sound-effects/"
echo ""

# Alternative: Create placeholder files for development
create_placeholder() {
    local file="$1"
    local desc="$2"
    if [ ! -f "$file" ]; then
        echo "  ⚠️  Creating placeholder: $desc"
        # Create a silent/short MP3 placeholder (1 second silence)
        # This is a minimal valid MP3 frame (silent)
        printf '\xff\xfb\x90\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' > "$file"
    fi
}

echo "Creating placeholder sound files for development..."
echo ""

# General sounds
create_placeholder "general/click.mp3" "Click sound"
create_placeholder "general/levelup.mp3" "Level up sound"
create_placeholder "general/gameover.mp3" "Game over sound"
create_placeholder "general/victory.mp3" "Victory sound"
create_placeholder "general/countdown.mp3" "Countdown sound"
create_placeholder "general/tick.mp3" "Tick sound"
create_placeholder "general/daily_bonus.mp3" "Daily bonus sound"

# Trivia sounds
create_placeholder "trivia/correct1.mp3" "Correct answer 1"
create_placeholder "trivia/correct2.mp3" "Correct answer 2"
create_placeholder "trivia/correct3.mp3" "Correct answer 3"
create_placeholder "trivia/wrong1.mp3" "Wrong answer 1"
create_placeholder "trivia/wrong2.mp3" "Wrong answer 2"
create_placeholder "trivia/timeout.mp3" "Timeout sound"
create_placeholder "trivia/suspense.mp3" "Suspense sound"
create_placeholder "trivia/final_answer.mp3" "Final answer sound"

# Dice sounds
create_placeholder "dice/roll1.mp3" "Dice roll 1"
create_placeholder "dice/roll2.mp3" "Dice roll 2"
create_placeholder "dice/coins.mp3" "Coins sound"
create_placeholder "dice/jackpot.mp3" "Jackpot sound"
create_placeholder "dice/loss.mp3" "Loss sound"

# Card sounds
create_placeholder "cards/flip.mp3" "Card flip"
create_placeholder "cards/shuffle.mp3" "Card shuffle"
create_placeholder "cards/deal.mp3" "Card deal"
create_placeholder "cards/win.mp3" "Card win"
create_placeholder "cards/lose.mp3" "Card lose"

# Strategy sounds
create_placeholder "strategy/move.mp3" "Move sound"
create_placeholder "strategy/attack.mp3" "Attack sound"
create_placeholder "strategy/build.mp3" "Build sound"
create_placeholder "strategy/defeat.mp3" "Defeat sound"

# Math sounds
create_placeholder "math/correct.mp3" "Math correct"
create_placeholder "math/wrong.mp3" "Math wrong"
create_placeholder "math/timeup.mp3" "Math time up"

# Word sounds
create_placeholder "word/correct.mp3" "Word correct"
create_placeholder "word/wrong.mp3" "Word wrong"
create_placeholder "word/hint.mp3" "Hint sound"
create_placeholder "word/complete.mp3" "Word complete"

echo ""
echo "=============================================="
echo "  ✅ Sound files created!"
echo "=============================================="
echo ""
echo "⚠️  IMPORTANT: These are SILENT PLACEHOLDERS"
echo ""
echo "To get actual sounds:"
echo ""
echo "1. Visit https://pixabay.com/sound-effects/"
echo "2. Search for sounds like:"
echo "   - 'correct answer'"
echo "3. Download MP3 files"
echo "4. Replace the placeholder files"
echo ""
echo "Recommended sounds to download:"
echo ""
echo "General (Pixabay):"
echo "  - 'click' or 'button click'"
echo "  - 'success' or 'win'"
echo "  - 'game over'"
echo "  - 'level up'"
echo "  - 'countdown' or 'tick'"
echo ""
echo "Trivia (Mixkit):"
echo "  - 'correct answer' variants"
echo "  - 'wrong answer' variants"
echo "  - 'suspense' or 'thinking'"
echo ""
echo "All sounds should be:"
echo "  - Under 200KB"
echo "  - MP3 format"
echo "  - CC0 or free commercial license"
echo ""

# List created files
echo "Created files:"
find . -name "*.mp3" -type f | sort | while read f; do
    size=$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo "0")
    echo "  $f (${size} bytes)"
done

echo ""
echo "=============================================="
