"""
Test database connection validation
Ensures proper error handling when DATABASE_URL is not set
"""
import os
import asyncio
from database import Database


def test_database_url_missing():
    """Test that Database raises ValueError when DATABASE_URL is not set"""
    # Save original value
    original_url = os.environ.get("DATABASE_URL")
    
    try:
        # Remove DATABASE_URL
        if "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]
        
        # Create database instance
        db = Database()
        
        # Attempt to connect should raise ValueError
        try:
            asyncio.run(db.connect())
            assert False, "Expected ValueError but connection succeeded"
        except ValueError as e:
            # Check error message contains helpful information
            error_msg = str(e)
            assert "DATABASE_URL" in error_msg
            assert "environment variable" in error_msg
            assert ".env" in error_msg
            print(f"✅ Correct error raised: {error_msg[:100]}...")
        except Exception as e:
            assert False, f"Expected ValueError but got {type(e).__name__}: {e}"
            
    finally:
        # Restore original value
        if original_url:
            os.environ["DATABASE_URL"] = original_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]


if __name__ == "__main__":
    print("Testing database validation...")
    test_database_url_missing()
    print("\n✅ All tests passed!")
