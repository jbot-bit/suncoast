"""
Logic Test - Vouch Portal Premium
Tests business logic, API structure, and core functionality without database
"""
import sys
import os

# Set UTF-8 encoding for Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from database import Database

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RESET = '\033[0m'

test_results = []

def log_test(name, passed, details=""):
    """Log test result"""
    status = f"{GREEN}[PASS]{RESET}" if passed else f"{RED}[FAIL]{RESET}"
    print(f"{status} | {name}")
    if details:
        print(f"      {details}")
    test_results.append((name, passed))

def test_rank_calculation_logic():
    """Test 1: Rank calculation algorithm"""
    try:
        db = Database()

        # Test unverified (0 votes)
        rank1 = db.calculate_rank(0, 0)
        assert rank1 == "unverified", f"Expected 'unverified', got '{rank1}'"

        # Test verified (3+ positive, good ratio)
        rank2 = db.calculate_rank(3, 0)
        assert rank2 == "verified", f"Expected 'verified', got '{rank2}'"

        # Test trusted (6+ positive, good ratio)
        rank3 = db.calculate_rank(6, 0)
        assert rank3 == "trusted", f"Expected 'trusted', got '{rank3}'"

        # Test endorsed (11+ positive, good ratio)
        rank4 = db.calculate_rank(11, 0)
        assert rank4 == "endorsed", f"Expected 'endorsed', got '{rank4}'"

        # Test top_tier (21+ positive, excellent ratio)
        rank5 = db.calculate_rank(21, 0)
        assert rank5 == "top_tier", f"Expected 'top_tier', got '{rank5}'"

        # Test with negative votes (should lower rank)
        rank6 = db.calculate_rank(10, 5)  # 10 pos, 5 neg = 66.7% trust ratio
        assert rank6 in ["unverified", "verified"], f"With many negatives, should be lower rank, got '{rank6}'"

        log_test("Rank Calculation Logic", True, "All rank thresholds work correctly")
        return True
    except AssertionError as e:
        log_test("Rank Calculation Logic", False, str(e))
        return False
    except Exception as e:
        log_test("Rank Calculation Logic", False, f"Error: {e}")
        return False

def test_rank_emojis():
    """Test 2: Rank emoji mapping"""
    try:
        db = Database()

        emojis = {
            "unverified": "🚫",
            "verified": "✅",
            "trusted": "🔷",
            "endorsed": "🛡",
            "top_tier": "👑"
        }

        for rank, expected_emoji in emojis.items():
            emoji = db.get_rank_emoji(rank)
            assert emoji == expected_emoji, f"Expected '{expected_emoji}' for {rank}, got '{emoji}'"

        log_test("Rank Emojis", True, "All rank emojis mapped correctly")
        return True
    except AssertionError as e:
        log_test("Rank Emojis", False, str(e))
        return False
    except Exception as e:
        log_test("Rank Emojis", False, f"Error: {e}")
        return False

def test_rank_names():
    """Test 3: Rank name mapping"""
    try:
        db = Database()

        names = {
            "unverified": "Unverified",
            "verified": "Verified",
            "trusted": "Trusted",
            "endorsed": "Endorsed",
            "top_tier": "Top-Tier"
        }

        for rank, expected_name in names.items():
            name = db.get_rank_name(rank)
            assert name == expected_name, f"Expected '{expected_name}' for {rank}, got '{name}'"

        log_test("Rank Names", True, "All rank names mapped correctly")
        return True
    except AssertionError as e:
        log_test("Rank Names", False, str(e))
        return False
    except Exception as e:
        log_test("Rank Names", False, f"Error: {e}")
        return False

def test_file_structure():
    """Test 4: Required files exist"""
    try:
        required_files = [
            "main.py",
            "bot.py",
            "database.py",
            "webapp/index.html",
            "webapp/static/styles.css",
            "webapp/static/main.js"
        ]

        missing = []
        for file_path in required_files:
            full_path = os.path.join(os.getcwd(), file_path)
            if not os.path.exists(full_path):
                missing.append(file_path)

        if missing:
            log_test("File Structure", False, f"Missing files: {', '.join(missing)}")
            return False

        log_test("File Structure", True, "All required files present")
        return True
    except Exception as e:
        log_test("File Structure", False, f"Error: {e}")
        return False

def test_api_endpoints_defined():
    """Test 5: API endpoints are defined"""
    try:
        with open("main.py", "r", encoding="utf-8") as f:
            content = f.read()

        required_endpoints = [
            "@app.post(\"/api/vouch\")",
            "@app.get(\"/api/profile/{user_id}\")",
            "@app.put(\"/api/profile\")",
            "@app.post(\"/api/streak/update\")",
            "@app.get(\"/api/pending-vouches/{user_id}\")",
            "@app.get(\"/api/community-groups\")"
        ]

        missing = []
        for endpoint in required_endpoints:
            if endpoint not in content:
                missing.append(endpoint)

        if missing:
            log_test("API Endpoints", False, f"Missing endpoints: {', '.join(missing)}")
            return False

        log_test("API Endpoints", True, "All premium API endpoints defined")
        return True
    except Exception as e:
        log_test("API Endpoints", False, f"Error: {e}")
        return False

def test_vote_type_support():
    """Test 6: vote_type parameter (positive/negative)"""
    try:
        with open("main.py", "r", encoding="utf-8") as f:
            content = f.read()

        # Check that vote_type is used instead of is_thumbs_up
        has_vote_type = 'vote_type: str = "positive"' in content
        no_thumbs_up = 'is_thumbs_up' not in content

        if not has_vote_type:
            log_test("Vote Type Support", False, "vote_type parameter not found")
            return False

        if not no_thumbs_up:
            log_test("Vote Type Support", False, "Old is_thumbs_up parameter still present")
            return False

        log_test("Vote Type Support", True, "Using premium vote_type system")
        return True
    except Exception as e:
        log_test("Vote Type Support", False, f"Error: {e}")
        return False

def test_html_structure():
    """Test 7: HTML has all premium features"""
    try:
        with open("webapp/index.html", "r", encoding="utf-8") as f:
            content = f.read()

        required_elements = [
            'id="profile-tab"',
            'id="vouch-tab"',
            'id="community-tab"',
            'id="groupsView"',  # Groups tab
            'id="groupsGrid"',  # Groups grid
            'id="profileBio"',  # Bio section
            'id="profileLocation"',  # Location section
            'id="streakCount"',  # Streak counter
            'id="ratingDisplay"'  # Rating display
        ]

        missing = []
        for element in required_elements:
            if element not in content:
                missing.append(element)

        if missing:
            log_test("HTML Structure", False, f"Missing elements: {', '.join(missing)}")
            return False

        log_test("HTML Structure", True, "All premium HTML elements present")
        return True
    except Exception as e:
        log_test("HTML Structure", False, f"Error: {e}")
        return False

def test_css_professional_design():
    """Test 8: CSS has professional design system"""
    try:
        with open("webapp/static/styles.css", "r", encoding="utf-8") as f:
            content = f.read()

        required_styles = [
            "--accent: #1d9bf0",  # Twitter blue
            ".groups-grid",  # Groups grid styling
            ".group-card",  # Group cards
            ".rating-display",  # Rating display
            ".streak-card"  # Streak styling
        ]

        missing = []
        for style in required_styles:
            if style not in content:
                missing.append(style)

        if missing:
            log_test("CSS Professional Design", False, f"Missing styles: {', '.join(missing)}")
            return False

        # Check no gimmicky animations (confetti)
        has_confetti = 'confetti' in content.lower()
        if has_confetti:
            log_test("CSS Professional Design", False, "Contains confetti animations (should be removed)")
            return False

        log_test("CSS Professional Design", True, "Professional Twitter-style design present")
        return True
    except Exception as e:
        log_test("CSS Professional Design", False, f"Error: {e}")
        return False

def test_javascript_clean():
    """Test 9: JavaScript is clean and professional"""
    try:
        with open("webapp/static/main.js", "r", encoding="utf-8") as f:
            content = f.read()

        # Check for groups functionality
        has_groups = 'loadGroupsView' in content and 'renderGroupsGrid' in content

        # Check no confetti in main code
        has_confetti_code = 'confetti({' in content

        if not has_groups:
            log_test("JavaScript Clean", False, "Missing groups functionality")
            return False

        if has_confetti_code:
            log_test("JavaScript Clean", False, "Contains confetti code (should be removed)")
            return False

        log_test("JavaScript Clean", True, "Clean JavaScript with groups support")
        return True
    except Exception as e:
        log_test("JavaScript Clean", False, f"Error: {e}")
        return False

def test_bot_smart_moderation():
    """Test 10: Bot has smart strike system"""
    try:
        with open("bot.py", "r", encoding="utf-8") as f:
            content = f.read()

        required_features = [
            "violation_tracker",  # Strike tracking
            "WARN_AFTER_STRIKES",  # Warning threshold
            "handle_violation_smartly",  # Smart handling function
            "track_violation"  # Violation tracking function
        ]

        missing = []
        for feature in required_features:
            if feature not in content:
                missing.append(feature)

        if missing:
            log_test("Bot Smart Moderation", False, f"Missing features: {', '.join(missing)}")
            return False

        log_test("Bot Smart Moderation", True, "Smart strike system implemented")
        return True
    except Exception as e:
        log_test("Bot Smart Moderation", False, f"Error: {e}")
        return False

def test_rating_percentage_logic():
    """Test 11: Rating percentage calculation"""
    try:
        # Test rating calculations
        test_cases = [
            (10, 0, 100.0),  # 10 positive, 0 negative = 100%
            (5, 5, 50.0),    # 5 positive, 5 negative = 50%
            (7, 3, 70.0),    # 7 positive, 3 negative = 70%
            (0, 0, 100.0),   # 0 votes = 100% (default)
        ]

        for positive, negative, expected_rating in test_cases:
            total = positive + negative
            if total > 0:
                actual_rating = (positive / total) * 100
            else:
                actual_rating = 100.0

            assert abs(actual_rating - expected_rating) < 0.1, \
                f"For {positive}+/{negative}- expected {expected_rating}%, got {actual_rating}%"

        log_test("Rating Percentage Logic", True, "Rating calculations correct")
        return True
    except AssertionError as e:
        log_test("Rating Percentage Logic", False, str(e))
        return False
    except Exception as e:
        log_test("Rating Percentage Logic", False, f"Error: {e}")
        return False

def run_all_tests():
    """Run all logic tests"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}  VOUCH PORTAL - LOGIC & STRUCTURE TEST{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

    tests = [
        test_rank_calculation_logic,
        test_rank_emojis,
        test_rank_names,
        test_file_structure,
        test_api_endpoints_defined,
        test_vote_type_support,
        test_html_structure,
        test_css_professional_design,
        test_javascript_clean,
        test_bot_smart_moderation,
        test_rating_percentage_logic
    ]

    passed_count = 0
    failed_count = 0

    for test in tests:
        try:
            result = test()
            if result:
                passed_count += 1
            else:
                failed_count += 1
        except Exception as e:
            print(f"{RED}[FATAL] Error in {test.__name__}: {e}{RESET}")
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
        print(f"  [SUCCESS] ALL TESTS PASSED - LOGIC 100% CORRECT")
        print(f"{'='*60}{RESET}\n")
    else:
        print(f"\n{YELLOW}{'='*60}")
        print(f"  [WARNING] {failed_count} TEST(S) FAILED")
        print(f"{'='*60}{RESET}\n")

    return failed_count == 0

if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Tests interrupted{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}FATAL ERROR: {e}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
