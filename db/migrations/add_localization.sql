-- ============================================
-- Localization Migration v21
-- ============================================

-- User language preferences
CREATE TABLE IF NOT EXISTS user_lang_prefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL UNIQUE,
    language_code TEXT NOT NULL DEFAULT 'en',  -- en, ar, es, fr, hi, pt, ru, tr, id, de
    auto_detected BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Group default language
-- Stored in groups.settings JSONB as: default_language: "en"

-- Index for language lookups
CREATE INDEX IF NOT EXISTS idx_user_lang_user ON user_lang_prefs(user_id);

-- Language usage stats (for analytics)
CREATE TABLE IF NOT EXISTS language_usage_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    language_code TEXT NOT NULL,
    user_count INTEGER DEFAULT 0,
    group_count INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(language_code)
);

-- Insert default stats for supported languages
INSERT INTO language_usage_stats (language_code) VALUES 
    ('en'), ('ar'), ('es'), ('fr'), ('hi'), ('pt'), ('ru'), ('tr'), ('id'), ('de')
ON CONFLICT (language_code) DO NOTHING;
