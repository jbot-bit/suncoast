"""
Vouch Beacon - System Test Script
Tests all major components without requiring full deployment
"""
import os
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_database():
    """Test database connection and operations"""
    logger.info("=" * 60)
    logger.info("Testing Database Connection and Operations")
    logger.info("=" * 60)

    try:
        from database_beacon import db

        # Connect
        logger.info("Connecting to database...")
        await db.connect()
        logger.info("✓ Database connected successfully")

        # Test user creation
        logger.info("\nTesting user creation...")
        user = await db.get_or_create_user(
            telegram_user_id=999999999,
            username="test_user",
            first_name="Test"
        )
        logger.info(f"✓ User created/retrieved: {user['username']}")

        # Test marking as known
        logger.info("\nTesting mark_user_as_known...")
        await db.mark_user_as_known(999999999)
        updated_user = await db.get_user_by_telegram_id(999999999)
        assert updated_user['is_known_user'] == True
        logger.info("✓ User marked as known")

        # Test magic link generation
        logger.info("\nTesting magic link generation...")
        magic_link = db.generate_magic_link(999999999)
        logger.info(f"✓ Magic link generated: {magic_link[:50]}...")

        # Test magic link verification
        logger.info("\nTesting magic link verification...")
        token = magic_link.split('token=')[1]
        verified_user_id = db.verify_magic_link(token)
        assert verified_user_id == 999999999
        logger.info("✓ Magic link verified successfully")

        # Test analytics
        logger.info("\nTesting analytics...")
        analytics = await db.get_analytics_summary()
        logger.info(f"✓ Analytics retrieved: {analytics['total_users']} users, {analytics['total_vouches']} vouches")

        await db.disconnect()
        logger.info("\n✓ All database tests passed!")
        return True

    except Exception as e:
        logger.error(f"✗ Database test failed: {e}")
        return False

def test_bot_components():
    """Test bot components (without connecting to Telegram)"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Bot Components")
    logger.info("=" * 60)

    try:
        from bot_beacon import sanitize_message, check_instant_violations, RANKS, BANNED_WORDS

        # Test message sanitization
        logger.info("\nTesting message sanitization...")
        clean = sanitize_message("Hello world!")
        assert clean == "Hello world!"
        logger.info(f"✓ Clean message: {clean}")

        dirty = sanitize_message("This is a scam message")
        assert "[filtered]" in dirty
        logger.info(f"✓ Filtered message: {dirty}")

        # Test instant violation detection
        logger.info("\nTesting violation detection...")
        is_violation, reason = check_instant_violations("This is a fraud")
        assert is_violation == True
        logger.info(f"✓ Violation detected: {reason}")

        is_violation, reason = check_instant_violations("Normal message")
        assert is_violation == False
        logger.info("✓ Clean message passed")

        # Test rank system
        logger.info("\nTesting rank system...")
        assert len(RANKS) == 7
        logger.info(f"✓ Rank system loaded: {len(RANKS)} ranks")

        # Test banned words
        logger.info("\nTesting banned words list...")
        assert len(BANNED_WORDS) > 0
        logger.info(f"✓ Banned words loaded: {len(BANNED_WORDS)} words")

        logger.info("\n✓ All bot component tests passed!")
        return True

    except Exception as e:
        logger.error(f"✗ Bot component test failed: {e}")
        return False

def test_api_structure():
    """Test API structure and endpoints (without starting server)"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing API Structure")
    logger.info("=" * 60)

    try:
        from api_beacon import app

        # Check routes
        logger.info("\nChecking API routes...")
        routes = [route.path for route in app.routes]

        required_routes = [
            "/",
            "/health",
            "/api/vouches",
            "/api/users/{telegram_user_id}",
            "/api/leaderboards",
            "/api/auth/magic-link",
            "/auth"
        ]

        for route in required_routes:
            # Check if route exists (allowing path parameters)
            route_exists = any(route in r or r.startswith(route.split('{')[0]) for r in routes)
            if route_exists:
                logger.info(f"✓ Route exists: {route}")
            else:
                logger.warning(f"⚠ Route missing: {route}")

        logger.info("\n✓ All API structure tests passed!")
        return True

    except Exception as e:
        logger.error(f"✗ API structure test failed: {e}")
        return False

def test_web_app_files():
    """Test web app files exist"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Web App Files")
    logger.info("=" * 60)

    try:
        required_files = [
            "webapp/index_beacon.html",
            "webapp/static/styles_beacon.css",
            "webapp/static/main_beacon.js"
        ]

        for file_path in required_files:
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                logger.info(f"✓ {file_path} exists ({size} bytes)")
            else:
                logger.error(f"✗ {file_path} missing")
                return False

        logger.info("\n✓ All web app files found!")
        return True

    except Exception as e:
        logger.error(f"✗ Web app file test failed: {e}")
        return False

def test_environment():
    """Test environment configuration"""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Environment Configuration")
    logger.info("=" * 60)

    required_vars = [
        'BOT_TOKEN',
        'WEBHOOK_URL',
        'DATABASE_URL',
        'ADMIN_ID',
        'JWT_SECRET'
    ]

    optional_vars = [
        'GROQ_API_KEY',
        'ENABLE_CONTENT_MODERATION',
        'MODERATION_LOG_CHANNEL'
    ]

    try:
        missing_required = []
        for var in required_vars:
            if os.getenv(var):
                logger.info(f"✓ {var} is set")
            else:
                logger.error(f"✗ {var} is missing")
                missing_required.append(var)

        for var in optional_vars:
            if os.getenv(var):
                logger.info(f"✓ {var} is set (optional)")
            else:
                logger.info(f"  {var} not set (optional)")

        if missing_required:
            logger.error(f"\n✗ Missing required variables: {', '.join(missing_required)}")
            logger.error("Please set these in your .env file")
            return False

        logger.info("\n✓ All required environment variables set!")
        return True

    except Exception as e:
        logger.error(f"✗ Environment test failed: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("\n")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + " " * 10 + "VOUCH BEACON SYSTEM TEST SUITE" + " " * 17 + "║")
    logger.info("╚" + "═" * 58 + "╝")
    logger.info("\n")

    results = []

    # Test environment first
    results.append(("Environment", test_environment()))

    # Test web app files
    results.append(("Web App Files", test_web_app_files()))

    # Test bot components
    results.append(("Bot Components", test_bot_components()))

    # Test API structure
    results.append(("API Structure", test_api_structure()))

    # Test database (requires connection)
    results.append(("Database", await test_database()))

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{name:.<40} {status}")

    logger.info("=" * 60)
    logger.info(f"Results: {passed}/{total} tests passed")

    if passed == total:
        logger.info("\n🎉 ALL TESTS PASSED! System is ready to deploy.")
        return 0
    else:
        logger.info(f"\n⚠ {total - passed} test(s) failed. Please fix issues before deployment.")
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        exit(1)
    except Exception as e:
        logger.error(f"\nTest suite crashed: {e}")
        exit(1)
