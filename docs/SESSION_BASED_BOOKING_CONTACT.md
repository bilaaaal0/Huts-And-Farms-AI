# Session-Based Booking Contact Details

## Overview

Booking contact details (name and CNIC) are now stored **temporarily in the session** rather than permanently in the user profile. This allows users to book properties for different people without changing their own profile information.

## Key Changes

### 1. Database Schema

**New columns in `sessions` table:**
```sql
booking_name TEXT    -- Temporary name for current booking
booking_cnic TEXT    -- Temporary CNIC for current booking
```

**Migration file:** `migrations/add_booking_contact_to_sessions.sql`

### 2. Data Flow

```
User provides/edits details
         ↓
prepare_booking_details tool validates
         ↓
Saves to session.booking_name & session.booking_cnic
         ↓
create_booking reads from session (priority order below)
         ↓
Booking created with contact_details
         ↓
Session fields cleared (booking_name = NULL, booking_cnic = NULL)
```

### 3. Priority Order for Name/CNIC

When creating a booking, the system uses this priority:

1. **Parameters** - Values passed from `prepare_booking_details` tool
2. **Session** - `session.booking_name` and `session.booking_cnic` (temporary)
3. **User Profile** - `user.name` and `user.cnic` (permanent, unchanged)

### 4. User Profile Unchanged

**Important:** The user profile (`user.name` and `user.cnic`) is **NEVER modified** during booking. It remains as the user's permanent identity.

## Implementation Details

### prepare_booking_details Tool

**Location:** `app/agents/tools/booking_details_tools.py`

**What it does:**
- Validates name (min 2 characters) and CNIC (exactly 13 digits)
- **Saves validated details to session** (not user table)
- Returns `ready=true` when details are valid and confirmed
- Shows edit form with error message if validation fails

**Key code:**
```python
# Save to session (temporary, for this booking only)
session.booking_name = final_name
session.booking_cnic = final_cnic
db.commit()
```

### create_booking Service

**Location:** `app/services/booking_service.py`

**What it does:**
- Accepts new parameter: `session_id` (optional)
- Reads name/CNIC from session if available
- Falls back to user profile if session values not set
- **Clears session fields after successful booking**
- Uses booking details for `booking_id` and `contact_details`

**Key code:**
```python
# Priority order for name/CNIC
final_name = user_name  # From prepare_booking_details
if not final_name and session:
    final_name = session.booking_name  # From session (temporary)
if not final_name:
    final_name = user.name  # From user profile (permanent)

# Clear session after booking
if session:
    session.booking_name = None
    session.booking_cnic = None
    db.commit()
```

### create_booking Tool

**Location:** `app/agents/tools/booking_tools.py`

**What it does:**
- Passes `session_id` to the booking service
- Allows service to read and clear session booking details

**Key code:**
```python
result = booking_service.create_booking(
    db=db,
    user_id=str(session.user_id),
    property_id=session.property_id,
    booking_date=booking_date_obj,
    shift_type=shift_type,
    user_name=user_name,
    cnic=cnic,
    booking_source="Bot",
    session_id=session_id  # NEW: Pass session_id
)
```

## Use Cases

### Use Case 1: First-Time User
1. User starts booking
2. `prepare_booking_details` asks for name and CNIC
3. User provides: "Ali Ahmed", "1234567890123"
4. Tool saves to `session.booking_name` and `session.booking_cnic`
5. User confirms booking
6. `create_booking` reads from session, creates booking
7. Session fields cleared
8. User profile remains empty (can be filled later)

### Use Case 2: Booking for Someone Else
1. User (Bilal) has profile: name="Bilal", cnic="4210112345678"
2. User wants to book for friend (Ahmed)
3. `prepare_booking_details` shows current details (Bilal's)
4. User clicks "Edit Details"
5. User enters: "Ahmed Ali", "9876543210123"
6. Tool saves to session (Bilal's profile unchanged)
7. Booking created with Ahmed's details
8. Session cleared
9. Next booking will show Bilal's details again

### Use Case 3: Editing During Validation Error
1. User provides: "A", "123" (invalid)
2. Tool shows error: "Name must be at least 2 characters and CNIC must be exactly 13 digits"
3. Edit form shown with both fields pre-filled
4. User corrects: "Ali", "1234567890123"
5. Tool validates and saves to session
6. Booking proceeds

## Benefits

1. **Flexibility** - Users can book for different people without changing their profile
2. **Privacy** - User profile remains unchanged and private
3. **Temporary Storage** - Booking details are session-specific and cleared after use
4. **Validation** - All details validated before saving
5. **Traceability** - Each booking has its own contact details in `contact_details` column

## Testing

To test the implementation:

1. **Run migration:**
   ```sql
   -- Execute in Neon DB SQL editor
   ALTER TABLE sessions 
   ADD COLUMN IF NOT EXISTS booking_name TEXT,
   ADD COLUMN IF NOT EXISTS booking_cnic TEXT;
   ```

2. **Test scenarios:**
   - New user booking (no profile data)
   - Existing user confirming their details
   - Existing user editing to book for someone else
   - Validation errors (short name, wrong CNIC length)
   - Multiple bookings with different details

3. **Verify:**
   - Session fields populated during booking flow
   - Session fields cleared after successful booking
   - User profile unchanged throughout
   - Booking `contact_details` contains correct information

## Files Modified

1. `migrations/add_booking_contact_to_sessions.sql` - Database migration
2. `app/models/user.py` - Added `booking_name` and `booking_cnic` to Session model
3. `app/agents/tools/booking_details_tools.py` - Save to session instead of user
4. `app/services/booking_service.py` - Read from session, clear after booking
5. `app/agents/tools/booking_tools.py` - Pass session_id to service

## Migration Required

**Before deploying, run this migration in Neon DB:**

```sql
ALTER TABLE sessions 
ADD COLUMN IF NOT EXISTS booking_name TEXT,
ADD COLUMN IF NOT EXISTS booking_cnic TEXT;

COMMENT ON COLUMN sessions.booking_name IS 'Temporary name for current booking (may differ from user.name)';
COMMENT ON COLUMN sessions.booking_cnic IS 'Temporary CNIC for current booking (may differ from user.cnic)';
```
