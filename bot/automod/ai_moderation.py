"""
bot/automod/ai_moderation.py

AI Auto-Moderation — heuristic-based toxicity and spam detection
beyond simple regex patterns.

Uses weighted scoring across multiple signals:
  - Toxic word/phrase detection with severity levels
  - ALL CAPS ratio detection
  - Excessive punctuation/emoji spam
  - URL density scoring
  - Repetition pattern detection
  - Character entropy analysis (keyboard spam detection)

No external API dependency — runs entirely locally.

Log prefix: [AI_MOD]
"""

import logging
import math
import re
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("ai_mod")

# Severity-weighted toxic patterns (weight 0.0-1.0)
TOXIC_PATTERNS = [
    # High severity
    (re.compile(r"\b(kill\s+your\s*self|kys)\b", re.I), 0.95),
    (re.compile(r"\b(go\s+die|hope\s+you\s+die)\b", re.I), 0.90),
    (re.compile(r"\b(ni[g]+[ae]r?|f[a@]g+[o0]?t)\b", re.I), 0.95),
    # Medium severity
    (re.compile(r"\b(retard|retarded)\b", re.I), 0.60),
    (re.compile(r"\b(shut\s+up|stfu)\b", re.I), 0.30),
    (re.compile(r"\b(idiot|moron|dumb\s*ass)\b", re.I), 0.40),
    (re.compile(r"\b(loser|pathetic|worthless)\b", re.I), 0.35),
    # Threats
    (re.compile(r"\b(i('ll|m\s+going\s+to)\s+(kill|hurt|find)\s+you)\b", re.I), 0.90),
    (re.compile(r"\b(doxx|swat)\b", re.I), 0.85),
]

# Spam patterns
SPAM_PATTERNS = [
    (re.compile(r"(https?://\S+)", re.I), 0.15),  # per URL
    (re.compile(r"@\w+", re.I), 0.05),  # per mention
    (re.compile(r"(earn\s+money|make\s+\$|free\s+crypto|click\s+here)", re.I), 0.70),
    (re.compile(r"(join\s+now|limited\s+offer|act\s+fast|dm\s+me)", re.I), 0.40),
    (re.compile(r"(t\.me/|discord\.gg/|bit\.ly/)", re.I), 0.50),
]


@dataclass
class AIModResult:
    """Result of AI moderation analysis."""

    score: float  # 0.0 to 1.0, where 1.0 = definitely toxic/spam
    triggered: bool
    reasons: list
    category: str  # 'toxicity', 'spam', 'clean'


def analyze_message(text: str, sensitivity: float = 0.7) -> AIModResult:
    """
    Analyze a message for toxicity and spam using heuristic scoring.

    Args:
        text: The message text to analyze
        sensitivity: Threshold for triggering (0.0-1.0, default 0.7)

    Returns:
        AIModResult with score, triggered flag, reasons, and category
    """
    if not text or len(text.strip()) < 3:
        return AIModResult(score=0.0, triggered=False, reasons=[], category="clean")

    scores = []
    reasons = []

    # 1. Toxic pattern matching
    toxic_score = _check_toxic_patterns(text)
    if toxic_score > 0:
        scores.append(("toxicity", toxic_score))
        reasons.append(f"toxic_patterns:{toxic_score:.2f}")

    # 2. Spam pattern matching
    spam_score = _check_spam_patterns(text)
    if spam_score > 0:
        scores.append(("spam", spam_score))
        reasons.append(f"spam_patterns:{spam_score:.2f}")

    # 3. ALL CAPS ratio
    caps_score = _check_caps_ratio(text)
    if caps_score > 0:
        scores.append(("caps", caps_score))
        reasons.append(f"caps_ratio:{caps_score:.2f}")

    # 4. Excessive punctuation / emoji
    punct_score = _check_excessive_punctuation(text)
    if punct_score > 0:
        scores.append(("punctuation", punct_score))
        reasons.append(f"punctuation:{punct_score:.2f}")

    # 5. Repetition detection
    repeat_score = _check_repetition(text)
    if repeat_score > 0:
        scores.append(("repetition", repeat_score))
        reasons.append(f"repetition:{repeat_score:.2f}")

    # 6. Character entropy (keyboard spam)
    entropy_score = _check_low_entropy(text)
    if entropy_score > 0:
        scores.append(("entropy", entropy_score))
        reasons.append(f"low_entropy:{entropy_score:.2f}")

    if not scores:
        return AIModResult(score=0.0, triggered=False, reasons=[], category="clean")

    # Weighted combination — max-based with boost from multiple signals
    max_score = max(s[1] for s in scores)
    avg_score = sum(s[1] for s in scores) / len(scores)
    final_score = max_score * 0.7 + avg_score * 0.3

    # Determine category
    toxic_total = sum(s[1] for s in scores if s[0] in ("toxicity", "caps"))
    spam_total = sum(s[1] for s in scores if s[0] in ("spam", "repetition"))
    category = "toxicity" if toxic_total >= spam_total else "spam"

    triggered = final_score >= sensitivity

    if triggered:
        log.info(
            f"[AI_MOD] Triggered | score={final_score:.2f} "
            f"sensitivity={sensitivity} cat={category} reasons={reasons}"
        )

    return AIModResult(
        score=round(final_score, 3),
        triggered=triggered,
        reasons=reasons,
        category=category,
    )


def _check_toxic_patterns(text: str) -> float:
    """Check for toxic words/phrases with severity weighting."""
    max_score = 0.0
    for pattern, weight in TOXIC_PATTERNS:
        if pattern.search(text):
            max_score = max(max_score, weight)
    return max_score


def _check_spam_patterns(text: str) -> float:
    """Check for spam indicators."""
    total = 0.0
    for pattern, weight in SPAM_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            total += weight * len(matches)
    return min(total, 1.0)


def _check_caps_ratio(text: str) -> float:
    """Check ALL CAPS ratio. Short messages are exempt."""
    alpha_chars = [c for c in text if c.isalpha()]
    if len(alpha_chars) < 10:
        return 0.0
    upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
    if upper_ratio > 0.8:
        return 0.5
    if upper_ratio > 0.6:
        return 0.25
    return 0.0


def _check_excessive_punctuation(text: str) -> float:
    """Check for excessive punctuation or emoji spam."""
    if len(text) < 5:
        return 0.0

    # Count repeated punctuation
    repeated_punct = len(re.findall(r"[!?]{3,}", text))
    if repeated_punct >= 2:
        return 0.4

    # Count emoji density
    emoji_pattern = re.compile(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        r"\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+"
    )
    emojis = emoji_pattern.findall(text)
    total_emoji_chars = sum(len(e) for e in emojis)
    if len(text) > 0 and total_emoji_chars / len(text) > 0.5:
        return 0.3

    return 0.0


def _check_repetition(text: str) -> float:
    """Detect repeated words/characters."""
    words = text.lower().split()
    if len(words) < 4:
        return 0.0

    # Check word repetition
    unique_words = set(words)
    if len(words) > 5 and len(unique_words) / len(words) < 0.3:
        return 0.6

    # Check character repetition (e.g., "aaaaaa")
    char_repeats = re.findall(r"(.)\1{4,}", text)
    if len(char_repeats) >= 2:
        return 0.5

    return 0.0


def _check_low_entropy(text: str) -> float:
    """
    Detect keyboard spam via character entropy.
    Very low entropy = random key mashing.
    """
    clean = re.sub(r"\s+", "", text.lower())
    if len(clean) < 10:
        return 0.0

    # Calculate Shannon entropy
    freq = {}
    for c in clean:
        freq[c] = freq.get(c, 0) + 1

    entropy = 0.0
    for count in freq.values():
        p = count / len(clean)
        if p > 0:
            entropy -= p * math.log2(p)

    # Normal text has entropy ~3.5-4.5 bits
    # Keyboard spam has entropy ~2.0-3.0
    if entropy < 2.0:
        return 0.6
    if entropy < 2.5:
        return 0.3
    return 0.0
