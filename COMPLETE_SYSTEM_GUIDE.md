# LocalVouch - Complete System Guide

## Overview

**LocalVouch** is a Telegram-native vouch/reputation system designed to:
1. Combat scammers in local communities
2. Build trust through public vouching
3. Protect groups from ToS violations
4. Work entirely within Telegram (no webapp friction)

## How It Works - User Perspective

### In Your Community Group

**Vouching for someone:**
```
Sarah: "Anyone know Mike the plumber?"
John: "vouch mike - fixed my sink perfectly"
[Bot reacts with ✅ emoji]
```

**Checking vouches (via DM):**
```
DM to bot: /check @mike

Bot responds:
Vouches for @mike
✅ TRUSTED
8 thumbs up | 0 thumbs down

Recent Vouches (8):
👍 @john (today)
   fixed my sink perfectly

👍 @sarah (3d ago)
   great work on kitchen remodel
...
```

**Warning about someone:**
```
Lisa: "warn @sketchy_guy - tried to overcharge me"
[Bot reacts with ⏳ emoji - pending admin approval]
```

## System Architecture

### 3-Layer Protection System

```
Message arrives in group
    ↓
Layer 1: Content Moderation (instant)
    ├─> Scam URLs? → DELETE
    ├─> Crypto addresses? → DELETE
    ├─> Banned words? → DELETE
    └─> Clean? → Continue
    ↓
Layer 2: Vouch Detection (instant)
    ├─> "vouch @user"? → Record + ✅ emoji
    ├─> "warn @user"? → Pending + ⏳ emoji
    └─> Normal chat? → Allow
    ↓
Layer 3: AI Analysis (2-3 sec, if enabled)
    ├─> Subtle scam? → DELETE
    ├─> Suspicious? → Flag for admin
    └─> Safe? → Allow
```

### Data Storage

**Database only** - no webapp required:
- User table: telegram_user_id, username, thumbs_up_count, thumbs_down_count, rank
- Vouches table: from_user_id, to_user_id, message, is_thumbs_up, created_at
- Everything accessible via bot commands

### Rank System (Auto-calculated)

```
🆕 NEW        → 0 vouches
⏳ BUILDING   → 1-2 thumbs up, no warnings
✅ TRUSTED    → 3-9 thumbs up, no warnings
⭐ TOP-RATED  → 10+ thumbs up, no warnings
⚠️ MIXED      → Any thumbs down (1-2 warnings)
🚫 CAUTION    → 3+ thumbs down (multiple warnings)
```

## User Flows

### Flow 1: Vouch for Local Tradesperson

**Scenario:** Sarah hired Mike to fix her plumbing and wants to vouch for him.

```
1. Sarah (in group): "vouch @mike_plumber - fast service, fair price"
2. Bot detects pattern → checks @mike_plumber exists
3. Bot records vouch to database
4. Bot reacts with ✅ emoji (confirmation)
5. Mike's thumbs_up_count increases: 7 → 8
6. Mike's rank stays: ✅ TRUSTED
```

**Result:** No spam messages, clean group chat, vouch recorded.

### Flow 2: Check Someone's Reputation

**Scenario:** Tom wants to hire an electrician, someone mentioned @electrician_bob.

```
1. Tom (in DM to bot): /check @electrician_bob
2. Bot queries database for all vouches for electrician_bob
3. Bot sends formatted response:

   Vouches for @electrician_bob
   ✅ TRUSTED
   5 thumbs up | 0 thumbs down

   Recent Vouches (5):
   👍 @sarah (2d ago)
      rewired my house, great work
   👍 @mike (5d ago)
      professional and on time
   ...

4. Tom makes informed decision
```

**Result:** Private, detailed vouch history without cluttering group.

### Flow 3: Warn About Scammer

**Scenario:** Lisa was scammed by a fake tradesperson.

```
1. Lisa (in group): "warn @fake_plumber - never showed up, took deposit"
2. Bot detects warn pattern → reacts with ⏳ (pending)
3. Bot sends to admin:
   ⚠️ NEGATIVE VOUCH PENDING APPROVAL
   From: Lisa (@lisa)
   Target: @fake_plumber
   Message: never showed up, took deposit
   Group: Local Trades Community

   [Approve] [Reject]

4. Admin clicks [Approve]
5. Bot records negative vouch
6. Bot changes reaction: ⏳ → ✅
7. fake_plumber's thumbs_down_count: 0 → 1
8. fake_plumber's rank: 🆕 NEW → ⚠️ MIXED REVIEWS
```

**Result:** Warnings are validated, group protected from false accusations.

### Flow 4: Scammer Attack Attempt

**Scenario:** Malicious actor tries to get group banned by posting ToS violation.

```
1. Scammer (burner account): "Buy crypto at bit.ly/scam123"
2. Bot Layer 1 (instant pattern matching):
   → Detects "bit.ly" (scam domain)
   → DELETE MESSAGE (within 0.5 seconds)
3. Bot logs to admin:
   🛡️ Group Protection Alert
   User: @scammer123 (ID: 999999)
   Reason: Instant: Scam domain: bit.ly
   Message deleted to protect group
4. Admin receives log, can ban user
```

**Result:** Violation deleted before screenshot possible, group stays safe.

### Flow 5: Subtle Scam (AI Detection)

**Scenario:** Sophisticated scammer posts message that looks normal but is actually a scam.

```
1. Scammer: "DM me if you want verified Telegram accounts cheap"
2. Bot Layer 1 (patterns): No instant match, continues...
3. Bot Layer 2 (vouch detection): Not a vouch, continues...
4. Bot Layer 3 (Groq AI):
   → Analyzes message
   → Detects: VIOLATION, category: "scam", confidence: 85%
   → DELETE MESSAGE (within 3 seconds)
5. Bot logs to admin:
   🛡️ Group Protection Alert
   Reason: AI: scam - Account selling (confidence: 85%)
   Message deleted
```

**Result:** Subtle violations caught by AI before damage done.

## Bot Commands

### For Everyone

```
/start          → Initialize your profile, get started
/check @user    → (DM only) See all vouches for someone
/profile        → View your own vouch stats
/share          → Get your profile link to share
/help           → Show command list
```

### In Groups (Natural Language)

```
"vouch @mike"              → Records vouch, reacts with ✅
"vouch mike - great work"  → Same, with message
"+1 @sarah"                → Alternative vouch syntax
"recommend @john"          → Another way to vouch
"warn @sketchy"            → Pending admin approval
"caution @scammer"         → Alternative warning syntax
```

### For Admins Only

```
/stats          → Analytics dashboard
/leaderboard    → Top vouched users
```

## Technical Setup

### Environment Variables

```env
# Required
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_ID=your_telegram_user_id
BOT_USERNAME=YourBotUsername
DATABASE_URL=postgresql://user:pass@host/db

# Optional but recommended
GROQ_API_KEY=gsk_xxxxx              # FREE AI (https://console.groq.com/keys)
ENABLE_CONTENT_MODERATION=true      # Enable ToS protection
MODERATION_LOG_CHANNEL=-1001234567  # Optional: private channel for logs

# Optional (webapp can be disabled)
WEBHOOK_URL=https://your-app.com    # Only if using webapp
```

### Bot Permissions Required

In your Telegram group, bot needs:
- ✅ Delete Messages (to remove ToS violations)
- ✅ Read Messages (to detect vouches and violations)
- ✅ Add Reactions (for emoji feedback)

Bot does NOT need:
- ❌ Post Messages (optional - only for admin-approved warnings)
- ❌ Pin Messages
- ❌ Manage Users

## Privacy & Safety

### Privacy Features

1. **Vouch lookup is DM-only** - prevents public shaming
2. **No PII collected** - only Telegram username/ID
3. **Transparent logging** - admin sees all moderation actions
4. **Negative vouches require approval** - prevents abuse

### Safety Features

1. **ToS Violation Protection**
   - Instant deletion of scam URLs, crypto addresses
   - AI detection of subtle violations
   - Admin logging for transparency

2. **Vouch Sanitization**
   - Banned words filtered automatically
   - URLs/crypto addresses removed from vouch messages
   - Character limits enforced

3. **False Positive Prevention**
   - AI confidence threshold (70%+)
   - Suspicious content flagged, not deleted
   - Admin override available

### Abuse Prevention

**Problem:** Bad actor vouches for themselves with fake accounts
**Solution:**
- Vouch patterns tracked (admin can see who vouches for whom)
- Low-rank users' vouches carry less weight (admin review)
- Can implement rate limiting (e.g., max 5 vouches/day per user)

**Problem:** Revenge negative vouches
**Solution:**
- All negative vouches require admin approval
- Admin sees full context before approving
- False warnings are rejected

**Problem:** Scammer tries to get group banned
**Solution:**
- ToS violations deleted within 5 seconds (before screenshots)
- All deletions logged to admin
- Group protected automatically

## Cost Analysis

```
Monthly Costs:
- Hosting (Railway/Heroku): $5-10
- Database (Postgres): $0 (included in hosting)
- Groq AI: $0 (14,400 requests/day free forever)
- Telegram Bot: $0 (free)

Total: $5-10/month
```

Compare to:
- Webapp hosting: +$0 (can disable)
- OpenAI/ChatGPT: $60/month (NOT NEEDED - Groq is free)
- Custom backend: Already included

## Success Metrics

After deploying in your community:

**Week 1:** Track initial adoption
- How many vouches created
- How many /check lookups
- Any false positives to adjust

**Month 1:** Measure impact
- Has scammer activity decreased?
- Are people asking for vouches before hiring?
- Any ToS violation attempts blocked?

**Month 3:** Long-term value
- Top users with high vouches trusted by community
- New members ask for vouches before transactions
- Group reputation improved

## Troubleshooting

### "Bot didn't react to my vouch"
- Check bot is admin with "Add Reactions" permission
- Check username is correct (must exist in system)
- Check pattern: "vouch @username" (@ optional)

### "Bot deleted my legitimate message"
- Review what was deleted in admin logs
- Likely contained flagged keyword or pattern
- Can whitelist trusted users in code

### "/check not working"
- Must use in DM (private message) to bot
- Username must have received at least one vouch
- Format: `/check @username` (@ optional)

### "Vouch recorded but rank didn't change"
- Rank updates automatically but has thresholds
- Check current rank requirements (see Rank System above)
- May need more vouches to reach next tier

## Future Enhancements (Optional)

1. **Verification badges**
   - Admin can manually verify trusted businesses
   - Displays ✓ verified badge

2. **Vouch decay**
   - Old vouches (>1 year) count less
   - Keeps reputation current

3. **Category tags**
   - "vouch @mike #plumber" → searchable by trade
   - "/check plumbers" → lists all vouched plumbers

4. **Business profiles**
   - Businesses can add contact info, prices
   - DM `/mybusiness` to set up

5. **Group analytics**
   - Most vouched users this month
   - Most active vouchers
   - Trust score trends

## Comparison: Before vs After

### Before LocalVouch

```
Sarah: "Anyone know a good plumber?"
Random: "Yeah I know a guy, DM me"
Sarah: *gets scammed, loses $500*
```

Problems:
- No verification system
- Scammers blend in
- No accountability
- Group gets spam DMs
- Group gets reported for ToS violations

### After LocalVouch

```
Sarah: "Anyone know a good plumber?"
John: "vouch @mike_plumber - did my bathroom"
[✅ emoji]
Sarah: (DMs bot) /check @mike_plumber
Bot: "8 thumbs up, ✅ TRUSTED"
Sarah: *hires Mike, great experience*
```

Benefits:
- Verified recommendations
- Public accountability
- Scammers visible (0 or negative vouches)
- Clean group chat (emoji reactions only)
- Group protected from ToS violations

## Summary

**LocalVouch = Trust + Protection + Simplicity**

✅ Trust through vouching
✅ Protection from scammers
✅ Protection from ToS violations
✅ Simple (everything in Telegram)
✅ Private (DM-based lookups)
✅ Free ($5/month hosting only)
✅ No friction (no webapp needed)

**Result:** Safer, more trusted local community.
