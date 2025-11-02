"""
Vouch Beacon - Main Entry Point
Unified launcher for the complete Vouch Beacon ecosystem
"""
import os
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_environment():
    """Validate that all required environment variables are set"""
    required_vars = [
        'BOT_TOKEN',
        'WEBHOOK_URL',
        'DATABASE_URL',
        'ADMIN_ID',
        'JWT_SECRET'
    ]

    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        logger.error("Missing required environment variables:")
        for var in missing:
            logger.error(f"  - {var}")
        logger.error("\nPlease set these in your .env file or environment.")
        logger.error("See .env.beacon.example for reference.")
        sys.exit(1)

    logger.info("Environment variables validated successfully")

def main():
    """Main entry point for Vouch Beacon"""
    logger.info("=" * 60)
    logger.info("VOUCH BEACON - Starting System")
    logger.info("=" * 60)

    # Check environment
    check_environment()

    # Import and run the API (which initializes bot internally)
    logger.info("Initializing Vouch Beacon API and Bot...")

    try:
        from api_beacon import app
        import uvicorn

        port = int(os.getenv("PORT", "5000"))
        is_production = os.getenv("REPLIT_ENVIRONMENT", "development") == "production"

        logger.info(f"Starting server on port {port}")
        logger.info(f"Mode: {'PRODUCTION' if is_production else 'DEVELOPMENT'}")
        logger.info(f"Webhook URL: {os.getenv('WEBHOOK_URL')}")
        logger.info("-" * 60)

        uvicorn.run(
            "api_beacon:app",
            host="0.0.0.0",
            port=port,
            reload=not is_production,
            log_level="info"
        )

    except Exception as e:
        logger.error(f"Failed to start Vouch Beacon: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
