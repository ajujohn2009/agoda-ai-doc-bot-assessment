-- Migration to add model info and sources to conversation messages
-- This allows storing which model was used and what sources were referenced

-- Add columns for model information
ALTER TABLE conversation_messages 
ADD COLUMN IF NOT EXISTS model_provider VARCHAR(32),
ADD COLUMN IF NOT EXISTS model_name VARCHAR(64),
ADD COLUMN IF NOT EXISTS sources JSONB;

-- Add index for querying by model
CREATE INDEX IF NOT EXISTS idx_conversation_messages_model 
ON conversation_messages(model_provider, model_name);

-- Add index for JSONB sources (for future queries)
CREATE INDEX IF NOT EXISTS idx_conversation_messages_sources 
ON conversation_messages USING gin(sources);