"""
Complete System Test - Vouch Portal Premium
Tests all functionality: database, API, vouching, profiles, groups
"""
import asyncio
import sys
import os
from database import db

# Set UTF-8 encoding for Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# ANSI color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

test_results = []

def log_test(name, passed, details=""):
    """Log test result"""
    status = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
    print(f"{status} | {name}")
    if details:
        print(f"      {details}")
    test_results.append((name, passed, details))

async def test_database_connection():
    """Test 1: Database connection"""
    try:
        await db.connect()
        log_test("Database Connection", True, "Connected successfully")
        return True
    except Exception as e:
        log_test("Database Connection", False, f"Error: {e}")
        return False

async def test_schema_creation():
    """Test 2: Schema initialization"""
    try:
        await db.init_schema()
        log_test("Schema Creation", True, "All tables created")
        return True
    except Exception as e:
        log_test("Schema Creation", False, f"Error: {e}")
        return False

async def test_user_creation():
    """Test 3: Create users"""
    try:
        # Create test users
        user1 = await db.get_or_create_user(
            telegram_user_id=111111,
            username="alice",
            first_name="Alice",
            last_name="Test"
        )

        user2 = await db.get_or_create_user(
            telegram_user_id=222222,
            username="bob",
            first_name="Bob",
            last_name="Test"
        )

        user3 = await db.get_or_create_user(
            telegram_user_id=333333,
            username="charlie",
            first_name="Charlie",
            last_name="Test"
        )

        passed = (user1 is not None and user2 is not None and user3 is not None)
        log_test("User Creation", passed, f"Created 3 test users")
        return passed
    except Exception as e:
        log_test("User Creation", False, f"Error: {e}")
        return False

async def test_positive_vouch():
    """Test 4: Positive vouch"""
    try:
        result = await db.create_vouch(
            from_user_id=111111,
            to_username="bob",
            message="Great person to work with!",
            vote_type="positive"
        )

        passed = "error" not in result and result.get("pending") == False
        details = f"Alice vouched for Bob (positive)"
        log_test("Positive Vouch", passed, details)
        return passed
    except Exception as e:
        log_test("Positive Vouch", False, f"Error: {e}")
        return False

async def test_negative_vouch():
    """Test 5: Negative vouch"""
    try:
        result = await db.create_vouch(
            from_user_id=333333,
            to_username="bob",
            message="Had issues with communication",
            vote_type="negative"
        )

        passed = "error" not in result and result.get("pending") == False
        details = f"Charlie gave Bob a negative vouch"
        log_test("Negative Vouch", passed, details)
        return passed
    except Exception as e:
        log_test("Negative Vouch", False, f"Error: {e}")
        return False

async def test_pending_vouch():
    """Test 6: Pending vouch (user doesn't exist)"""
    try:
        result = await db.create_vouch(
            from_user_id=111111,
            to_username="david",  # User doesn't exist
            message="Looking forward to working with you!",
            vote_type="positive"
        )

        passed = "error" not in result and result.get("pending") == True
        details = f"Alice vouched for non-existent user 'david' - vouch is pending"
        log_test("Pending Vouch", passed, details)
        return passed
    except Exception as e:
        log_test("Pending Vouch", False, f"Error: {e}")
        return False

async def test_pending_vouch_processing():
    """Test 7: Process pending vouches when user joins"""
    try:
        # Create user 'david' who now joins
        user4 = await db.get_or_create_user(
            telegram_user_id=444444,
            username="david",
            first_name="David",
            last_name="Test"
        )

        # Process pending vouches
        count = await db.process_pending_vouches(444444, "david")

        # Check if vouch was applied
        user_after = await db.get_user(444444)

        passed = count == 1 and user_after['positive_votes'] == 1
        details = f"Processed {count} pending vouch(s) - David now has {user_after['positive_votes']} positive vote"
        log_test("Pending Vouch Processing", passed, details)
        return passed
    except Exception as e:
        log_test("Pending Vouch Processing", False, f"Error: {e}")
        return False

async def test_self_vouch_prevention():
    """Test 8: Prevent self-vouching"""
    try:
        result = await db.create_vouch(
            from_user_id=111111,
            to_username="alice",  # Same user
            message="I'm great!",
            vote_type="positive"
        )

        passed = "error" in result and "cannot vouch for yourself" in result["error"].lower()
        details = "Self-vouch correctly blocked"
        log_test("Self-Vouch Prevention", passed, details)
        return passed
    except Exception as e:
        log_test("Self-Vouch Prevention", False, f"Error: {e}")
        return False

async def test_duplicate_vouch_prevention():
    """Test 9: Prevent duplicate vouches"""
    try:
        # Try to vouch for Bob again
        result = await db.create_vouch(
            from_user_id=111111,
            to_username="bob",
            message="Another vouch",
            vote_type="positive"
        )

        passed = "error" in result and "already vouched" in result["error"].lower()
        details = "Duplicate vouch correctly blocked"
        log_test("Duplicate Vouch Prevention", passed, details)
        return passed
    except Exception as e:
        log_test("Duplicate Vouch Prevention", False, f"Error: {e}")
        return False

async def test_rank_calculation():
    """Test 10: Rank calculation system"""
    try:
        # Get Bob's user data - should have 1 positive and 1 negative
        bob = await db.get_user(222222)

        # Bob should have: 1 positive (from Alice), 1 negative (from Charlie)
        expected_rank = "unverified"  # 1 positive vote, 50% trust ratio

        passed = bob['rank'] == expected_rank
        details = f"Bob's rank: {bob['rank']} (positive: {bob['positive_votes']}, negative: {bob['negative_votes']}, rating: {bob['rating_percentage']:.1f}%)"
        log_test("Rank Calculation", passed, details)
        return passed
    except Exception as e:
        log_test("Rank Calculation", False, f"Error: {e}")
        return False

async def test_profile_update():
    """Test 11: Profile update (bio, location)"""
    try:
        result = await db.update_user_profile(
            telegram_user_id=111111,
            bio="I'm a software developer passionate about building great products",
            location="San Francisco, CA"
        )

        passed = "error" not in result
        details = f"Alice's profile updated with bio and location"
        log_test("Profile Update", passed, details)
        return passed
    except Exception as e:
        log_test("Profile Update", False, f"Error: {e}")
        return False

async def test_streak_system():
    """Test 12: Daily streak tracking"""
    try:
        # Update streak for Alice
        result = await db.update_streak(111111)

        # Check if streak was set to 1
        alice = await db.get_user(111111)

        passed = alice['streak_days'] == 1
        details = f"Alice's streak: {alice['streak_days']} days"
        log_test("Streak System", passed, details)
        return passed
    except Exception as e:
        log_test("Streak System", False, f"Error: {e}")
        return False

async def test_vouch_retrieval():
    """Test 13: Get vouches for user"""
    try:
        # Get vouches received by Bob
        vouches = await db.get_vouches_for_user(222222)

        # Bob should have 2 vouches (1 positive, 1 negative)
        passed = len(vouches) == 2
        details = f"Bob has {len(vouches)} vouches"
        log_test("Vouch Retrieval", passed, details)
        return passed
    except Exception as e:
        log_test("Vouch Retrieval", False, f"Error: {e}")
        return False

async def test_rating_percentage():
    """Test 14: Rating percentage calculation"""
    try:
        bob = await db.get_user(222222)

        # Bob has 1 positive and 1 negative = 50%
        expected_rating = 50.0
        actual_rating = float(bob['rating_percentage'])

        passed = abs(actual_rating - expected_rating) < 0.1
        details = f"Bob's rating: {actual_rating:.1f}% (expected {expected_rating}%)"
        log_test("Rating Percentage", passed, details)
        return passed
    except Exception as e:
        log_test("Rating Percentage", False, f"Error: {e}")
        return False

async def test_community_groups():
    """Test 15: Community groups"""
    try:
        # Add a test community group
        group = await db.add_community_group(
            name="Vouch Portal Official",
            telegram_link="https://t.me/vouchportal",
            description="Official Vouch Portal community - discuss features and connect with others",
            member_count=150,
            icon_emoji="🚀"
        )

        # Get all groups
        groups = await db.get_community_groups()

        passed = len(groups) >= 1
        details = f"Added community group: {group['name']} ({group['member_count']} members)"
        log_test("Community Groups", passed, details)
        return passed
    except Exception as e:
        log_test("Community Groups", False, f"Error: {e}")
        return False

async def test_leaderboard():
    """Test 16: Leaderboard generation"""
    try:
        # Get most vouched leaderboard
        leaderboard = await db.get_leaderboard('most_vouched', limit=10)

        passed = isinstance(leaderboard, list)
        details = f"Leaderboard contains {len(leaderboard)} users"
        log_test("Leaderboard", passed, details)
        return passed
    except Exception as e:
        log_test("Leaderboard", False, f"Error: {e}")
        return False

async def test_activity_feed():
    """Test 17: Activity feed"""
    try:
        activity = await db.get_recent_activity(limit=20)

        passed = isinstance(activity, list)
        details = f"Activity feed has {len(activity)} events"
        log_test("Activity Feed", passed, details)
        return passed
    except Exception as e:
        log_test("Activity Feed", False, f"Error: {e}")
        return False

async def test_vouch_editing():
    """Test 18: Edit vouch message"""
    try:
        # Get Alice's vouch to Bob
        vouches_given = await db.get_vouches_by_user(111111)
        vouch_to_bob = [v for v in vouches_given if v['to_user_id'] == 222222]

        if not vouch_to_bob:
            log_test("Edit Vouch", False, "No vouch found to edit")
            return False

        vouch_id = vouch_to_bob[0]['id']

        # Edit the vouch
        result = await db.update_vouch(
            vouch_id=vouch_id,
            from_user_id=111111,
            new_message="Updated: Really professional and reliable!"
        )

        passed = "error" not in result
        details = "Vouch message updated successfully"
        log_test("Edit Vouch", passed, details)
        return passed
    except Exception as e:
        log_test("Edit Vouch", False, f"Error: {e}")
        return False

async def test_analytics():
    """Test 19: Analytics summary"""
    try:
        analytics = await db.get_analytics_summary()

        passed = (
            'total_users' in analytics and
            'total_vouches' in analytics and
            'active_users' in analytics
        )
        details = f"Total users: {analytics.get('total_users', 0)}, Total vouches: {analytics.get('total_vouches', 0)}"
        log_test("Analytics", passed, details)
        return passed
    except Exception as e:
        log_test("Analytics", False, f"Error: {e}")
        return False

async def test_full_rank_progression():
    """Test 20: Full rank progression (unverified -> top_tier)"""
    try:
        # Create a new user for rank testing
        user5 = await db.get_or_create_user(
            telegram_user_id=555555,
            username="eve",
            first_name="Eve",
            last_name="Test"
        )

        # Give multiple positive vouches to test rank progression
        for i in range(25):  # Enough to reach top_tier
            test_user_id = 100000 + i
            await db.get_or_create_user(
                telegram_user_id=test_user_id,
                username=f"testuser{i}",
                first_name=f"Test{i}"
            )

            await db.create_vouch(
                from_user_id=test_user_id,
                to_username="eve",
                message=f"Test vouch {i}",
                vote_type="positive"
            )

        # Get Eve's updated profile
        eve = await db.get_user(555555)

        # With 25 positive votes and 0 negative, should be top_tier
        passed = eve['rank'] == 'top_tier' and eve['positive_votes'] == 25
        details = f"Eve's rank: {eve['rank']} with {eve['positive_votes']} positive votes (rating: {eve['rating_percentage']:.1f}%)"
        log_test("Full Rank Progression", passed, details)
        return passed
    except Exception as e:
        log_test("Full Rank Progression", False, f"Error: {e}")
        return False

async def run_all_tests():
    """Run all tests"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}  VOUCH PORTAL - COMPLETE SYSTEM TEST{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    tests = [
        test_database_connection,
        test_schema_creation,
        test_user_creation,
        test_positive_vouch,
        test_negative_vouch,
        test_pending_vouch,
        test_pending_vouch_processing,
        test_self_vouch_prevention,
        test_duplicate_vouch_prevention,
        test_rank_calculation,
        test_profile_update,
        test_streak_system,
        test_vouch_retrieval,
        test_rating_percentage,
        test_community_groups,
        test_leaderboard,
        test_activity_feed,
        test_vouch_editing,
        test_analytics,
        test_full_rank_progression
    ]

    passed_count = 0
    failed_count = 0

    for test in tests:
        try:
            result = await test()
            if result:
                passed_count += 1
            else:
                failed_count += 1
        except Exception as e:
            print(f"{RED}✗ FATAL ERROR in {test.__name__}: {e}{RESET}")
            failed_count += 1

    # Print summary
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}  TEST SUMMARY{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")
    print(f"{GREEN}Passed: {passed_count}{RESET}")
    print(f"{RED}Failed: {failed_count}{RESET}")
    print(f"Total:  {passed_count + failed_count}")

    success_rate = (passed_count / (passed_count + failed_count) * 100) if (passed_count + failed_count) > 0 else 0
    print(f"\n{BLUE}Success Rate: {success_rate:.1f}%{RESET}")

    if failed_count == 0:
        print(f"\n{GREEN}{'='*60}")
        print(f"  [SUCCESS] ALL TESTS PASSED - SYSTEM 100% FUNCTIONAL")
        print(f"{'='*60}{RESET}\n")
    else:
        print(f"\n{YELLOW}{'='*60}")
        print(f"  [WARNING] {failed_count} TEST(S) FAILED - REVIEW REQUIRED")
        print(f"{'='*60}{RESET}\n")

    # Cleanup
    await db.disconnect()

    return failed_count == 0

if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Tests interrupted by user{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}FATAL ERROR: {e}{RESET}")
        sys.exit(1)
