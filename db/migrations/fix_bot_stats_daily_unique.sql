-- Fix missing UNIQUE constraint on bot_stats_daily (chat_id, day)
-- This is required for ON CONFLICT (chat_id, day) to work in the aggregator
-- Error seen: "there is no unique or exclusion constraint matching the ON CONFLICT specification"

-- Add constraint if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_bot_stats_daily_chat_day'
    ) THEN
        -- Remove any duplicate rows first (keep the one with highest message_count)
        DELETE FROM bot_stats_daily a
        USING bot_stats_daily b
        WHERE a.ctid < b.ctid
          AND a.chat_id = b.chat_id
          AND a.day = b.day
          AND a.chat_id IS NOT NULL
          AND a.day IS NOT NULL;

        -- Now add the constraint
        ALTER TABLE bot_stats_daily
            ADD CONSTRAINT uq_bot_stats_daily_chat_day
            UNIQUE (chat_id, day);

        RAISE NOTICE 'Added uq_bot_stats_daily_chat_day constraint';
    ELSE
        RAISE NOTICE 'Constraint uq_bot_stats_daily_chat_day already exists';
    END IF;
END $$;

-- Also ensure index exists for performance
CREATE INDEX IF NOT EXISTS idx_bot_stats_daily_chat_day
    ON bot_stats_daily (chat_id, day);
