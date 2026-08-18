#!/usr/bin/env python3
"""
Diagnostic script to identify API response issues
Tests the dexscreener API and analyzes response format
"""

import sys
import json
import requests
from typing import Optional
from error_handler_429_403 import (
    HTTPErrorHandler,
    DataParsingDebugger,
    APIResponseValidator,
)


def test_dexscreener_api(chain: str, address: str) -> dict:
    """Test a single dexscreener API call"""
    url = f"https://api.dexscreener.com/latest/dex/tokens/{chain}:{address}"

    print(f"\n{'='*60}")
    print(f"Testing API: {url}")
    print(f"{'='*60}")

    try:
        response = requests.get(url, timeout=10)
        print(f"HTTP Status: {response.status_code}")

        # Check for 429/403
        if HTTPErrorHandler.is_429_error(response.status_code, {}):
            print("❌ ERROR 429: Too Many Requests (Rate Limited)")
            return {"error": "429", "status_code": response.status_code}

        if HTTPErrorHandler.is_403_error(response.status_code, {}):
            print("❌ ERROR 403: Forbidden (Access Denied)")
            return {"error": "403", "status_code": response.status_code}

        print(f"✅ HTTP {response.status_code}: OK")

        # Try to parse as JSON
        try:
            data = response.json()
            print("✅ Response is valid JSON")

            # Validate price data
            is_valid, error_msg = APIResponseValidator.validate_price_data(data)
            if is_valid:
                print("✅ Contains valid price data")
                return {"status": "valid", "data": data}
            else:
                print(f"❌ Invalid price data: {error_msg}")
                # Analyze format
                analysis = DataParsingDebugger.analyze_response_format(data, "dexscreener")
                print(f"\nAnalysis:")
                print(f"  - Response Type: {analysis['response_type']}")
                print(f"  - Data Structure: {analysis['data_structure']}")
                print(f"  - Has Data: {analysis['has_data']}")
                if analysis.get("dict_keys"):
                    print(f"  - Available Keys: {analysis['dict_keys']}")
                if analysis["potential_issues"]:
                    print(f"  - Issues: {', '.join(analysis['potential_issues'])}")
                return {"status": "invalid_format", "data": data, "analysis": analysis}

        except json.JSONDecodeError:
            print("❌ Response is not valid JSON")
            print(f"Response Content-Type: {response.headers.get('content-type')}")
            print(f"Response Length: {len(response.text)} chars")

            # Analyze raw response
            analysis = DataParsingDebugger.analyze_response_format(
                response.text, "dexscreener"
            )
            print(f"\nAnalysis:")
            print(f"  - Issues: {', '.join(analysis['potential_issues'])}")
            print(f"  - First 100 chars: {response.text[:100]}")

            return {"status": "parse_error", "error": str(analysis["potential_issues"])}

    except requests.exceptions.Timeout:
        print("❌ ERROR: Request Timeout")
        return {"error": "timeout"}
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Connection Error")
        return {"error": "connection"}
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        return {"error": str(e)}


def test_multiple_tokens():
    """Test several tokens to identify patterns"""
    test_cases = [
        ("base", "0xE1c135D5F02941c9Bb61edc23B6C193D39100F23"),  # BODA
        ("solana", ""),  # Will fail - need valid address
        ("ethereum", ""),  # Will fail - need valid address
    ]

    results = {}
    for chain, address in test_cases:
        if address:  # Skip invalid addresses
            print(f"\nTesting {chain}...")
            result = test_dexscreener_api(chain, address)
            results[f"{chain}:{address[:8]}..."] = result

    return results


def main():
    """Main diagnostic function"""
    print("\n" + "=" * 60)
    print("API RESPONSE DIAGNOSTIC TOOL")
    print("=" * 60)

    # Test specific token that was failing
    print("\nTest 1: BODA token (known failure case)")
    test_dexscreener_api("base", "0xE1c135D5F02941c9Bb61edc23B6C193D39100F23")

    print("\n" + "=" * 60)
    print("RECOMMENDATIONS:")
    print("=" * 60)

    print("""
1. For 429 (Rate Limit) errors:
   - Add exponential backoff retry logic
   - Implement rate limiting queue
   - Add delay between requests
   - Use RateLimitHandler from error_handler_429_403.py

2. For 403 (Forbidden) errors:
   - Check if API requires authentication
   - Verify API key/credentials are valid
   - Check if IP is whitelisted
   - Review API documentation for access requirements

3. For "No price data found" errors:
   - Check if response format is JSON or binary/encoded
   - Handle different response structures
   - Validate data before parsing
   - Log debug info using DataParsingDebugger
   - Consider token might be unlisted/delisted

4. For parsing failures:
   - Handle encoded data (base64, gzip, zlib)
   - Add response format validation
   - Implement fallback parsing methods
   - Log full response for debugging

Next steps:
   1. Run this diagnostic: python diagnose_api_issues.py
   2. Check output for specific error type
   3. Implement appropriate fix from error_handler_429_403.py
   4. Add error handling to cs.py
    """)


if __name__ == "__main__":
    main()
