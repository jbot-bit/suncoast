"""
Vouch Beacon Guardian Bot
Implements Welcome Mat, Guardian Protocol, and Vouch Flow
"""
import os
import logging
import re
import json
import asyncio
from datetime import datetime
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from database_beacon import db
from improvements_beacon import (
    ConnectionSuggester,
    ProgressiveModerator,
    StreakSystem
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
BOT_USERNAME = os.getenv("BOT_USERNAME", "VouchBeaconBot")

# Initialize improvement modules
connection_suggester = ConnectionSuggester(db)
progressive_moderator = ProgressiveModerator(db)
streak_system = StreakSystem(db)

# TOS Compliance - Banned words and phrases
BANNED_WORDS = [
    "scam", "fraud", "fake", "cheat", "steal", "hack", "stolen",
    "phishing", "ponzi", "pyramid", "mlm", "money laundering",
    "kill", "murder", "attack", "bomb", "terrorism", "terrorist",
    "violence", "hurt", "harm", "weapon", "gun", "explosive",
    "drug", "cocaine", "heroin", "meth", "illegal", "smuggle",
    "counterfeit", "piracy", "pirated", "cracked",
    "nazi", "fascist", "genocide", "supremacy", "racist",
    "porn", "xxx", "nsfw", "sexual", "nude",
    "casino", "poker", "bet", "gambling", "lottery",
    "credit card", "social security", "ssn", "password",
    "bank account", "routing number"
]

SUSPICIOUS_PATTERNS = [
    r'(?:http[s]?://)?(?:www\.)?[a-zA-Z0-9-]+\.(?:xyz|tk|ml|ga|cf|gq)\b',
    r'[!@#$%^&*()]{4,}',
    r'\b[A-Z]{15,}\b',
    r'\+\d[\d\-]{8,}',
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    r'\b(?:0x[a-fA-F0-9]{40}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-zA-Z0-9]{39,59})\b'
]


def sanitize_message(text: str) -> str:
    """Sanitize messages for TOS compliance"""
    if not text:
        return ""

    sanitized = text

    # Check for banned words
    for word in BANNED_WORDS:
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        sanitized = pattern.sub("[filtered]", sanitized)

    # Check for suspicious patterns
    for pattern in SUSPICIOUS_PATTERNS:
        regex = re.compile(pattern, re.IGNORECASE)
        sanitized = regex.sub("[filtered]", sanitized)

    # Remove excessive whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()

    # Check if message is mostly filtered
    filtered_count = sanitized.count("[filtered]")
    word_count = len(sanitized.split())

    if filtered_count > 0 and word_count > 0:
        if filtered_count / word_count > 0.5:
            return None  # Return None to indicate message should be rejected

    return sanitized[:120]


def check_instant_violations(text: str) -> tuple[bool, str]:
    """Instant pattern-based violation detection"""
    if not text:
        return False, ""

    text_lower = text.lower()

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


# ==================== WELCOME MAT FLOW ====================

async def welcome_mat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Welcome Mat: Ephemeral message for new users in groups
    Shows a deep-linked [Connect] button that triggers /start
    """
    if not update.message or not update.message.text:
        return

    # Only in groups
    if update.message.chat.type not in ['group', 'supergroup']:
        return

    user = update.effective_user
    group_name = update.message.chat.title

    # Check if user is in database
    existing_user = await db.get_user_by_telegram_id(user.id)

    if existing_user and existing_user.get("is_known_user"):
        # User already completed Welcome Mat
        return

    # New user detected - post ephemeral welcome message
    deep_link = f"https://t.me/{BOT_USERNAME}?start=connect_{group_name}"

    keyboard = [[InlineKeyboardButton("🔗 Connect", url=deep_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_msg = await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        f"To participate in vouching, click Connect below to link your account.\n\n"
        f"_This message will self-destruct in 60 seconds._",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    # Schedule message deletion in 60 seconds
    async def delete_welcome():
        await asyncio.sleep(60)
        try:
            await welcome_msg.delete()
        except Exception as e:
            logger.error(f"Failed to delete welcome message: {e}")

    # Run deletion in background
    asyncio.create_task(delete_welcome())

    # Create user record with is_known_user = FALSE
    if not existing_user:
        await db.get_or_create_user(
            telegram_user_id=user.id,
            username=user.username,
            first_name=user.first_name
        )


# ==================== GUARDIAN PROTOCOL ====================

async def guardian_protocol_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Guardian Protocol: TOS compliance filter
    Intercepts all group messages and deletes violations
    """
    if not update.message or not update.message.text:
        return

    # Only in groups
    if update.message.chat.type not in ['group', 'supergroup']:
        return

    # Don't moderate admin or bot messages
    if update.effective_user.id == ADMIN_ID or update.effective_user.is_bot:
        return

    message_text = update.message.text
    user = update.effective_user
    group_name = update.message.chat.title

    # Check for instant violations
    is_violation, reason = check_instant_violations(message_text)

    if is_violation:
        # DELETE IMMEDIATELY
        try:
            await update.message.delete()
            logger.info(f"Deleted TOS violation from {user.id} in {group_name}: {reason}")

            # Log violation event to database
            await db.log_event(
                event_type="violation",
                metadata={
                    "user_id": user.id,
                    "group": group_name,
                    "reason": reason,
                    "message_preview": message_text[:100]
                }
            )

            # Progressive moderation - escalating punishments
            await progressive_moderator.handle_violation(
                user_id=user.id,
                reason=reason,
                bot=context.bot,
                context=context
            )

            # Log to admin
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🛡️ **Guardian Protocol Alert**\n\n"
                         f"**Group:** {group_name}\n"
                         f"**User:** {user.first_name} (@{user.username or 'no_username'})\n"
                         f"**Reason:** {reason}\n"
                         f"**Message:** {message_text[:100]}...\n\n"
                         f"_Message deleted._",
                    parse_mode="Markdown"
                )
            except:
                pass

        except Exception as e:
            logger.error(f"Failed to delete violation: {e}")


# ==================== VOUCH FLOW ====================

async def vouch_flow_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Vouch Flow: Keyword detection + emoji reaction + DM prompts
    1. Detect vouch keywords in group messages
    2. Delete trigger message
    3. React with emoji in group
    4. Send DM to giver with [Add Comment] and [Undo Vouch] buttons
    """
    if not update.message or not update.message.text:
        return

    # Only in groups
    if update.message.chat.type not in ['group', 'supergroup']:
        return

    text = update.message.text.strip().lower()
    user = update.effective_user
    group_chat_id = update.message.chat.id

    # Check if user is muted (progressive moderation)
    if progressive_moderator.is_muted(user.id):
        # Delete message silently
        try:
            await update.message.delete()
        except:
            pass
        return

    # Vouch patterns
    patterns = [
        r'(?:^|\s)vouch\s+@?(\w+)(?:\s+[-:]?\s*(.*))?',
        r'(?:^|\s)\+1\s+@?(\w+)(?:\s+[-:]?\s*(.*))?',
        r'(?:^|\s)recommend\s+@?(\w+)(?:\s+[-:]?\s*(.*))?',
    ]

    # Try to match
    match = None
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            match = m
            break

    if not match:
        return

    target_username = match.group(1).lower()

    # STEP 1: Delete the trigger message
    try:
        await update.message.delete()
    except Exception as e:
        logger.error(f"Failed to delete trigger message: {e}")

    # STEP 2: Create vouch in database
    try:
        result = await db.create_vouch(
            from_telegram_id=user.id,
            to_username=target_username,
            group_chat_id=group_chat_id,
            comment=None  # No comment yet
        )

        if "error" in result:
            # React with ❌
            try:
                # Send error message briefly then delete
                error_msg = await context.bot.send_message(
                    chat_id=update.message.chat.id,
                    text=f"❌ {result['error']}",
                    reply_to_message_id=update.message.message_id if update.message else None
                )

                # Delete after 5 seconds
                async def delete_error():
                    await asyncio.sleep(5)
                    try:
                        await error_msg.delete()
                    except:
                        pass

                asyncio.create_task(delete_error())
            except:
                pass
            return

        # STEP 3: React with ✅ emoji in group
        try:
            # Find the original message to react to (since we deleted trigger)
            # Instead, send a brief confirmation that self-destructs
            confirm_msg = await context.bot.send_message(
                chat_id=update.message.chat.id,
                text=f"✅ @{user.username or user.first_name} vouched for @{target_username}"
            )

            # Delete after 10 seconds
            async def delete_confirm():
                await asyncio.sleep(10)
                try:
                    await confirm_msg.delete()
                except:
                    pass

            asyncio.create_task(delete_confirm())
        except Exception as e:
            logger.error(f"Failed to send confirmation: {e}")

        # STEP 4: Send DM to giver with buttons
        vouch_id = result["vouch_id"]

        keyboard = [
            [InlineKeyboardButton("💬 Add Comment", callback_data=f"add_comment_{vouch_id}")],
            [InlineKeyboardButton("↩️ Undo Vouch", callback_data=f"undo_vouch_{vouch_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=f"✅ Your vouch for @{target_username} has been recorded!\n\n"
                     f"You can optionally add a comment or undo this vouch.",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send DM to voucher: {e}")

        logger.info(f"Vouch created: {user.username} → @{target_username} in group {group_chat_id}")

    except Exception as e:
        logger.error(f"Vouch flow error: {e}")


# ==================== COMMAND HANDLERS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /start command
    - Mark user as known (completed Welcome Mat)
    - Update streak
    - Send magic link to webapp
    - Suggest connections if isolated
    """
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Get or create user
    user_data = await db.get_or_create_user(
        telegram_user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )

    # Mark user as known
    await db.mark_user_as_known(user.id)

    # Update streak system
    current_streak = await streak_system.check_and_update_streak(user.id)

    # Generate magic link
    magic_link = db.generate_magic_link(user.id)

    # Get user stats
    stats = await db.get_user_stats(user.id)

    keyboard = [[InlineKeyboardButton("🚀 Open Vouch Beacon", url=magic_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Build message with streak
    message = f"**Welcome to Vouch Beacon** 🤝\n\n"
    message += f"**Your Stats:**\n"
    message += f"• Vouches Received: {stats['vouches_received']}\n"
    message += f"• Vouches Given: {stats['vouches_given']}\n"

    if current_streak > 0:
        message += f"• 🔥 Current Streak: {current_streak} days\n"

    message += f"\nClick below to access your profile!"

    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

    # Send connection suggestions if user is isolated (0 vouches)
    if stats['vouches_received'] == 0 and stats['vouches_given'] == 0:
        # Wait a bit, then send suggestions
        await asyncio.sleep(2)
        await connection_suggester.send_connection_suggestions(
            user_id=user.id,
            bot=context.bot
        )


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /check @username - View vouches for a user
    """
    user = update.effective_user

    # Only work in DMs
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
            "Example: `/check @mike`",
            parse_mode="Markdown"
        )
        return

    target_username = context.args[0].replace("@", "").lower()

    # Find user
    target_user = await db.get_user_by_username(target_username)

    if not target_user:
        await update.message.reply_text(
            f"User @{target_username} hasn't received any vouches yet.",
            parse_mode="Markdown"
        )
        return

    # Get vouches
    vouches = await db.get_vouches_for_user(target_user["telegram_user_id"], limit=20)

    response = f"**Vouches for @{target_username}**\n\n"
    response += f"**Total Vouches:** {len(vouches)}\n\n"

    if vouches:
        response += "**Recent Vouches:**\n\n"
        for vouch in vouches[:10]:
            from_name = vouch['from_username'] or vouch['from_first_name']
            response += f"• **@{from_name}**"
            if vouch['comment']:
                response += f": _{vouch['comment']}_"
            response += "\n"
    else:
        response += "_No vouches yet._"

    await update.message.reply_text(response.strip(), parse_mode="Markdown")


# ==================== CALLBACK QUERY HANDLERS ====================

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline buttons"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("add_comment_"):
        vouch_id = int(data.split("_")[2])

        # Ask user to send comment
        await query.edit_message_text(
            f"💬 **Add Comment to Vouch**\n\n"
            f"Reply to this message with your comment (max 120 characters).\n\n"
            f"Type 'cancel' to skip.",
            parse_mode="Markdown"
        )

        # Store vouch_id in user_data for next message
        context.user_data["pending_comment_vouch_id"] = vouch_id

    elif data.startswith("undo_vouch_"):
        vouch_id = int(data.split("_")[2])

        # Undo vouch
        result = await db.undo_vouch(vouch_id, query.from_user.id)

        if "error" in result:
            await query.edit_message_text(f"❌ {result['error']}")
        else:
            await query.edit_message_text("↩️ Vouch undone successfully!")

    elif data.startswith("quick_vouch_"):
        # Quick vouch from connection suggestions
        target_telegram_id = int(data.split("_")[2])
        from_user_id = query.from_user.id

        # Get target user info
        target_user = await db.get_user_by_telegram_id(target_telegram_id)
        if not target_user:
            await query.edit_message_text("❌ User not found.")
            return

        target_username = target_user['username'] or target_user['first_name']

        # Create vouch
        result = await db.create_vouch(
            from_telegram_id=from_user_id,
            to_username=target_username,
            group_chat_id=None,  # From suggestion, not a group
            comment=None
        )

        if "error" in result:
            await query.edit_message_text(f"❌ {result['error']}")
        else:
            await query.edit_message_text(
                f"✅ **Vouch Created!**\n\n"
                f"You vouched for @{target_username}\n\n"
                f"Building your network strengthens your reputation!",
                parse_mode="Markdown"
            )


async def comment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle comment messages for vouches"""
    if not update.message or not update.message.text:
        return

    # Only in DMs
    if update.message.chat.type != 'private':
        return

    # Check if user has pending comment
    vouch_id = context.user_data.get("pending_comment_vouch_id")

    if not vouch_id:
        return

    comment = update.message.text.strip()

    if comment.lower() == "cancel":
        await update.message.reply_text("Comment cancelled.")
        context.user_data.pop("pending_comment_vouch_id", None)
        return

    # Sanitize comment
    sanitized_comment = sanitize_message(comment)

    if not sanitized_comment:
        await update.message.reply_text(
            "❌ Your comment contains prohibited content. Please try again with appropriate content."
        )
        return

    # Update vouch
    result = await db.update_vouch_comment(
        vouch_id=vouch_id,
        from_telegram_id=update.effective_user.id,
        comment=sanitized_comment
    )

    if "error" in result:
        await update.message.reply_text(f"❌ {result['error']}")
    else:
        await update.message.reply_text(f"✅ Comment added: \"{sanitized_comment}\"")

    context.user_data.pop("pending_comment_vouch_id", None)


# ==================== BOT SETUP ====================

def setup_bot_handlers(application: Application):
    """Setup all bot command handlers"""
    # Command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("check", check_command))

    # Callback query handler
    application.add_handler(CallbackQueryHandler(callback_query_handler))

    # Group message handlers (priority order matters!)
    # 1. Welcome Mat (priority 0 - check if user is new)
    application.add_handler(MessageHandler(
        filters.TEXT & (filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP),
        welcome_mat_handler
    ), group=0)

    # 2. Guardian Protocol (priority 1 - TOS filtering)
    application.add_handler(MessageHandler(
        filters.TEXT & (filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP),
        guardian_protocol_handler
    ), group=1)

    # 3. Vouch Flow (priority 2 - keyword detection)
    application.add_handler(MessageHandler(
        filters.TEXT & (filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP),
        vouch_flow_handler
    ), group=2)

    # 4. Comment handler (DMs only)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE,
        comment_handler
    ), group=3)

    logger.info("Vouch Beacon bot handlers setup complete")
    logger.info("✓ Welcome Mat ENABLED")
    logger.info("✓ Guardian Protocol ENABLED")
    logger.info("✓ Vouch Flow ENABLED")


def create_bot_application() -> Application:
    """Create and configure the bot application"""
    application = Application.builder().token(BOT_TOKEN).build()
    setup_bot_handlers(application)
    return application
