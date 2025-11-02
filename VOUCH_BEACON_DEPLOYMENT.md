# Vouch Beacon Deployment Guide

## What is Vouch Beacon?

Vouch Beacon is a hybrid group-based reputation system that implements:

- **Welcome Mat**: Ephemeral onboarding for new group members
- **Guardian Protocol**: Real-time TOS compliance filtering
- **Vouch Flow**: Silent keyword-based vouching with emoji reactions
- **Trust Network**: D3.js-powered network visualization
- **Gamification**: Ranks, badges, progress bars, and social proof
- **Magic Link Auth**: Secure JWT-based web app authentication

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     VOUCH BEACON SYSTEM                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Telegram    │  │   REST API   │  │   Web App    │     │
│  │  Guardian    │◄─┤   FastAPI    │◄─┤   (D3.js)    │     │
│  │    Bot       │  │              │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                  │                  │            │
│         └──────────────────┴──────────────────┘            │
│                            │                               │
│                   ┌────────▼─────────┐                     │
│                   │   PostgreSQL     │                     │
│                   │    Database      │                     │
│                   └──────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

```
vouch-beacon/
├── database_beacon.py          # Database schema & operations
├── api_beacon.py               # REST API endpoints
├── bot_beacon.py               # Guardian Bot (3 core flows)
├── main_beacon.py              # Unified entry point
│
├── webapp/
│   ├── index_beacon.html       # Web app UI
│   └── static/
│       ├── styles_beacon.css   # Professional design system
│       └── main_beacon.js      # Frontend logic + D3.js network
│
├── requirements.txt            # Python dependencies
├── .env.beacon.example         # Environment template
└── VOUCH_BEACON_DEPLOYMENT.md  # This file
```

## Step 1: Environment Setup

1. **Copy environment template:**
   ```bash
   cp .env.beacon.example .env
   ```

2. **Fill in your .env file:**
   ```env
   # Required
   BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
   BOT_USERNAME=YourBotUsername
   WEBHOOK_URL=https://your-app.repl.co
   ADMIN_ID=123456789
   DATABASE_URL=postgresql://user:pass@host:5432/db
   JWT_SECRET=generate-a-random-32-char-string

   # Optional
   ENABLE_CONTENT_MODERATION=true
   GROQ_API_KEY=your_groq_key_for_ai_moderation
   ```

3. **Generate JWT_SECRET:**
   ```python
   import secrets
   print(secrets.token_urlsafe(32))
   ```

## Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `fastapi` - REST API framework
- `uvicorn` - ASGI server
- `python-telegram-bot` - Telegram Bot API
- `asyncpg` - PostgreSQL async driver
- `pyjwt` - JWT token generation
- `httpx` - Async HTTP client

## Step 3: Database Setup

The database schema will be created automatically on first run. Tables include:

- `users` - User profiles with `is_known_user` flag
- `vouches` - Vouch records with group_chat_id and soft delete
- `group_config` - Group-specific settings
- `events` - Analytics and event tracking

## Step 4: Run the System

**On Replit:**
```bash
python main_beacon.py
```

**Locally:**
```bash
python main_beacon.py
```

The system will:
1. Validate environment variables
2. Connect to PostgreSQL
3. Initialize database schema
4. Start the Telegram bot
5. Launch the FastAPI server
6. Serve the web app

## Step 5: Set Telegram Webhook

After your app is running, set the webhook:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://your-app.repl.co/webhook"
```

Verify it's set:
```bash
curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
```

## Step 6: Add Bot to Group

1. Add your bot to a Telegram group
2. Make it an **admin** with these permissions:
   - Delete messages (for Guardian Protocol)
   - Pin messages (optional)
   - Invite users (optional)

3. Test the flows:

### Test Welcome Mat
- Have a new user send a message
- They should see an ephemeral "Connect" button
- Clicking it runs `/start` and marks them as known

### Test Guardian Protocol
- Send a message with banned words (e.g., "scam", "fraud")
- The bot should delete it immediately
- You should receive a DM warning

### Test Vouch Flow
- Send: `vouch @username`
- Message gets deleted
- Confirmation appears (10 seconds)
- You receive DM with [Add Comment] and [Undo Vouch]

## Step 7: Web App Access

Users can access the web app via:

1. **Magic Link from Bot:**
   - User sends `/start` to bot
   - Bot generates magic link with JWT
   - User clicks link → authenticated session

2. **Direct URL (if authenticated):**
   - `https://your-app.repl.co/`

## Key Features Implemented

### 1. Welcome Mat Flow
- Detects new users in groups
- Posts ephemeral message with deep link
- Self-destructs after 60 seconds
- Marks user as "known" after `/start`

### 2. Guardian Protocol
- Monitors ALL group messages
- Instant pattern-based violation detection
- Deletes TOS-violating content immediately
- Sends private warnings to users
- Logs to admin for review

### 3. Vouch Flow
- Detects: `vouch @user`, `+1 @user`, `recommend @user`
- Deletes trigger message (no spam)
- Creates vouch with group_chat_id
- Reacts with ✅ emoji (self-destructs)
- Sends DM with action buttons

### 4. Gamification System
- **Ranks**: 7 levels (Newcomer → Legend)
- **Badges**: First Vouch, Supporter, Collector, Early Adopter, Influencer
- **Progress Bars**: Visual progress to next rank
- **Social Proof Grid**: Stacks vouches with profile pictures

### 5. Trust Network Visualization
- D3.js force-directed graph
- Interactive node dragging
- Color-coded connections:
  - Blue: You (center)
  - Orange: Vouchers (people who vouched for you)
  - Green: Vouched (people you vouched for)

### 6. Magic Link Authentication
- JWT tokens with 15-minute expiry
- Secure session cookies
- Seamless redirect to web app

## API Endpoints

### Vouches
- `POST /api/vouches` - Create vouch
- `PUT /api/vouches/{id}` - Update comment
- `DELETE /api/vouches/{id}` - Undo vouch

### Users
- `GET /api/users/{telegram_user_id}` - Get profile + stats

### Leaderboards
- `GET /api/leaderboards?type=most_vouched` - Get leaderboard
- `GET /api/leaderboards?type=top_givers` - Get top givers

### Authentication
- `POST /api/auth/magic-link` - Generate magic link
- `GET /auth?token=...` - Verify and authenticate

### Analytics
- `GET /api/analytics` - Get system analytics

## Bot Commands

- `/start` - Initialize profile, get magic link
- `/check @username` - View vouches for user (DM only)

## Troubleshooting

### Bot not responding in group
- Make sure bot is an **admin**
- Check webhook is set: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
- Check logs for errors

### Database connection failed
- Verify `DATABASE_URL` format: `postgresql://user:pass@host:5432/db`
- Ensure PostgreSQL is running
- Check firewall/network access

### Web app not loading
- Verify `WEBHOOK_URL` is correct
- Check static files are mounted: `webapp/static/`
- Open browser console for errors

### Magic links not working
- Verify `JWT_SECRET` is set and secure
- Check token hasn't expired (15 min limit)
- Ensure `/auth` endpoint is accessible

### Vouches not appearing
- Verify user has used `/start` (must be in database)
- Check `is_known_user = TRUE` in database
- Ensure group_chat_id is correct

## Performance Considerations

- **Database**: Uses connection pooling (2-10 connections)
- **Bot**: Async handlers for non-blocking processing
- **API**: FastAPI with async endpoints
- **Frontend**: Skeleton loading, optimistic updates

## Security Features

- JWT-based authentication with expiry
- TOS compliance filtering (pattern + AI optional)
- Soft deletes (audit trail preserved)
- Admin-only analytics endpoints
- Rate limiting on magic links

## Scaling

For production at scale:

1. **Add Redis** for caching and session management
2. **Enable Groq AI** for advanced content moderation
3. **Use CDN** for static assets
4. **Database read replicas** for heavy read loads
5. **Horizontal scaling** with load balancer

## Support

For issues or questions:
1. Check logs: `tail -f vouch-beacon.log`
2. Verify environment variables
3. Test individual components:
   - Database: `python -c "from database_beacon import db; import asyncio; asyncio.run(db.connect())"`
   - Bot: Check Telegram BotFather
   - API: Visit `https://your-app.repl.co/health`

---

**Built with the Vouch Beacon Blueprint**
Hybrid group-based vouch system with private actions, public recognition.
