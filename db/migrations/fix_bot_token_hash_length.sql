-- Fix groups with truncated 10-character bot_token_hash values
-- by updating them to the full 64-character SHA-256 hash from the bots table.
-- This resolves the "groups not loading" bug caused by hash length mismatch.

UPDATE groups g
SET bot_token_hash = b.token_hash
FROM bots b
WHERE LEFT(b.token_hash, 10) = g.bot_token_hash
  AND LENGTH(g.bot_token_hash) = 10;
