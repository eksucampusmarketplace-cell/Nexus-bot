-- ============================================
-- Community Vote Migration v21
-- ============================================

-- Community vote log (audit trail for all vote outcomes)
CREATE TABLE IF NOT EXISTS community_vote_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    target_user_id BIGINT NOT NULL,
    scam_type TEXT NOT NULL,  -- lottery, crypto_pump, urgency, recovery, job, airdrop, manual
    trigger_text TEXT,  -- The text that triggered auto-detection
    vote_message_id BIGINT,
    
    -- Vote counts
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0,
    abstentions INTEGER DEFAULT 0,
    
    -- Config at time of vote
    threshold INTEGER DEFAULT 5,  -- votes needed for action
    timeout_minutes INTEGER DEFAULT 10,
    action TEXT DEFAULT 'kick',  -- mute, kick, ban, delete
    
    -- Outcome
    result TEXT,  -- passed, failed, timeout, cancelled
    action_taken TEXT,  -- the action that was actually taken
    action_timestamp TIMESTAMPTZ,
    
    -- Metadata
    started_by BIGINT NOT NULL,  -- user who triggered the vote
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    
    -- Index for lookups
    UNIQUE(chat_id, message_id)
);

-- Community vote participants (who voted what)
CREATE TABLE IF NOT EXISTS community_vote_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vote_id UUID REFERENCES community_vote_log(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    vote TEXT NOT NULL,  -- up, down, abstain
    voted_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(vote_id, user_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_community_vote_chat ON community_vote_log(chat_id);
CREATE INDEX IF NOT EXISTS idx_community_vote_target ON community_vote_log(target_user_id);
CREATE INDEX IF NOT EXISTS idx_community_vote_result ON community_vote_log(result) WHERE result IS NULL;
CREATE INDEX IF NOT EXISTS idx_community_vote_participants_vote ON community_vote_participants(vote_id);

-- Add auto_vote settings to groups
-- This is stored in groups.settings JSONB
-- auto_vote: { enabled: bool, threshold: int, timeout: int, action: string }
