"""
Input Sanitization Module

Provides comprehensive security functions to prevent:
- SQL Injection
- XSS Attacks
- Command Injection
- Spam/Flooding
- Malicious code injection
"""

import re
import logging
from typing import Optional, List, Dict, Any
from html import escape

log = logging.getLogger(__name__)


# ============================================================================
# SQL Injection Detection Patterns
# ============================================================================
SQL_INJECTION_PATTERNS = [
    r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|UNION|EXEC|EXECUTE)\b)',
    r'(--|#|\/\*|\*\/)',  # SQL comments
    r'(\bor\b\s+\d+\s*=\s*\d+)',  # OR 1=1
    r'(\band\b\s+\d+\s*=\s*\d+)',  # AND 1=1
    r'(\'\s*(OR|AND)\s*\'.*?\')',  # ' OR '1'='1
    r'(;|\||&&)',  # Command separators
    r'(\b(WAITFOR\s+DELAY|BENCHMARK|SLEEP)\b)',  # Time-based injection
    r'(\b(INFORMATION_SCHEMA|SYS\.)\b)',  # System tables
    r'(\bXOR\b|\bCASE\s+WHEN\b)',  # Advanced injection
    r'(\\x[0-9a-fA-F]{2})',  # Hex encoding
]

# Compiled regex for performance
SQL_INJECTION_REGEX = re.compile('|'.join(SQL_INJECTION_PATTERNS), re.IGNORECASE)


# ============================================================================
# XSS/HTML Injection Detection Patterns
# ============================================================================
XSS_PATTERNS = [
    r'<\s*script[^>]*>',  # <script> tags
    r'<\s*iframe[^>]*>',  # <iframe> tags
    r'on\w+\s*=',  # Event handlers (onclick, onload, etc.)
    r'javascript:',  # JavaScript protocol
    r'data:',  # Data protocol (potential for code injection)
    r'vbscript:',  # VBScript protocol
    r'fromCharCode',  # Common obfuscation
    r'eval\s*\(',  # eval() function
    r'expression\s*\(',  # CSS expression
    r'@import',  # CSS import
    r'<\s*object[^>]*>',  # <object> tags
    r'<\s*embed[^>]*>',  # <embed> tags
]

XSS_REGEX = re.compile('|'.join(XSS_PATTERNS), re.IGNORECASE)


# ============================================================================
# Command Injection Detection Patterns
# ============================================================================
COMMAND_INJECTION_PATTERNS = [
    r'[;&|`$]',  # Shell command separators
    r'\$\(',  # Command substitution
    r'\n',  # Newline (command chaining)
    r'\r',  # Carriage return
    r'\t',  # Tab (command separator)
    r'\\[\\nrt]',  # Escaped separators
]

COMMAND_INJECTION_REGEX = re.compile('|'.join(COMMAND_INJECTION_PATTERNS))


# ============================================================================
# Spam Detection Patterns
# ============================================================================
SPAM_PATTERNS = [
    r'(.)\1{10,}',  # Repeated characters (11+ times)
    r'(https?:\/\/[^\s]+)\1{3,}',  # Same URL repeated 4+ times
    r'(?:^|\s)(\S+)(?:\s+\1){4,}',  # Same word repeated 5+ times
]

SPAM_REGEX = re.compile('|'.join(SPAM_PATTERNS), re.IGNORECASE)


# ============================================================================
# Dangerous Keywords
# ============================================================================
DANGEROUS_KEYWORDS = [
    'password', 'passwd', 'pwd', 'secret', 'token', 'api_key',
    'credit_card', 'card_number', 'cvv', 'ssn', 'social_security',
    'drop table', 'delete from', 'truncate', 'grant all', 'revoke',
    'system(', 'exec(', 'eval(', 'passthru(', 'shell_exec(',
    'php://', 'expect://', 'file://',
]


# ============================================================================
# Main Sanitization Functions
# ============================================================================

def detect_sql_injection(text: str) -> tuple[bool, List[str]]:
    """
    Detect SQL injection patterns in input.
    
    Returns:
        tuple: (is_injection, list_of_patterns_found)
    """
    if not text or not isinstance(text, str):
        return False, []
    
    matches = []
    
    for pattern in SQL_INJECTION_PATTERNS:
        found = re.findall(pattern, text, re.IGNORECASE)
        if found:
            matches.extend([f"{m}" for m in found if m])
    
    return len(matches) > 0, list(set(matches))


def detect_xss(text: str) -> tuple[bool, List[str]]:
    """
    Detect XSS/HTML injection patterns in input.
    
    Returns:
        tuple: (is_xss, list_of_patterns_found)
    """
    if not text or not isinstance(text, str):
        return False, []
    
    matches = []
    
    for pattern in XSS_PATTERNS:
        found = re.findall(pattern, text, re.IGNORECASE)
        if found:
            matches.extend([f"{m}" for m in found if m])
    
    return len(matches) > 0, list(set(matches))


def detect_command_injection(text: str) -> tuple[bool, List[str]]:
    """
    Detect command injection patterns in input.
    
    Returns:
        tuple: (is_injection, list_of_patterns_found)
    """
    if not text or not isinstance(text, str):
        return False, []
    
    matches = COMMAND_INJECTION_REGEX.findall(text)
    return len(matches) > 0, list(set(matches))


def detect_spam(text: str) -> tuple[bool, str]:
    """
    Detect spam patterns in input.
    
    Returns:
        tuple: (is_spam, reason)
    """
    if not text or not isinstance(text, str):
        return False, ""
    
    # Check for character repetition
    if re.search(r'(.)\1{20,}', text):
        return True, "Excessive character repetition"
    
    # Check for word repetition
    words = text.lower().split()
    word_counts = {}
    for word in words:
        if len(word) > 2:  # Ignore short words
            word_counts[word] = word_counts.get(word, 0) + 1
    
    for word, count in word_counts.items():
        if count >= 10:
            return True, f"Word '{word}' repeated {count} times"
    
    # Check for URL spam
    urls = re.findall(r'https?://[^\s]+', text)
    if len(urls) > 5:
        return True, f"Too many URLs ({len(urls)})"
    
    return False, ""


def detect_dangerous_keywords(text: str) -> List[str]:
    """
    Detect dangerous keywords in input.
    
    Returns:
        list: List of dangerous keywords found
    """
    if not text or not isinstance(text, str):
        return []
    
    text_lower = text.lower()
    found = []
    
    for keyword in DANGEROUS_KEYWORDS:
        if keyword.lower() in text_lower:
            found.append(keyword)
    
    return found


# ============================================================================
# Combined Security Check
# ============================================================================

def validate_input(
    text: str,
    max_length: int = 1000,
    allow_html: bool = False,
    check_sql: bool = True,
    check_xss: bool = True,
    check_command: bool = True,
    check_spam: bool = True,
    check_keywords: bool = True
) -> tuple[bool, str, Dict[str, Any]]:
    """
    Comprehensive input validation.
    
    Args:
        text: Input text to validate
        max_length: Maximum allowed length
        allow_html: Whether HTML is allowed
        check_sql: Check for SQL injection
        check_xss: Check for XSS
        check_command: Check for command injection
        check_spam: Check for spam patterns
        check_keywords: Check for dangerous keywords
    
    Returns:
        tuple: (is_valid, error_message, details)
    """
    if not isinstance(text, str):
        return False, "Input must be a string", {"type": "invalid_type"}
    
    # Length check
    if len(text) > max_length:
        return False, f"Input too long (max {max_length} characters)", {"type": "too_long", "length": len(text)}
    
    # Empty check
    if not text.strip():
        return False, "Input cannot be empty", {"type": "empty"}
    
    # Security checks
    details = {}
    
    if check_sql:
        is_sql, sql_matches = detect_sql_injection(text)
        if is_sql:
            log.warning(f"[SECURITY] SQL injection detected: {sql_matches}")
            return False, "Input contains SQL injection patterns", {"type": "sql_injection", "patterns": sql_matches}
    
    if check_xss and not allow_html:
        is_xss, xss_matches = detect_xss(text)
        if is_xss:
            log.warning(f"[SECURITY] XSS detected: {xss_matches}")
            return False, "Input contains XSS patterns", {"type": "xss", "patterns": xss_matches}
    
    if check_command:
        is_cmd, cmd_matches = detect_command_injection(text)
        if is_cmd:
            log.warning(f"[SECURITY] Command injection detected: {cmd_matches}")
            return False, "Input contains command injection patterns", {"type": "command_injection", "patterns": cmd_matches}
    
    if check_spam:
        is_spam, spam_reason = detect_spam(text)
        if is_spam:
            log.warning(f"[SECURITY] Spam detected: {spam_reason}")
            return False, f"Input appears to be spam: {spam_reason}", {"type": "spam", "reason": spam_reason}
    
    if check_keywords:
        keywords = detect_dangerous_keywords(text)
        if keywords:
            log.warning(f"[SECURITY] Dangerous keywords detected: {keywords}")
            return False, f"Input contains restricted keywords: {', '.join(keywords)}", {"type": "dangerous_keywords", "keywords": keywords}
    
    details["checks_passed"] = ["sql", "xss", "command", "spam", "keywords"]
    return True, "Input is valid", details


# ============================================================================
# Input Sanitization Functions
# ============================================================================

def sanitize_text(text: str, allow_html: bool = False) -> str:
    """
    Sanitize text by removing dangerous patterns.
    
    Args:
        text: Text to sanitize
        allow_html: Whether to preserve HTML tags
    
    Returns:
        str: Sanitized text
    """
    if not isinstance(text, str):
        return ""
    
    sanitized = text
    
    # Remove SQL injection patterns
    for pattern in SQL_INJECTION_PATTERNS:
        sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
    
    # Remove command injection patterns
    sanitized = COMMAND_INJECTION_REGEX.sub('', sanitized)
    
    # Remove XSS patterns (unless HTML is allowed)
    if not allow_html:
        for pattern in XSS_PATTERNS:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        # HTML escape
        sanitized = escape(sanitized)
    else:
        # Still escape dangerous event handlers even if HTML is allowed
        sanitized = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'javascript:', '', sanitized, flags=re.IGNORECASE)
    
    # Remove excessive whitespace
    sanitized = ' '.join(sanitized.split())
    
    return sanitized.strip()


def sanitize_numeric_input(value: Any, min_val: Optional[int] = None, max_val: Optional[int] = None) -> Optional[int]:
    """
    Sanitize numeric input.
    
    Args:
        value: Value to sanitize
        min_val: Minimum allowed value (optional)
        max_val: Maximum allowed value (optional)
    
    Returns:
        int: Sanitized integer or None if invalid
    """
    try:
        num = int(value)
        
        if min_val is not None and num < min_val:
            return min_val
        if max_val is not None and num > max_val:
            return max_val
        
        return num
    except (ValueError, TypeError):
        return None


def sanitize_chat_id(chat_id: Any) -> Optional[int]:
    """
    Sanitize and validate Telegram chat ID.
    
    Args:
        chat_id: Chat ID to sanitize
    
    Returns:
        int: Valid chat ID or None
    """
    try:
        chat_id = int(chat_id)
        # Valid Telegram chat IDs are typically in specific ranges
        # This is a basic check - may need adjustment based on your use case
        if chat_id > 0 or chat_id < -10000000000:
            return chat_id
        return None
    except (ValueError, TypeError):
        return None


def sanitize_user_id(user_id: Any) -> Optional[int]:
    """
    Sanitize and validate Telegram user ID.
    
    Args:
        user_id: User ID to sanitize
    
    Returns:
        int: Valid user ID or None
    """
    try:
        user_id = int(user_id)
        # Valid Telegram user IDs are positive
        if user_id > 0:
            return user_id
        return None
    except (ValueError, TypeError):
        return None


def sanitize_bot_token(token: str) -> str:
    """
    Sanitize bot token input (preserves format but removes dangerous patterns).
    
    Args:
        token: Bot token to sanitize
    
    Returns:
        str: Sanitized token
    """
    if not isinstance(token, str):
        return ""
    
    # Bot tokens are in format: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
    # Only keep alphanumeric and colon
    sanitized = re.sub(r'[^a-zA-Z0-9:_-]', '', token)
    
    return sanitized.strip()


# ============================================================================
# Bulk Validation
# ============================================================================

def validate_multiple_inputs(inputs: Dict[str, Any], rules: Dict[str, Dict[str, Any]]) -> tuple[bool, Dict[str, Any]]:
    """
    Validate multiple inputs with custom rules for each.
    
    Args:
        inputs: Dictionary of input_name -> value
        rules: Dictionary of input_name -> validation_rules
    
    Returns:
        tuple: (all_valid, errors)
    """
    errors = {}
    all_valid = True
    
    for field_name, field_value in inputs.items():
        field_rules = rules.get(field_name, {})
        
        is_valid, error_msg, details = validate_input(
            str(field_value) if field_value is not None else "",
            max_length=field_rules.get('max_length', 1000),
            allow_html=field_rules.get('allow_html', False),
            check_sql=field_rules.get('check_sql', True),
            check_xss=field_rules.get('check_xss', True),
            check_command=field_rules.get('check_command', True),
            check_spam=field_rules.get('check_spam', True),
            check_keywords=field_rules.get('check_keywords', True)
        )
        
        if not is_valid:
            all_valid = False
            errors[field_name] = {
                "message": error_msg,
                "details": details
            }
    
    return all_valid, errors


# ============================================================================
# Rate Limiting Helper (for input-based rate limiting)
# ============================================================================

class InputRateLimiter:
    """
    Simple in-memory rate limiter for input validation.
    """
    
    def __init__(self, max_attempts: int = 10, window_seconds: int = 60):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.attempts: Dict[str, List[float]] = {}
    
    def check_rate_limit(self, identifier: str) -> tuple[bool, int]:
        """
        Check if identifier has exceeded rate limit.
        
        Args:
            identifier: Unique identifier (user_id, IP, etc.)
        
        Returns:
            tuple: (allowed, remaining_attempts)
        """
        import time
        
        now = time.time()
        
        # Clean old attempts
        if identifier in self.attempts:
            self.attempts[identifier] = [
                t for t in self.attempts[identifier]
                if now - t < self.window_seconds
            ]
        else:
            self.attempts[identifier] = []
        
        current_count = len(self.attempts[identifier])
        
        if current_count >= self.max_attempts:
            return False, 0
        
        # Add current attempt
        self.attempts[identifier].append(now)
        
        remaining = self.max_attempts - len(self.attempts[identifier])
        return True, remaining
    
    def reset(self, identifier: str):
        """Reset attempts for identifier."""
        if identifier in self.attempts:
            del self.attempts[identifier]


# Global rate limiter instance
input_rate_limiter = InputRateLimiter(max_attempts=10, window_seconds=60)
