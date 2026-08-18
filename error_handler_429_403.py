"""
Error Handler for 429 (Too Many Requests) and 403 (Forbidden) errors
Plus debugging utilities for data parsing issues

This module provides utilities to:
1. Check for HTTP 429/403 errors in API responses
2. Handle rate limiting gracefully
3. Debug data parsing failures
"""

import json
import logging
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class HTTPErrorHandler:
    """Handle HTTP errors with proper logging and recovery strategies"""

    HTTP_429 = 429  # Too Many Requests
    HTTP_403 = 403  # Forbidden

    @staticmethod
    def check_response_error(response_data: Dict[str, Any] | str) -> Tuple[bool, Optional[str]]:
        """
        Check if response contains error information

        Args:
            response_data: Response from API (dict or string)

        Returns:
            Tuple of (has_error, error_description)
        """
        if isinstance(response_data, str):
            response_data = {"raw": response_data}

        # Check common error indicators
        if isinstance(response_data, dict):
            # Check for error status
            if response_data.get("status") in [429, 403]:
                return True, f"HTTP {response_data.get('status')} error"

            # Check for error message
            if "error" in response_data:
                return True, str(response_data.get("error"))

            # Check for message field
            if "message" in response_data:
                msg = response_data.get("message", "")
                if "too many" in str(msg).lower() or "rate limit" in str(msg).lower():
                    return True, f"Rate limit error: {msg}"
                if "forbidden" in str(msg).lower() or "unauthorized" in str(msg).lower():
                    return True, f"Authorization error: {msg}"

        return False, None

    @staticmethod
    def is_429_error(status_code: int, response: Dict[str, Any] | str) -> bool:
        """Check if response is 429 Too Many Requests"""
        if status_code == 429:
            return True

        if isinstance(response, dict):
            if response.get("status") == 429:
                return True
            msg = str(response.get("message", "")).lower()
            if "rate limit" in msg or "too many" in msg:
                return True

        return False

    @staticmethod
    def is_403_error(status_code: int, response: Dict[str, Any] | str) -> bool:
        """Check if response is 403 Forbidden"""
        if status_code == 403:
            return True

        if isinstance(response, dict):
            if response.get("status") == 403:
                return True
            msg = str(response.get("message", "")).lower()
            if "forbidden" in msg or "unauthorized" in msg or "access denied" in msg:
                return True

        return False


class RateLimitHandler:
    """Handle rate limiting with exponential backoff"""

    def __init__(self, max_retries: int = 3, initial_delay: float = 1.0):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.retry_count = 0
        self.last_error_time = None

    def should_retry(self) -> bool:
        """Check if we should retry based on retry count"""
        return self.retry_count < self.max_retries

    def get_backoff_delay(self) -> float:
        """Calculate exponential backoff delay"""
        delay = self.initial_delay * (2 ** self.retry_count)
        return min(delay, 300)  # Cap at 5 minutes

    def record_error(self):
        """Record error and increment retry count"""
        self.retry_count += 1
        self.last_error_time = datetime.now()

    def reset(self):
        """Reset retry counter"""
        self.retry_count = 0
        self.last_error_time = None

    def wait_before_retry(self):
        """Wait before retrying"""
        delay = self.get_backoff_delay()
        logger.warning(f"Rate limited. Waiting {delay}s before retry {self.retry_count}/{self.max_retries}")
        time.sleep(delay)


class DataParsingDebugger:
    """Debug and analyze data parsing issues"""

    @staticmethod
    def analyze_response_format(response: Any, endpoint: str = "unknown") -> Dict[str, Any]:
        """
        Analyze response format and content

        Args:
            response: API response data
            endpoint: API endpoint name for logging

        Returns:
            Dictionary with analysis results
        """
        analysis = {
            "endpoint": endpoint,
            "timestamp": datetime.now().isoformat(),
            "response_type": type(response).__name__,
            "is_empty": response is None or (isinstance(response, (list, dict)) and len(response) == 0),
            "has_data": False,
            "data_structure": None,
            "potential_issues": [],
        }

        # Analyze different response types
        if response is None:
            analysis["potential_issues"].append("Response is None")

        elif isinstance(response, dict):
            analysis["data_structure"] = "dict"
            analysis["has_data"] = len(response) > 0

            # Check for common price data fields
            price_fields = ["open", "high", "low", "close", "price", "data", "bars"]
            found_fields = [k for k in response.keys() if any(pf in k.lower() for pf in price_fields)]

            if not found_fields:
                analysis["potential_issues"].append("No price/data fields found in dict")
                analysis["dict_keys"] = list(response.keys())[:10]  # First 10 keys

        elif isinstance(response, list):
            analysis["data_structure"] = "list"
            analysis["has_data"] = len(response) > 0
            if response:
                analysis["list_length"] = len(response)
                analysis["first_element_type"] = type(response[0]).__name__

        elif isinstance(response, str):
            analysis["data_structure"] = "string"
            analysis["string_length"] = len(response)

            # Check if it looks like base64 or encoded data
            if len(response) > 50 and response.startswith(("iVBO", "SGVs", "Salted")):
                analysis["potential_issues"].append("Response appears to be encoded/binary data")

            # Try to parse as JSON
            try:
                parsed = json.loads(response)
                analysis["potential_issues"].append("String is valid JSON - consider parsing")
                analysis["data_structure"] = "json_string"
            except json.JSONDecodeError:
                analysis["potential_issues"].append("String is not valid JSON")

        elif isinstance(response, bytes):
            analysis["data_structure"] = "bytes"
            analysis["bytes_length"] = len(response)

            # Check for common binary headers
            if response.startswith(b"Salted"):
                analysis["potential_issues"].append("Data appears to be OpenSSL encrypted")
            elif response.startswith(b"\x1f\x8b"):
                analysis["potential_issues"].append("Data appears to be GZIP compressed")
            elif response.startswith(b"\x78\x9c"):
                analysis["potential_issues"].append("Data appears to be ZLIB compressed")
            else:
                analysis["potential_issues"].append("Data is binary - needs decoding/decompression")

        return analysis

    @staticmethod
    def log_debug_info(symbol: str, chain: str, response: Any, endpoint: str = "dexscreener"):
        """
        Log comprehensive debug information for failed price fetch

        Args:
            symbol: Token symbol
            chain: Blockchain name
            response: API response
            endpoint: API endpoint
        """
        analysis = DataParsingDebugger.analyze_response_format(response, endpoint)

        logger.debug(f"\n{'='*60}")
        logger.debug(f"DEBUG INFO: {symbol} / {chain}")
        logger.debug(f"{'='*60}")
        logger.debug(f"Endpoint: {endpoint}")
        logger.debug(f"Response Type: {analysis['response_type']}")
        logger.debug(f"Data Structure: {analysis['data_structure']}")
        logger.debug(f"Has Data: {analysis['has_data']}")
        logger.debug(f"Is Empty: {analysis['is_empty']}")

        if analysis.get("dict_keys"):
            logger.debug(f"Available Keys: {analysis['dict_keys']}")

        if analysis.get("string_length"):
            logger.debug(f"String Length: {analysis['string_length']}")

        if analysis.get("bytes_length"):
            logger.debug(f"Bytes Length: {analysis['bytes_length']}")

        if analysis["potential_issues"]:
            logger.debug("Potential Issues:")
            for issue in analysis["potential_issues"]:
                logger.debug(f"  - {issue}")

        logger.debug(f"{'='*60}\n")


class APIResponseValidator:
    """Validate API responses for expected data"""

    @staticmethod
    def validate_price_data(response: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate if response contains valid price data

        Args:
            response: Response from price API

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check if it's an error response
        has_error, error_msg = HTTPErrorHandler.check_response_error(response)
        if has_error:
            return False, error_msg

        # Check for required price fields
        required_price_fields = ["open", "high", "low", "close", "price"]

        if isinstance(response, dict):
            found_fields = [f for f in required_price_fields if f in response]
            if not found_fields:
                return False, f"Missing price data fields. Expected one of: {required_price_fields}"

            # Check if any price field has a valid value
            for field in found_fields:
                value = response.get(field)
                if value is not None and (isinstance(value, (int, float)) or (isinstance(value, str) and value)):
                    return True, None

            return False, "Price fields exist but contain no valid data"

        return False, f"Invalid response type: {type(response).__name__}"


# Example usage wrapper for existing scripts
def wrap_api_call_with_error_handling(api_func, *args, **kwargs):
    """
    Wrapper to add error handling to API calls

    Usage:
        response = wrap_api_call_with_error_handling(
            requests.get,
            url,
            timeout=10
        )
    """
    handler = RateLimitHandler()

    while handler.should_retry():
        try:
            return api_func(*args, **kwargs)
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                logger.error(f"429 Rate Limit Error: {e}")
                handler.record_error()
                if handler.should_retry():
                    handler.wait_before_retry()
                else:
                    raise
            elif "403" in str(e) or "forbidden" in str(e).lower():
                logger.error(f"403 Forbidden Error: {e}")
                raise
            else:
                raise
