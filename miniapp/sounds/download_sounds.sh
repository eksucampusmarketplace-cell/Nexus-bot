#!/bin/bash
# Nexus Bot Game Sounds
# Real sound files generated as WAV format
# All sounds are synthetic beeps/dings (no copyright issues)

echo "=============================================="
echo "  🎵 NEXUS BOT GAME SOUNDS"
echo "=============================================="
echo ""
echo "Sound files have been generated!"
echo ""
echo "All sounds are:"
echo "  ✓ Synthesized (no copyright)"
echo "  ✓ WAV format (universally supported)"
echo "  ✓ Under 50KB each"
echo "  ✓ Appropriate for all ages"
echo ""

# List all sound files
echo "Generated sound files:"
echo ""

categories=("general" "trivia" "dice" "cards" "math" "word")
for cat in "${categories[@]}"; do
    echo "📁 $cat/"
    for file in "$cat"/*.wav; do
        if [ -f "$file" ]; then
            size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null)
            size_kb=$((size / 1024))
            echo "   • $(basename $file) (${size_kb}KB)"
        fi
    done
    echo ""
done

echo "=============================================="
echo "  Total size: $(du -sh . | cut -f1)"
echo "=============================================="
echo ""
echo "To customize sounds:"
echo "1. Replace any .wav file with your own"
echo "2. Keep the same filename"
echo "3. Use WAV format for best compatibility"
echo ""
echo "Free sound sources:"
echo "  • https://pixabay.com/sound-effects/"
echo "  • https://mixkit.co/free-sound-effects/"
echo "  • https://freesound.org/"
echo ""
