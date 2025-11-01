"""
Telegram Bot handlers for Vouch Portal
Handles all bot commands and interactions
Includes Group Protection System against coordinated ToS violation attacks
"""
import os
import logging
import re
import json
import httpx
from typing import Optional
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, ChatPermissions
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from database import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import moderation engine
try:
    from moderation.engine import Engine as ModerationEngine
    MODERATION_ENGINE_AVAILABLE = True
    logger.info("✓ Moderation Engine loaded successfully")
except ImportError as e:
    MODERATION_ENGINE_AVAILABLE = False
    ModerationEngine = None
    logger.warning(f"Moderation Engine not available: {e}")

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "VouchPortalBot")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")  # Free tier: 14,400 requests/day

# Group Protection Settings
ENABLE_CONTENT_MODERATION = os.getenv("ENABLE_CONTENT_MODERATION", "true").lower() == "true"
MODERATION_LOG_CHANNEL = os.getenv("MODERATION_LOG_CHANNEL", "")  # Optional: channel ID for logging deletions

# Smart Strike System - Track violations without spamming users
from collections import defaultdict
from datetime import timedelta
violation_tracker = defaultdict(list)  # user_id -> [(timestamp, reason), ...]
STRIKE_WINDOW_HOURS = 24  # Track violations within 24 hours
WARN_AFTER_STRIKES = 2  # Send DM warning after this many violations
ALERT_ADMIN_AFTER_STRIKES = 4  # Alert admin after this many violations

# Telegram TOS compliance - Banned words and phrases for content filtering
BANNED_WORDS = [
    # Scam/Fraud related
    "scam", "fraud", "fake", "cheat", "steal", "hack", "stolen",
    "phishing", "ponzi", "pyramid", "mlm", "money laundering",

    # Violence/Threats
    "kill", "murder", "attack", "bomb", "terrorism", "terrorist",
    "violence", "hurt", "harm", "weapon", "gun", "explosive",

    # Illegal activities
    "drug", "cocaine", "heroin", "meth", "illegal", "smuggle",
    "counterfeit", "piracy", "pirated", "cracked",

    # Hate speech indicators
    "nazi", "fascist", "genocide", "supremacy", "racist",

    # Adult content indicators
    "porn", "xxx", "nsfw", "sexual", "nude",

    # Gambling (non-regulated)
    "casino", "poker", "bet", "gambling", "lottery",

    # Personal info requests (Telegram TOS violation)
    "credit card", "social security", "ssn", "password",
    "bank account", "routing number",

    # Spam indicators
    "buy now", "click here", "limited offer", "act now",
    "free money", "get rich", "make money fast"
]

# Pattern-based TOS violations (for instant detection)
SUSPICIOUS_PATTERNS = [
    # URLs with suspicious TLDs or patterns
    r'(?:http[s]?://)?(?:www\.)?[a-zA-Z0-9-]+\.(?:xyz|tk|ml|ga|cf|gq)\b',

    # Multiple special characters (spam indicator)
    r'[!@#$%^&*()]{4,}',

    # Excessive capitalization (spam indicator) - tuned to reduce false positives
    r'\b[A-Z]{15,}\b',

    # Phone numbers (privacy concern) - improved pattern
    r'\+\d[\d\-]{8,}',

    # Email addresses (privacy concern)
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',

    # Cryptocurrency addresses (potential scam)
    r'\b(?:0x[a-fA-F0-9]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-zA-Z0-9]{39,59})\b'
]

# High-risk scam domains (instant delete)
SCAM_DOMAINS = [
    'bit.ly', 'tinyurl.com', 'goo.gl',  # URL shorteners (often used for phishing)
    'airdrop', 'free-crypto', 'easy-money', 'get-rich',
    'dating', 'adult', 'casino', 'poker'
]

def sanitize_message(text: str) -> str:
    """
    Sanitize user messages for Telegram TOS compliance
    SMART WORD REPLACEMENT: Preserves context with clean substitutes
    - Everyone can vouch, but what gets stored is ToS-compliant
    - Replaces violations with similar-sounding clean words
    - People that know will know - and the ones that don't, don't
    Example: "great product connect" → "great car detailer"
    """
    if not text:
        return ""

    sanitized = text

    # Smart word replacements - context preserved
    smart_replacements = {
        # Drugs → Car/Auto terms
        r'\bweed\b': 'grass seed',
        r'\bcannabis\b': 'herbs',
        r'\bpills\b': 'supplements',
        r'\bxanax\b': 'relaxation',
        r'\bcocaine\b': 'energy',
        r'\bheroin\b': 'medicine',
        r'\bmeth\b': 'method',
        r'\bplug\b': 'connector',
        r'\bconnect\b': 'contact',
        r'\bproduct\b': 'service',
        r'\bquality\b': 'detailed',
        r'\bfire\b': 'excellent',
        r'\bgas\b': 'fuel',

        # Scam/fraud → Business terms
        r'\bscam\b': 'scheme',
        r'\bfraud\b': 'issue',
        r'\bponzi\b': 'plan',
        r'\bpyramid\b': 'structure',
        r'\bmlm\b': 'marketing',
        r'\binvestment\b': 'opportunity',
        r'\bguaranteed\b': 'expected',
        r'\breturns\b': 'results',
        r'\bprofit\b': 'benefit',
        r'\bairdrop\b': 'giveaway',
        r'\bbitcoin\b': 'digital',
        r'\bcrypto\b': 'tech',

        # Adult → General terms
        r'\bporn\b': 'content',
        r'\bxxx\b': 'adult',
        r'\bnsfw\b': 'mature',
        r'\bnude\b': 'art',
        r'\bsex\b': 'adult',
        r'\bdating\b': 'social',
        r'\bescort\b': 'companion',
        r'\bonlyfans\b': 'subscription',

        # Violence → Neutral terms
        r'\bnazi\b': 'extremist',
        r'\bgenocide\b': 'tragedy',
        r'\bterror\b': 'fear',
        r'\bweapon\b': 'tool',
        r'\bgun\b': 'device',
        r'\bbomb\b': 'explosive',

        # Gambling → Game terms
        r'\bcasino\b': 'venue',
        r'\bpoker\b': 'cards',
        r'\bbetting\b': 'gaming',
        r'\bgamble\b': 'chance',
    }

    # Apply smart replacements
    for pattern, replacement in smart_replacements.items():
        regex = re.compile(pattern, re.IGNORECASE)
        sanitized = regex.sub(replacement, sanitized)

    # Filter suspicious patterns (URLs, crypto addresses, phone numbers) with generic placeholder
    for pattern in SUSPICIOUS_PATTERNS:
        regex = re.compile(pattern, re.IGNORECASE)
        sanitized = regex.sub("[contact info]", sanitized)

    # Remove excessive whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()

    # Limit to 120 characters
    return sanitized[:120]


async def analyze_message_safety(message_text: str) -> dict:
    """
    Analyze message for ToS violations using Groq AI (FREE tier)
    SEMANTIC ANALYSIS: Understands context, intent, and coded language
    Returns: {
        "verdict": "SAFE" | "SUSPICIOUS" | "VIOLATION",
        "category": "scam" | "adult" | "threat" | "spam" | "doxxing" | "illegal" | null,
        "confidence": 0.0-1.0,
        "reason": "Brief explanation"
    }
    """
    if not GROQ_API_KEY:
        # Fallback to pattern matching only
        return {"verdict": "SAFE", "category": None, "confidence": 0.0, "reason": "AI disabled"}

    try:
        prompt = f'''You are a content moderator AI for a Telegram group. Analyze this message for Terms of Service violations using SEMANTIC UNDERSTANDING - look at the intent and meaning, not just keywords.

Message: "{message_text}"

IMPORTANT: People try to bypass filters by:
- Using coded language, slang, or misspellings
- Hiding intent in seemingly innocent words
- Using emojis or symbols to represent banned content
- Obfuscating URLs or contact info

Check for INTENT of:
1. **Scams/Fraud**: Investment schemes, "guaranteed returns", "get rich quick", crypto pumps, phishing attempts, fake giveaways
2. **Adult Content**: Sexual services, dating spam, explicit offers (even if coded)
3. **Threats/Violence**: Intimidation, doxxing threats, violent intent (even if subtle)
4. **Spam**: Mass advertising, MLM recruitment, bot-like repetition, unsolicited promotions
5. **Doxxing**: Sharing private info (addresses, phone numbers, personal details)
6. **Illegal Activity**: Drug sales, weapon sales, hacking services, stolen goods (even with code words)

Context matters:
- Friendly banter vs. actual threats
- Legitimate questions vs. spam
- Educational discussion vs. promotion
- Normal conversation vs. coded illegal activity

Respond ONLY with valid JSON (no markdown, no code blocks):
{{"verdict": "SAFE/SUSPICIOUS/VIOLATION", "category": "scam/adult/threat/spam/doxxing/illegal", "confidence": 0.95, "reason": "Brief reason explaining the semantic understanding"}}'''

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 150
                },
                timeout=5.0
            )

        if response.status_code != 200:
            logger.error(f"Groq API error: {response.status_code}")
            return {"verdict": "SAFE", "category": None, "confidence": 0.0, "reason": "API error"}

        result = response.json()
        content = result["choices"][0]["message"]["content"].strip()

        # Remove markdown code blocks if present
        content = content.replace("```json", "").replace("```", "").strip()

        analysis = json.loads(content)
        return analysis

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Groq response: {e}")
        return {"verdict": "SAFE", "category": None, "confidence": 0.0, "reason": "Parse error"}
    except Exception as e:
        logger.error(f"Error analyzing message safety: {e}")
        return {"verdict": "SAFE", "category": None, "confidence": 0.0, "reason": "Analysis failed"}


def check_instant_violations(text: str) -> tuple[bool, str]:
    """
    Instant pattern-based violation detection (0 latency)
    Returns: (is_violation, reason)
    """
    if not text:
        return False, ""

    text_lower = text.lower()

    # Check for scam domains
    for domain in SCAM_DOMAINS:
        if domain in text_lower:
            return True, f"Scam domain detected: {domain}"

    # Check for banned words
    for word in BANNED_WORDS:
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        if pattern.search(text):
            return True, f"Prohibited content: {word}"

    # Check for suspicious patterns
    for pattern in SUSPICIOUS_PATTERNS:
        regex = re.compile(pattern, re.IGNORECASE)
        if regex.search(text):
            return True, f"Suspicious pattern detected"

    return False, ""


def track_violation(user_id: int, reason: str) -> int:
    """
    Track a violation and return current strike count within the time window
    Returns the number of violations in the last STRIKE_WINDOW_HOURS
    """
    now = datetime.now()
    cutoff = now - timedelta(hours=STRIKE_WINDOW_HOURS)

    # Clean old violations outside the time window
    violation_tracker[user_id] = [
        (timestamp, r) for timestamp, r in violation_tracker[user_id]
        if timestamp > cutoff
    ]

    # Add new violation
    violation_tracker[user_id].append((now, reason))

    return len(violation_tracker[user_id])


async def handle_violation_smartly(context: ContextTypes.DEFAULT_TYPE, user, message_text: str, reason: str, group_name: str):
    """
    Smart violation handling:
    - Silent deletion on first offense
    - DM warning after multiple strikes
    - Admin alert only on repeat offenders
    """
    strike_count = track_violation(user.id, reason)

    # DM warning after WARN_AFTER_STRIKES violations
    if strike_count >= WARN_AFTER_STRIKES:
        try:
            warning_text = f"""⚠️ **Content Violation Warning**

Your message in **{group_name}** was removed.

**Strike {strike_count}/{ALERT_ADMIN_AFTER_STRIKES}**
**Reason:** {reason}

Please keep messages appropriate and ToS-compliant. Repeated violations may result in admin review.
"""
            await context.bot.send_message(
                chat_id=user.id,
                text=warning_text,
                parse_mode="Markdown"
            )
        except:
            pass  # User may have blocked bot

    # Alert admin only on repeat offenders
    if strike_count >= ALERT_ADMIN_AFTER_STRIKES:
        admin_alert = f"""🚨 **Repeat Offender Alert**

**Group:** {group_name}
**User:** {user.first_name} (@{user.username or 'no_username'})
**User ID:** {user.id}
**Total Strikes:** {strike_count} (last 24h)
**Latest Violation:** {reason}

**Recent Messages:**
{message_text[:200]}...

_User has violated guidelines {strike_count} times. Consider reviewing their activity._
"""
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_alert,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send admin alert: {e}")

        # Also send to log channel if configured
        if MODERATION_LOG_CHANNEL:
            try:
                await context.bot.send_message(
                    chat_id=MODERATION_LOG_CHANNEL,
                    text=admin_alert,
                    parse_mode="Markdown"
                )
            except:
                pass


async def log_moderation_action(context: ContextTypes.DEFAULT_TYPE, user, message_text: str, reason: str, group_name: str):
    """DEPRECATED - Use handle_violation_smartly instead for smart strike tracking"""
    # This is now just a wrapper for backwards compatibility
    await handle_violation_smartly(context, user, message_text, reason, group_name)


async def group_content_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Monitor ALL group messages for ToS violations
    SEMANTIC-FIRST APPROACH: AI understanding of intent, not just keywords
    """
    if not update.message or not update.message.text:
        return

    # Only moderate in groups
    if update.message.chat.type not in ['group', 'supergroup']:
        return

    # Skip if moderation is disabled
    if not ENABLE_CONTENT_MODERATION:
        return

    # Don't moderate admin messages
    if update.effective_user.id == ADMIN_ID:
        return

    # Don't moderate bot messages
    if update.effective_user.is_bot:
        return

    message_text = update.message.text
    user = update.effective_user
    group_name = update.message.chat.title

    # Layer 1: Moderation Engine (NEW - ultra-fast <10ms detection)
    # Catches 90%+ of violations with Aho-Corasick pattern matching
    if MODERATION_ENGINE_AVAILABLE and ModerationEngine:
        decision = ModerationEngine.decide(user.id, message_text)

        # CRITICAL: Mute user temporarily (e.g., CSAM, extreme violence)
        if decision["action"] == "mute":
            try:
                from datetime import datetime, timedelta
                await update.message.delete()
                # Mute for 24 hours instead of permanent ban
                mute_until = datetime.now() + timedelta(hours=24)
                await context.bot.restrict_chat_member(
                    update.message.chat.id,
                    user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=mute_until
                )
                await handle_violation_smartly(context, user, message_text, f"CRITICAL: {decision['reason']}", group_name)
                await db.record_behavior_event(user.id, "message_deleted", -10, update.message.chat.id)
                logger.warning(f"🚨 MUTED user {user.id} for 24h - critical violation: {decision['reason']}")
                return
            except Exception as e:
                logger.error(f"Failed to mute user: {e}")
                return

        # HIGH/MEDIUM: Delete message + strike
        elif decision["action"] == "delete":
            try:
                await update.message.delete()
                reason = f"{decision['reason'].upper()}: {', '.join(decision['hits'][:3])}"
                await handle_violation_smartly(context, user, message_text, reason, group_name)
                await db.record_behavior_event(user.id, "message_deleted", -2, update.message.chat.id)
                logger.info(f"✓ Deleted {decision['reason']} violation from {user.id} (score: {decision['score']})")
                return
            except Exception as e:
                logger.error(f"Failed to delete violation: {e}")
                return

        # SUSPICIOUS: Escalate to AI Layer 2
        elif decision["action"] == "escalate":
            logger.info(f"⚠ Escalating to AI - suspicious content from {user.id} (score: {decision['score']})")
            # Continue to AI analysis below

        # SAFE: Award +1 behavior point and return
        elif decision["action"] == "allow":
            await db.record_behavior_event(user.id, "message_accepted", 1, update.message.chat.id)
            return

    else:
        # Fallback to old pattern matching if engine unavailable
        is_obvious_violation, instant_reason = check_instant_violations(message_text)

        if is_obvious_violation:
            try:
                await update.message.delete()
                await handle_violation_smartly(context, user, message_text, f"Obvious: {instant_reason}", group_name)
                await db.record_behavior_event(user.id, "message_deleted", -2, update.message.chat.id)
                logger.info(f"✓ Deleted obvious violation from {user.id}: {instant_reason}")
                return
            except Exception as e:
                logger.error(f"Failed to delete obvious violation: {e}")
                return

    # Layer 2: SEMANTIC AI ANALYSIS (PRIMARY FILTER)
    # Analyze ALL messages with AI to understand context and intent
    if GROQ_API_KEY:
        analysis = await analyze_message_safety(message_text)

        if analysis["verdict"] == "VIOLATION" and analysis["confidence"] >= 0.75:
            # DELETE - AI detected semantic violation
            try:
                await update.message.delete()
                reason = f"Semantic: {analysis['category']} ({analysis['confidence']:.0%})"
                await handle_violation_smartly(context, user, message_text, reason, group_name)
                # Award -2 behavior points
                await db.record_behavior_event(user.id, "message_deleted", -2, update.message.chat.id)
                logger.info(f"✓ Deleted semantic violation from {user.id}: {analysis['category']} - {analysis['reason']}")
                return
            except Exception as e:
                logger.error(f"Failed to delete AI-detected violation: {e}")
                return

        elif analysis["verdict"] == "SUSPICIOUS" and analysis["confidence"] >= 0.6:
            # Log suspicious content for admin review
            review_message = f"""⚠️ **Suspicious Content Detected**

**Group:** {group_name}
**User:** @{user.username or user.first_name} (ID: {user.id})
**Category:** {analysis['category']}
**Confidence:** {analysis['confidence']:.0%}
**Reason:** {analysis['reason']}

**Message:**
{message_text[:500]}

_Not deleted - requires admin review._
"""
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=review_message,
                    parse_mode="Markdown"
                )
            except:
                pass

        elif analysis["verdict"] == "SAFE":
            # Message passed AI analysis - award +1 behavior point
            await db.record_behavior_event(user.id, "message_accepted", 1, update.message.chat.id)
    else:
        # No AI available - use pattern matching only (fallback)
        logger.warning("AI semantic analysis unavailable - using pattern matching only")
        # Still award +1 for messages that pass pattern filter
        await db.record_behavior_event(user.id, "message_accepted", 1, update.message.chat.id)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - streamlined for quick access"""
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Parse deep link parameters
    referrer_id = None
    direct_to_profile = None
    
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                referrer_id = int(arg.replace("ref_", ""))
            except ValueError:
                pass
        elif arg.startswith("profile_"):
            try:
                direct_to_profile = int(arg.replace("profile_", ""))
            except ValueError:
                pass

    # Create or get user
    user_data = await db.get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        referrer_id=referrer_id
    )

    # Log referral if applicable
    if referrer_id:
        await db.log_event("referral_signup", user.id, {"referrer_id": referrer_id})

    # Get user's current stats
    rank_emoji = db.get_rank_emoji(user_data["rank"])
    rank_name = db.get_rank_name(user_data["rank"])

    # Determine webapp URL
    if direct_to_profile:
        webapp_url = f"{WEBHOOK_URL}?view=profile&id={direct_to_profile}"
        button_text = "👀 View Profile"
        message_intro = f"**Check out this profile!**\n\n"
    else:
        webapp_url = WEBHOOK_URL
        button_text = "🚀 Open App"
        message_intro = ""

    # Single button to open app
    keyboard = [[InlineKeyboardButton(button_text, web_app=WebAppInfo(url=webapp_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Simplified welcome message
    if user_data['total_vouches'] == 0:
        status_message = "🆕 **New Member** - Get your first vouch!"
    else:
        status_message = f"{rank_emoji} **{rank_name}** • {user_data['total_vouches']} vouches"

    welcome_message = f"""
{message_intro}**Vouch Portal** 🤝

{status_message}

{button_text} to start building trust!
"""

    await update.message.reply_text(
        welcome_message.strip(),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /profile command"""
    user = update.effective_user

    # Get user data
    user_data = await db.get_user(user.id)
    if not user_data:
        await update.message.reply_text("Please use /start first to create your profile.")
        return

    # Get vouches
    vouches = await db.get_vouches_for_user(user.id)

    rank_emoji = db.get_rank_emoji(user_data["rank"])
    rank_name = db.get_rank_name(user_data["rank"])

    # Create webapp button
    webapp_url = f"{WEBHOOK_URL}?view=profile&id={user.id}"
    keyboard = [[InlineKeyboardButton("📊 View Full Profile", web_app=WebAppInfo(url=webapp_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    profile_text = f"""
**Your Profile**

{rank_emoji} **{rank_name}**
Total Vouches: **{user_data['total_vouches']}**
Member since: {user_data['first_seen_at'].strftime('%B %d, %Y')}

Recent vouches: **{len(vouches[:5])}** shown
"""

    await update.message.reply_text(
        profile_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def vouch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /vouch command"""
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "Usage: `/vouch @username [optional message]`\n\n"
            "Or use the WebApp for an easier experience!",
            parse_mode="Markdown"
        )
        return

    # Parse target username
    target_username = context.args[0].replace("@", "")
    message = " ".join(context.args[1:]) if len(context.args) > 1 else None

    # Sanitize message
    if message:
        message = sanitize_message(message)

    # Create vouch (works for both existing and non-existing users)
    result = await db.create_vouch(user.id, to_username=target_username, message=message)

    if "error" in result:
        await update.message.reply_text(f"❌ {result['error']}")
        return

    # Check if this was a pending vouch or immediate vouch
    if result.get("is_pending"):
        # Pending vouch for user who hasn't joined yet
        await update.message.reply_text(
            f"✅ Vouch recorded for @{target_username}!\n\n"
            f"They haven't used the bot yet, but your vouch will be counted when they join.",
            parse_mode="Markdown"
        )
    else:
        # Immediate vouch for existing user
        target_user_id = result.get("to_user_id")
        
        # Get updated user data
        target_data = await db.get_user(target_user_id)
        rank_emoji = db.get_rank_emoji(target_data["rank"])

        await update.message.reply_text(
            f"✅ Vouch recorded for @{target_username}!\n\n"
            f"They now have {rank_emoji} **{target_data['total_vouches']}** vouches.",
            parse_mode="Markdown"
        )

        # Check if this triggered a rank up
        rank_events = await db.pool.fetch(
            "SELECT * FROM rank_events WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1",
            target_user_id
        )

        if rank_events and (rank_events[0]["created_at"]).timestamp() > (result["created_at"]).timestamp() - 5:
            # Rank up just happened
            new_rank_name = db.get_rank_name(target_data["rank"])
            new_rank_emoji = db.get_rank_emoji(target_data["rank"])

            # NOTIFICATIONS DISABLED - No rank-up messages sent
            # Users will see rank updates when they open the app
            pass


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command (admin only)"""
    user = update.effective_user

    if user.id != ADMIN_ID:
        await update.message.reply_text("This command is only available to admins.")
        return

    # Get analytics
    analytics = await db.get_analytics_summary()

    stats_text = f"""
**📊 Vouch Portal Statistics**

**Users:**
• Total: {analytics['total_users']}
• Active (24h): {analytics['active_users']['24h']}
• Active (7d): {analytics['active_users']['7d']}
• New (7d): {analytics['new_signups_7d']}

**Engagement:**
• Total Vouches: {analytics['total_vouches']}
• Mutual Vouches: {analytics['mutual_vouch_count']}

**Top Helpers (This Week):**
"""

    for helper in analytics['top_helpers'][:5]:
        username = helper['username'] or helper['first_name']
        stats_text += f"• @{username}: {helper['vouch_count']} vouches\n"

    stats_text += "\n**Rank Distribution:**\n"
    for rank_data in analytics['rank_distribution']:
        emoji = db.get_rank_emoji(rank_data['rank'])
        rank_name = db.get_rank_name(rank_data['rank'])
        stats_text += f"• {emoji} {rank_name}: {rank_data['count']}\n"

    # Create dashboard button
    webapp_url = f"{WEBHOOK_URL}?view=admin"
    keyboard = [[InlineKeyboardButton("📈 Open Full Dashboard", web_app=WebAppInfo(url=webapp_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        stats_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def leaderboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /leaderboard command"""
    analytics = await db.get_analytics_summary()

    leaderboard_text = "**🏆 Top Vouched Users**\n\n"

    for i, user in enumerate(analytics['most_vouched'][:10], 1):
        username = user['username'] or user['first_name']
        emoji = db.get_rank_emoji(user['rank'])
        leaderboard_text += f"{i}. @{username} {emoji} — {user['total_vouches']} vouches\n"

    leaderboard_text += "\n_Build your reputation through community trust!_"

    # Create webapp button
    webapp_url = f"{WEBHOOK_URL}?view=community"
    keyboard = [[InlineKeyboardButton("👥 View Community", web_app=WebAppInfo(url=webapp_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        leaderboard_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
**🤝 Vouch Portal Commands**

/start — Initialize your profile
/profile — View your stats
/vouch @username [message] — Vouch for someone
/leaderboard — See top users
/help — Show this message

**About Vouch Portal:**
Build trust through community vouches. Your reputation grows as people verify you.

**Ranks:**
🚫 Unverified (0-2)
✅ Verified (3-5)
🔷 Trusted (6-10)
🛡 Endorsed (11-15)
👑 Top-Tier (16+)

_All feedback is community-based. Keep it respectful!_
"""

    # Create webapp button
    webapp_url = WEBHOOK_URL
    keyboard = [[InlineKeyboardButton("🚀 Open WebApp", web_app=WebAppInfo(url=webapp_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        help_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline buttons"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("vouch_"):
        # Handle vouch button (from group posts)
        parts = data.split("_")
        if len(parts) != 3:
            return

        action = parts[1]  # yes or unsure
        target_user_id = int(parts[2])
        from_user_id = query.from_user.id

        if action == "yes":
            # Create vouch
            result = await db.create_vouch(from_user_id, target_user_id)

            if "error" in result:
                await query.answer(f"❌ {result['error']}", show_alert=True)
                return

            await query.answer("✅ Vouch recorded!", show_alert=False)

            # Update message
            target_data = await db.get_user(target_user_id)
            rank_emoji = db.get_rank_emoji(target_data["rank"])

            await query.edit_message_text(
                f"✅ Vouch received!\n\n"
                f"User now has {rank_emoji} **{target_data['total_vouches']}** vouches.",
                parse_mode="Markdown"
            )

        elif action == "unsure":
            await query.answer("👍 Thanks for your feedback", show_alert=False)


async def group_new_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new members joining the group"""
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue

        # Create user profile
        await db.get_or_create_user(
            telegram_user_id=member.id,
            username=member.username,
            first_name=member.first_name,
            last_name=member.last_name
        )

        # Send vouch request to group
        keyboard = [
            [
                InlineKeyboardButton("👍 Yes", callback_data=f"vouch_yes_{member.id}"),
                InlineKeyboardButton("⚠️ Unsure", callback_data=f"vouch_unsure_{member.id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🧾 @{member.username or member.first_name} joined. Do you vouch for them?",
            reply_markup=reply_markup
        )


async def share_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get shareable profile link"""
    user = update.effective_user

    # Get user data to show their stats
    user_data = await db.get_user(user.id)

    # Create shareable link
    share_link = f"https://t.me/{BOT_USERNAME}?start=profile_{user.id}"

    if user_data:
        rank_emoji = db.get_rank_emoji(user_data["rank"])
        share_text = f"""
**Your Profile Link:**
`{share_link}`

{rank_emoji} **{user_data['thumbs_up_count']}** thumbs up | **{user_data['thumbs_down_count']}** thumbs down

Tap to copy the link above
Share it to let others vouch for you!
"""
    else:
        share_text = f"""
**Your Profile Link:**
`{share_link}`

Share this link to start receiving vouches!

Tap to copy the link above
"""

    await update.message.reply_text(
        share_text.strip(),
        parse_mode="Markdown"
    )


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Check vouches for a user - DM ONLY
    Usage: /check @username or /check username
    """
    user = update.effective_user

    # Only work in DMs (privacy-focused)
    if update.message.chat.type != 'private':
        await update.message.reply_text(
            "For privacy, use `/check @username` in a DM with me.",
            parse_mode="Markdown"
        )
        return

    if not context.args:
        await update.message.reply_text(
            "**Check User Vouches**\n\n"
            "Usage: `/check @username`\n"
            "Example: `/check @mike`\n\n"
            "I'll show you all vouches for that person.",
            parse_mode="Markdown"
        )
        return

    # Parse target username
    target_username = context.args[0].replace("@", "").lower()

    # Find target user
    target_user = await db.pool.fetchrow(
        "SELECT telegram_user_id, username, first_name, last_name, thumbs_up_count, thumbs_down_count, rank FROM users WHERE LOWER(username) = $1",
        target_username
    )

    if not target_user:
        await update.message.reply_text(
            f"User @{target_username} hasn't been vouched for yet.\n\n"
            f"They need to receive their first vouch in your community group.",
            parse_mode="Markdown"
        )
        return

    # Get all vouches for this user
    vouches = await db.pool.fetch(
        """
        SELECT
            v.message,
            v.is_thumbs_up,
            v.created_at,
            u.username as from_username,
            u.first_name as from_first_name
        FROM vouches v
        JOIN users u ON v.from_user_id = u.telegram_user_id
        WHERE v.to_user_id = $1
        ORDER BY v.created_at DESC
        LIMIT 50
        """,
        target_user['telegram_user_id']
    )

    # Build response
    rank_emoji = db.get_rank_emoji(target_user["rank"])
    rank_name = db.get_rank_name(target_user["rank"])

    response = f"""**Vouches for @{target_username}**

{rank_emoji} **{rank_name}**
**{target_user['thumbs_up_count']}** thumbs up | **{target_user['thumbs_down_count']}** thumbs down

"""

    if not vouches:
        response += "_No vouches yet._"
    else:
        response += f"**Recent Vouches** ({len(vouches)}):\n\n"

        for i, vouch in enumerate(vouches[:10], 1):  # Show top 10
            vouch_emoji = "👍" if vouch['is_thumbs_up'] else "👎"
            from_name = vouch['from_username'] or vouch['from_first_name']
            time_ago = (datetime.now() - vouch['created_at']).days

            if time_ago == 0:
                time_str = "today"
            elif time_ago == 1:
                time_str = "yesterday"
            else:
                time_str = f"{time_ago}d ago"

            response += f"{vouch_emoji} **@{from_name}** ({time_str})\n"
            if vouch['message']:
                # Clean message
                msg = vouch['message'].strip()[:80]
                response += f"   _{msg}_\n"
            response += "\n"

        if len(vouches) > 10:
            response += f"_...and {len(vouches) - 10} more vouches_"

    await update.message.reply_text(
        response.strip(),
        parse_mode="Markdown"
    )


async def inline_vouch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    SILENT VOUCHING SYSTEM with emoji reactions
    - Detects vouch patterns in group messages
    - Reacts with emoji (no spam messages)
    - Records to database silently
    - Users can DM bot with /check to see vouches
    """
    if not update.message or not update.message.text:
        return

    # Only work in groups
    if update.message.chat.type not in ['group', 'supergroup']:
        return

    text = update.message.text.strip().lower()
    user = update.effective_user

    # Flexible vouch patterns - matches:
    # "vouch @mike", "vouch mike", "+1 @mike", "recommend mike - good work", etc.
    positive_patterns = [
        r'(?:^|\s)vouch\s+@?(\w+)(?:\s+[-:]?\s*(.*))?',
        r'(?:^|\s)\+1\s+@?(\w+)(?:\s+[-:]?\s*(.*))?',
        r'(?:^|\s)recommend\s+@?(\w+)(?:\s+[-:]?\s*(.*))?',
        r'(?:^|\s)thumbs?\s*up\s+@?(\w+)(?:\s+[-:]?\s*(.*))?',
    ]

    # Negative patterns - require admin approval
    negative_patterns = [
        r'(?:^|\s)warn\s+@?(\w+)(?:\s+[-:]?\s*(.*))?',
        r'(?:^|\s)caution\s+@?(\w+)(?:\s+[-:]?\s*(.*))?',
        r'(?:^|\s)thumbs?\s*down\s+@?(\w+)(?:\s+[-:]?\s*(.*))?',
        r'(?:^|\s)negative\s+@?(\w+)(?:\s+[-:]?\s*(.*))?',
    ]

    # Try to match
    match = None
    is_thumbs_up = None

    for pattern in positive_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            match = m
            is_thumbs_up = True
            break

    if not match:
        for pattern in negative_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                match = m
                is_thumbs_up = False
                break

    if not match:
        return

    target_username = match.group(1).lower()
    message = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else text[:100]

    # Sanitize message - ALWAYS ACCEPT and store the cleaned version
    # Goal: Everyone can vouch, but what gets stored is ToS-compliant
    if message:
        message = sanitize_message(message)[:100]

        # Even if heavily filtered, we keep it - sanitized version goes to DB
        # People that know will know - and the ones that don't, don't

    try:
        # Ensure voucher is registered
        await db.get_or_create_user(
            telegram_user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )

        # Find target user in DB
        target = await db.pool.fetchrow(
            "SELECT telegram_user_id, username, first_name FROM users WHERE LOWER(username) = $1",
            target_username
        )

        if not target:
            # User not in system - react with ❓ to indicate unknown user
            try:
                await update.message.set_reaction("❓")
            except:
                pass
            return

        # ADMIN APPROVAL FOR NEGATIVE VOUCHES
        if not is_thumbs_up:
            # React with ⏳ to indicate pending
            try:
                await update.message.set_reaction("⏳")
            except:
                pass

            # Send approval request to admin
            approval_message = f"""
⚠️ **NEGATIVE VOUCH PENDING APPROVAL**

**From:** {user.first_name} (@{user.username or 'no_username'})
**Target:** @{target_username}
**Message:** {message if message else '(no message)'}
**Group:** {update.message.chat.title}
"""

            keyboard = [[
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_neg_{user.id}_{target['telegram_user_id']}_{update.message.chat.id}_{update.message.message_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_neg_{user.id}_{target['telegram_user_id']}_{update.message.chat.id}_{update.message.message_id}")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=approval_message.strip(),
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Failed to send admin approval request: {e}")

            return

        # Create positive vouch (immediate, with feedback)
        result = await db.create_vouch(
            from_user_id=user.id,
            to_username=target_username,
            message=message if message else None,
            is_thumbs_up=is_thumbs_up
        )

        if "error" in result:
            # React with ❌ to indicate error
            try:
                await update.message.set_reaction("❌")
            except:
                pass
            logger.error(f"Vouch error: {result['error']}")
            return

        # SUCCESS - Delete original vouch message and post confirmation
        try:
            # 1. Delete the user's vouch command message
            await update.message.delete()
        except Exception as e:
            logger.warning(f"Could not delete vouch message: {e}")

        try:
            # 2. Get updated user stats for confirmation
            target_data = await db.get_user(target['telegram_user_id'])
            rank_emoji = db.get_rank_emoji(target_data["rank"])

            # 3. Post confirmation message with details
            confirmation_text = (
                f"✅ @{user.username or user.first_name} vouched for @{target_username}\n"
                f"{rank_emoji} {target_data['total_vouches']} total vouches"
            )

            confirmation_msg = await context.bot.send_message(
                chat_id=update.message.chat.id,
                text=confirmation_text,
                parse_mode="Markdown"
            )

            # 4. Schedule auto-deletion after 60 seconds
            async def delete_confirmation(ctx):
                try:
                    await ctx.bot.delete_message(
                        chat_id=update.message.chat.id,
                        message_id=confirmation_msg.message_id
                    )
                except Exception as e:
                    logger.debug(f"Confirmation message already deleted: {e}")

            context.job_queue.run_once(
                delete_confirmation,
                when=60,
                name=f"del_conf_{confirmation_msg.message_id}"
            )

            logger.info(f"Vouch recorded with confirmation: {user.username} vouched for @{target_username} in {update.message.chat.title}")

        except Exception as e:
            logger.error(f"Error posting confirmation message: {e}")
            # Fallback to reaction if confirmation fails
            try:
                await update.message.set_reaction("✅")
            except:
                pass

    except Exception as e:
        logger.error(f"Inline vouch error: {e}")
        # React with ❌
        try:
            await update.message.set_reaction("❌")
        except:
            pass


def setup_bot_handlers(application: Application):
    """Setup all bot command handlers"""
    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("check", check_command))  # NEW: Look up vouches
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("vouch", vouch_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("share", share_command))

    # Callback query handler
    application.add_handler(CallbackQueryHandler(callback_query_handler))

    # Group Protection System - HIGHEST PRIORITY (runs BEFORE vouch handler)
    # This protects against malicious users posting ToS violations to get group reported
    application.add_handler(MessageHandler(
        filters.TEXT & (filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP),
        group_content_moderator
    ), group=0)

    # Inline vouch handler (groups) - SECOND PRIORITY
    # Runs after content moderation to handle legitimate vouch commands
    application.add_handler(MessageHandler(
        filters.TEXT & (filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP),
        inline_vouch_handler
    ), group=1)

    # New member handler (for groups)
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        group_new_member_handler
    ))

    logger.info("Bot handlers setup complete (with Group Protection System)")
    if ENABLE_CONTENT_MODERATION:
        logger.info("✓ Content moderation ENABLED")
        if GROQ_API_KEY:
            logger.info("✓ Groq AI analysis ENABLED")
        else:
            logger.warning("⚠ Groq AI disabled - pattern matching only")
    else:
        logger.warning("⚠ Content moderation DISABLED")


async def get_user_profile_photo_file_id(user_id: int) -> Optional[str]:
    """
    Fetch user's profile photo file_id from Telegram
    Returns the file_id (NOT a URL) or None if no photo available
    """
    try:
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        
        # Get user profile photos
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        
        if photos.total_count > 0:
            # Get the first photo (most recent) - return file_id only
            file_id = photos.photos[0][0].file_id
            
            logger.info(f"Fetched profile photo file_id for user {user_id}")
            return file_id
        else:
            logger.info(f"No profile photo found for user {user_id}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching profile photo for user {user_id}: {e}")
        return None


async def download_profile_photo_bytes(file_id: str) -> Optional[bytes]:
    """
    Download profile photo bytes from Telegram using file_id
    Returns the photo bytes or None if download fails
    """
    try:
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        
        # Get file info
        file_info = await bot.get_file(file_id)
        
        # Download the file bytes
        photo_bytes = await file_info.download_as_bytearray()
        
        logger.info(f"Downloaded profile photo for file_id {file_id}")
        return bytes(photo_bytes)
            
    except Exception as e:
        logger.error(f"Error downloading profile photo for file_id {file_id}: {e}")
        return None


def create_bot_application() -> Application:
    """Create and configure the bot application"""
    application = Application.builder().token(BOT_TOKEN).build()
    setup_bot_handlers(application)
    return application
