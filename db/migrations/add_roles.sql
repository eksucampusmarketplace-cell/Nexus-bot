-- Custom Roles & Permissions System
-- Adds role-based access control on top of Telegram's admin system

-- Roles table: defines roles per group
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#64748b',
    permissions JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(chat_id, name)
);

-- User roles table: assigns roles to users
CREATE TABLE IF NOT EXISTS user_roles (
    user_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    granted_by BIGINT,
    expires_at TIMESTAMPTZ,           -- NULL = permanent
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, chat_id, role_id)
);

-- Indexes for fast permission lookups
CREATE INDEX IF NOT EXISTS idx_roles_chat ON roles(chat_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_lookup ON user_roles(user_id, chat_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_expires ON user_roles(expires_at) WHERE expires_at IS NOT NULL;
