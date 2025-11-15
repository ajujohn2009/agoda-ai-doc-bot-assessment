-- Migration to ensure conversation_messages table has proper timestamp column
-- This is idempotent and safe to run multiple times

-- The created_at column should already exist from 001_init.sql
-- This migration just ensures it's there and has proper defaults

DO $$ 
BEGIN
    -- Check if created_at column exists, if not add it
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'conversation_messages' 
        AND column_name = 'created_at'
    ) THEN
        ALTER TABLE conversation_messages 
        ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW();
    END IF;
END $$;

-- Add index for better query performance when fetching conversations
CREATE INDEX IF NOT EXISTS idx_conversation_messages_created_at 
ON conversation_messages(conversation_id, created_at);