# Vouch Portal — Your Community’s Trust Layer

Vouch Portal helps Telegram communities signal *authentic, human trust*. Every interaction is designed to feel honest, useful, and respectful—no gimmicks, no slot-machine points. When someone vouches, they are making a lasting statement about character. When members browse profiles, they see real context, not vanity metrics.

---

## Product Principles

- **Authenticity over gamification** – Trust comes from people, not leaderboards. We keep the experience transparent and meaningful.
- **Immediate clarity** – One command should tell a new member what matters. One glance should reveal why someone is trusted.
- **Respect for communities** – The bot works alongside human moderators, reinforces culture, and never hijacks conversations.

---

## What the Bot Delivers Today

- **Natural vouching** – `vouch @username` (and conversational variations like “I vouch for @username” or “+1 @username”) are detected in-group with zero setup.
- **Automatic profiles** – The first time a member interacts, their profile is created in the background. No `/start` ritual required.
- **Trust confirmations** – Clean, compact “trust cards” post back into the group so everyone understands who vouched, for whom, and why.
- **Context-on-demand** – `/search @username` surfaces real vouches right in chat. `/profile` in DM adds richer detail.
- **Respectful safety net** – AI-assisted moderation quietly removes harmful content, warns privately on first offense, and escalates only when behavior repeats.
- **Web companion** – A focused WebApp (Telegram Web App) shows your trust timeline, incoming requests, and the people who rely on you.

### Coming next (already in design)
- Structured “why I vouch” prompts to capture richer context.
- Trust request pipeline so members can nudge their network gracefully.
- Referral hooks that celebrate genuine introductions, not vanity invites.

---

## Architecture at a Glance

| Layer | Purpose |
|-------|---------|
| `bot.py` | Telegram command handlers, inline detection, moderation workflows |
| `database.py` | PostgreSQL access with strict transactions and trust-safe constraints |
| `main.py` | FastAPI server hosting the WebApp, REST APIs, and Telegram webhook |
| `webapp/` | Lightweight HTML/JS front-end for trust timelines and profile management |

### Tech Stack Highlights
- **Language**: Python 3.12 (async-first)
- **Frameworks**: FastAPI, python-telegram-bot
- **Database**: PostgreSQL via asyncpg connection pooling
- **Front-end**: Vanilla JS + modular CSS (Telegram WebApp compatible)
- **Moderation**: Pattern engine with optional Groq semantic checks

---

## Getting Started

### 1. Configure environment
Create a `.env` file (or set secrets in your host):

```env
DATABASE_URL=postgresql://user:password@host:5432/database
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_ID=your_telegram_user_id
WEBHOOK_URL=https://your-domain.com        # Required if you deploy over HTTPS
BOT_USERNAME=YourBotUsername               # Optional override
GROQ_API_KEY=optional_ai_moderation_key    # Optional
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run locally
```bash
python main.py
```
This boots the FastAPI server, connects to PostgreSQL, applies any pending schema migrations, and starts the Telegram bot.

### 4. Expose publicly (for Telegram webhooks)
- Use a tunneling tool (`ngrok http 8000`) or deploy to a host (Replit, Railway, Render, Fly.io, etc.).
- Run:
  ```bash
  curl "https://api.telegram.org/bot$BOT_TOKEN/setWebhook?url=$WEBHOOK_URL/webhook"
  ```

---

## Operational Checklist

- **Unique vouch protection** – Database enforces one vouch per pair via a UNIQUE constraint. If the bot starts without it, the migration adds it automatically.
- **Race-condition safe** – Cooldowns and point awards lock rows with `SELECT … FOR UPDATE` so members cannot double-dip.
- **Progressive moderation** – First violation = warning DM. Second = 1-hour mute. Third = 24-hour timeout.
- **Clean shutdown** – Lifespan hooks close the bot and database pool gracefully.
- **Health monitoring** – `/health` returns service and DB status for uptime checks.

---

## Key Commands

| Command | Where | Outcome |
|---------|-------|---------|
| `vouch @username …` | Group | Records trust signal, posts trust card |
| `/search @username` | Group | Shows recent vouches inline |
| `/start` | DM | Opens personal trust dashboard and WebApp |
| `/profile` | DM | Summarizes rank, timeline, and links |
| `/help`, `/faq` | DM | Concise guidance and expectations |
| `/leaderboard` | Group/DM | Highlights notable contributors (admins can toggle) |
| `/stats` | DM (admin) | Pulls community analytics |

---

## API Surface

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve the Telegram WebApp shell |
| `/webhook` | POST | Telegram updates → bot pipeline |
| `/api/profile/init` | POST | Auto-create or fetch a user profile |
| `/api/profile/{user_id}` | GET | Detailed profile payload |
| `/api/vouch` | POST | Programmatic vouch creation (internal use) |
| `/api/users` | GET | Paginated user directory |
| `/api/leaderboard` | GET | Aggregate trust standings |
| `/api/analytics` | GET | Admin-focused health metrics |

All endpoints require server-side authentication (private deployment). Expose only what your infrastructure needs.

---

## Database Notes

Integrated migrations ensure required tables and indexes exist. Highlights:

- `users` – canonical identity with trust rank, behavior flags, and engagement streaks.
- `vouches` – immutable trust edges with vote type, message, and timestamps.
- `rank_events` – audit trail of promotions/demotions.
- `behavior_events` – moderation ledger feeding progressive discipline.
- `user_group_activity` – keeps group-level engagement stats fresh without double counting.

Schema changes are versioned in `database.py`; starting the bot applies missing alterations.

---

## Production Guidance

1. **Secure secrets** – never hardcode tokens. Use platform secrets management.
2. **Monitor pool usage** – default max connection pool size is 10. Scale up if you see saturation.
3. **Log moderation outcomes** – review warnings/mutes weekly to catch culture drift.
4. **Document norms publicly** – trust only works if members know how to earn and keep it.

---

## Extending the Experience

- Add richer Trust Card designs by editing `bot.py` trust confirmation block.
- Surface additional context in the WebApp by extending `webapp/static/main.js` and corresponding APIs.
- Integrate with CRM/Slack by consuming the `/api/vouch` endpoint and webhooking notable events.

Pull requests that keep the focus on authentic trust are welcome. If you build a feature, include rationale for how it supports the product principles at the top of this document.

---

**Built to help communities trust faster—and protect that trust forever.**
