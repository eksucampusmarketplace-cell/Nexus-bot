-- Security Events Table
-- Tracks security violations and suspicious activities
CREATE TABLE IF NOT EXISTS security_events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,  -- 'sql_injection', 'xss', 'spam', 'rate_limit', etc.
    severity VARCHAR(20) NOT NULL,     -- 'low', 'medium', 'high', 'critical'
    user_id BIGINT,                      -- Telegram user ID if available
    chat_id BIGINT,                      -- Chat ID if applicable
    ip_address VARCHAR(45),             -- Client IP address
    endpoint VARCHAR(255),              -- API endpoint or bot command
    input_data TEXT,                     -- Sanitized input sample (first 500 chars)
    pattern_matched TEXT,                -- Pattern that triggered the event
    additional_info JSONB,               -- Extra details
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_security_events_user_id ON security_events(user_id);
CREATE INDEX IF NOT EXISTS idx_security_events_chat_id ON security_events(chat_id);
CREATE INDEX IF NOT EXISTS idx_security_events_event_type ON security_events(event_type);
CREATE INDEX IF NOT EXISTS idx_security_events_severity ON security_events(severity);
CREATE INDEX IF NOT EXISTS idx_security_events_created_at ON security_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_events_ip_address ON security_events(ip_address);

-- Blocked Users Table
-- Tracks users who have been temporarily or permanently blocked
CREATE TABLE IF NOT EXISTS blocked_users (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    chat_id BIGINT,                      -- 0 for global blocks, or specific chat
    blocked_by BIGINT,                   -- Admin who blocked the user
    reason VARCHAR(255),
    block_type VARCHAR(20) DEFAULT 'temporary',  -- 'temporary', 'permanent', 'auto'
    blocked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,  -- NULL for permanent blocks
    violation_count INTEGER DEFAULT 1,
    additional_info JSONB
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_blocked_users_user_id ON blocked_users(user_id);
CREATE INDEX IF NOT EXISTS idx_blocked_users_chat_id ON blocked_users(chat_id);
CREATE INDEX IF NOT EXISTS idx_blocked_users_expires_at ON blocked_users(expires_at);
CREATE INDEX IF NOT EXISTS idx_blocked_users_block_type ON blocked_users(block_type);

-- Input Validation Settings Table (per group)
-- Customizes validation rules per group
CREATE TABLE IF NOT EXISTS input_validation_settings (
    id BIGSERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL UNIQUE,
    max_message_length INTEGER DEFAULT 4000,
    max_word_count INTEGER DEFAULT 1000,
    max_url_count INTEGER DEFAULT 5,
    allow_html BOOLEAN DEFAULT FALSE,
    strict_mode BOOLEAN DEFAULT FALSE,  -- Enables stricter validation
    blocked_patterns JSONB,              -- Custom regex patterns to block
    allowed_patterns JSONB,              -- Whitelist patterns
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index
CREATE INDEX IF NOT EXISTS idx_input_validation_settings_chat_id ON input_validation_settings(chat_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for input_validation_settings
CREATE TRIGGER update_input_validation_settings_updated_at
    BEFORE UPDATE ON input_validation_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to clean up old security events (older than 90 days)
CREATE OR REPLACE FUNCTION cleanup_old_security_events()
RETURNS void AS $$
BEGIN
    DELETE FROM security_events
    WHERE created_at < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;
