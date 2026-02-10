-- Migration: Add booking contact fields to sessions table
-- Date: 2026-02-11
-- Description: Stores temporary booking contact details (name and CNIC) for current booking session

ALTER TABLE sessions 
ADD COLUMN IF NOT EXISTS booking_name TEXT,
ADD COLUMN IF NOT EXISTS booking_cnic TEXT;

-- Add comments to columns
COMMENT ON COLUMN sessions.booking_name IS 'Temporary name for current booking (may differ from user.name)';
COMMENT ON COLUMN sessions.booking_cnic IS 'Temporary CNIC for current booking (may differ from user.cnic)';
