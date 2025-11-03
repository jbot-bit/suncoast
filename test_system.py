#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive System Test Suite
Tests all components of the Vouch Portal system
"""

import sys
import os
import importlib.util

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def test_section(title):
    """Print a test section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

def test_import(module_name, description=""):
    """Test if a module can be imported"""
    try:
        module = __import__(module_name)
        print(f"✅ {module_name:30s} {'- ' + description if description else ''}")
        return True, module
    except Exception as e:
        print(f"❌ {module_name:30s} - ERROR: {str(e)[:50]}")
        return False, None

def test_dependency(package_name):
    """Test if a package is installed"""
    spec = importlib.util.find_spec(package_name)
    if spec is not None:
        print(f"✅ {package_name:30s}")
        return True
    else:
        print(f"❌ {package_name:30s} - NOT INSTALLED")
        return False

def main():
    print("\n" + "="*70)
    print("  VOUCH PORTAL v2.0 - COMPREHENSIVE SYSTEM TEST")
    print("="*70)
    
    all_passed = True
    
    # Test 1: Core Dependencies
    test_section("1. TESTING CORE DEPENDENCIES")
    dependencies = [
        ('fastapi', 'FastAPI'),
        ('uvicorn', 'Uvicorn'),
        ('telegram', 'python-telegram-bot'),
        ('asyncpg', 'AsyncPG'),
        ('pydantic', 'Pydantic'),
        ('dotenv', 'python-dotenv'),
        ('jwt', 'PyJWT'),
        ('httpx', 'HTTPX'),
    ]
    
    for module, name in dependencies:
        if not test_dependency(module):
            all_passed = False
    
    # Test 2: Moderation Engine Dependencies
    test_section("2. TESTING MODERATION ENGINE DEPENDENCIES")
    mod_dependencies = [
        ('ahocorasick', 'pyahocorasick'),
        ('confusable_homoglyphs', 'confusable-homoglyphs'),
        ('ftfy', 'ftfy'),
        ('rapidfuzz', 'rapidfuzz'),
        ('jellyfish', 'jellyfish'),
        ('yaml', 'pyyaml'),
    ]
    
    for module, package in mod_dependencies:
        if not test_dependency(module):
            all_passed = False
    
    # Test 3: Core Modules
    test_section("3. TESTING CORE MODULES")
    modules = [
        ('vouch_parser', 'Vouch Detection Engine v2.0'),
        ('database', 'Database Layer'),
        ('bot', 'Telegram Bot Handlers'),
        ('main', 'FastAPI Application'),
    ]
    
    loaded_modules = {}
    for module, desc in modules:
        success, mod = test_import(module, desc)
        if success:
            loaded_modules[module] = mod
        else:
            all_passed = False
    
    # Test 4: Vouch Parser Functionality
    if 'vouch_parser' in loaded_modules:
        test_section("4. TESTING VOUCH PARSER FUNCTIONALITY")
        try:
            from vouch_parser import parse_vouches_from_message, get_metrics, reset_metrics
            
            # Reset metrics for clean test
            reset_metrics()
            
            # Test cases
            test_cases = [
                ("vouch @alice", 1, "Standard vouch"),
                ("👍 @bob", 1, "Emoji vouch"),
                ("I voch for @charlie", 1, "Typo detection"),
                ("@dave is solid and legit", 1, "Implicit sentiment"),
                ("hey @eve what's up", 0, "False positive prevention"),
            ]
            
            parser_passed = 0
            parser_total = len(test_cases)
            
            for text, expected_count, description in test_cases:
                result = parse_vouches_from_message(text)
                actual_count = len(result)
                
                if actual_count == expected_count:
                    print(f"✅ {description:30s} - Detected {actual_count} vouch(s)")
                    parser_passed += 1
                else:
                    print(f"❌ {description:30s} - Expected {expected_count}, got {actual_count}")
                    all_passed = False
            
            print(f"\nParser Tests: {parser_passed}/{parser_total} passed ({parser_passed/parser_total*100:.0f}%)")
            
            # Show metrics
            metrics = get_metrics()
            print(f"Total parses: {metrics.get('total_parses', 0)}")
            
        except Exception as e:
            print(f"❌ Vouch parser tests failed: {e}")
            all_passed = False
    
    # Test 5: Bot Configuration
    if 'bot' in loaded_modules:
        test_section("5. TESTING BOT CONFIGURATION")
        try:
            bot_mod = loaded_modules['bot']
            
            configs = [
                ('BOT_TOKEN', 'configured' if bot_mod.BOT_TOKEN else 'missing'),
                ('BOT_USERNAME', bot_mod.BOT_USERNAME),
                ('ADMIN_ID', str(bot_mod.ADMIN_ID)),
                ('ENABLE_CONTENT_MODERATION', str(bot_mod.ENABLE_CONTENT_MODERATION)),
            ]
            
            for key, value in configs:
                print(f"✅ {key:30s} = {value}")
                
        except Exception as e:
            print(f"❌ Bot configuration test failed: {e}")
            all_passed = False
    
    # Test 6: Database Interface
    if 'database' in loaded_modules:
        test_section("6. TESTING DATABASE INTERFACE")
        try:
            from database import db
            
            methods = [m for m in dir(db) if not m.startswith('_') and callable(getattr(db, m))]
            print(f"✅ Database methods available: {len(methods)}")
            
            # Check for key methods
            key_methods = [
                'get_or_create_user',
                'create_vouch',
                'get_rank_emoji',
                'get_rank_name',
                'calculate_trust_metrics',
            ]
            
            for method in key_methods:
                if hasattr(db, method):
                    print(f"✅ {method:30s}")
                else:
                    print(f"❌ {method:30s} - MISSING")
                    all_passed = False
                    
        except Exception as e:
            print(f"❌ Database interface test failed: {e}")
            all_passed = False
    
    # Test 7: FastAPI Application
    if 'main' in loaded_modules:
        test_section("7. TESTING FASTAPI APPLICATION")
        try:
            main_mod = loaded_modules['main']
            app = main_mod.app
            
            routes = [r.path for r in app.routes if hasattr(r, 'path')]
            print(f"✅ API routes registered: {len(routes)}")
            
            # Check for key routes
            key_routes = [
                '/api/profile/{user_id}',
                '/api/vouch',
                '/api/users',
                '/api/activity',
                '/health',
            ]
            
            routes_found = 0
            for route in key_routes:
                if route in routes:
                    print(f"✅ {route:30s}")
                    routes_found += 1
                else:
                    print(f"⚠️  {route:30s} - not found (may be normal)")
            
        except Exception as e:
            print(f"❌ FastAPI application test failed: {e}")
            all_passed = False
    
    # Final Summary
    test_section("SUMMARY")
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("\nSystem Status: READY FOR DEPLOYMENT")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED")
        print("\nPlease review the errors above and fix any issues.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    print("\n" + "="*70 + "\n")
    sys.exit(exit_code)
