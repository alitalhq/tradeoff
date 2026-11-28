-- Separate file: a new enum value cannot be used in the transaction that adds it.
ALTER TYPE session_status ADD VALUE 'awaiting_limits' AFTER 'paused';
