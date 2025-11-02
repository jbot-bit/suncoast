# LocalVouch - Quick Reference Card

## How It Works (Simple Version)

### In Your Community Group

**Someone asks about a person:**
```
"Anyone know Mike the plumber?"
```

**You vouch for them:**
```
"vouch @mike - fixed my sink, great price"
[Bot reacts with ✅]
```

**To check someone's reputation:**
```
DM the bot: /check @mike

Bot shows:
✅ TRUSTED
8 thumbs up | 0 thumbs down
[Full vouch history]
```

**That's it!** Simple, clean, no spam.

---

## Vouch Syntax (All Work)

```
vouch @mike
vouch mike
vouch @mike - great work
+1 @mike
recommend @mike
thumbs up @mike
```

**Warnings (require admin approval):**
```
warn @sketchy
caution @sketchy
thumbs down @sketchy
```

---

## Bot Reactions

| You See | Means |
|---------|-------|
| ✅ | Success - vouch recorded |
| ❓ | User not found - they need to /start bot |
| ⏳ | Pending admin approval (negative vouch) |
| ❌ | Error - contact admin |

---

## Commands

**In DMs to Bot:**
```
/check @username   → See their vouches
/start             → Initialize your profile
/profile           → See your stats
/share             → Get your profile link
```

**Admin Only:**
```
/stats          → Analytics
/leaderboard    → Top users
```

---

## Ranks (Auto-Assigned)

```
🆕 NEW        → 0 vouches
⏳ BUILDING   → 1-2 thumbs up
✅ TRUSTED    → 3-9 thumbs up
⭐ TOP-RATED  → 10+ thumbs up
⚠️ MIXED      → Has warnings
🚫 CAUTION    → Multiple warnings
```

---

## Protection System

**Bot automatically deletes:**
- Scam links (bit.ly, etc.)
- Crypto addresses
- Adult content
- Threats/harassment
- Spam

**Result:** Group stays safe, no manual moderation needed.

---

## Privacy

- ✅ Vouching is public (in group)
- ✅ Checking vouches is private (DM only)
- ✅ No personal info collected
- ✅ All moderation is logged (transparent)

---

## Example Scenario

**Day 1:**
```
Sarah: "Need a plumber, anyone?"
John: "vouch @mike_plumber - he's great"
[✅]
```

**Day 2:**
```
Tom (in DM): /check @mike_plumber
Bot: "✅ TRUSTED - 1 thumbs up
     👍 @john (yesterday)
        he's great"
Tom: "I'll hire him"
```

**Day 3:**
```
Tom: "vouch @mike_plumber - fast service, fair price"
[✅]
Mike now: ✅ TRUSTED - 2 thumbs up
```

**Month later:**
```
Anyone: /check @mike_plumber
Bot: "⭐ TOP-RATED - 12 thumbs up
     [Shows all 12 vouches...]"

Result: Mike has built reputation, gets more business
```

---

## Setup (Admin)

1. Add bot to group as admin
2. Enable permissions: Delete Messages, Read Messages, Add Reactions
3. Get free Groq API key: https://console.groq.com/keys
4. Add to environment: `GROQ_API_KEY=gsk_xxxxx`
5. Restart bot
6. Test: "vouch @someone"
7. Done!

---

## Cost

```
$0   → Groq AI (free)
$0   → Telegram Bot (free)
$5-10 → Hosting (Railway/Heroku)

Total: $5-10/month
```

---

## The Magic

**Before:** "Anyone vouch for X?" → Random people say "yeah sure" → Scams happen

**After:** "Anyone vouch for X?" → /check shows 8 detailed vouches → Informed decision

**Result:** Scammers can't hide, trustworthy people get recognized.

---

## Questions?

- Full guide: [COMPLETE_SYSTEM_GUIDE.md](COMPLETE_SYSTEM_GUIDE.md)
- Setup help: [SETUP_GROUP_PROTECTION.md](SETUP_GROUP_PROTECTION.md)
- Implementation details: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
