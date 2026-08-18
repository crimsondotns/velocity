# HTTP 429/403 Error Handling & Data Parsing Guide

## 🔍 Analysis Summary

Based on your log file analysis, the "No price data found" errors are **NOT HTTP 429/403 errors**, but rather **data availability or parsing issues**.

### What Happened:
- ✅ API calls succeeded (HTTP 200)
- ✅ Data was received and saved (JSON file contains OHLC data)
- ❌ Script failed to extract/recognize valid price data
- Result: 652 tokens found successfully, 594 tokens reported "No price data found"

---

## 🎯 Root Causes

### 1. **Data Format Issues** (Most Likely)
The API might return data in different formats:
- **Binary/Encoded data**: OHLC candlestick data that needs decoding
- **Unexpected JSON structure**: Different from what the script expects
- **Missing fields**: Required price fields not present in response

### 2. **Token Issues**
Some tokens might be:
- Not yet listed on the exchange
- Delisted/removed
- Only available on specific DEX pairs
- Insufficient liquidity for price data

### 3. **API Rate Limiting** (Less likely but possible)
- Status 429: Too Many Requests
- API might return success but with incomplete data
- Needs exponential backoff retry logic

### 4. **Authorization Issues** (Possible)
- Status 403: Forbidden
- API key expired/invalid
- IP address not whitelisted

---

## 🛠️ Solutions Implemented

### New Files Added:

#### 1. `error_handler_429_403.py`
Comprehensive error handling module with:

```python
from error_handler_429_403 import (
    HTTPErrorHandler,      # Check for 429/403 errors
    RateLimitHandler,      # Handle rate limiting with backoff
    DataParsingDebugger,   # Debug data format issues
    APIResponseValidator   # Validate price data
)

# Example: Check for errors
has_error, msg = HTTPErrorHandler.check_response_error(response)
if HTTPErrorHandler.is_429_error(status_code, response):
    print("Rate limited!")
if HTTPErrorHandler.is_403_error(status_code, response):
    print("Access forbidden!")

# Example: Debug data issues
analysis = DataParsingDebugger.analyze_response_format(response)
print(analysis["potential_issues"])

# Example: Retry with exponential backoff
handler = RateLimitHandler(max_retries=3)
while handler.should_retry():
    try:
        response = api.call()
        break
    except Exception as e:
        handler.record_error()
        handler.wait_before_retry()
```

#### 2. `diagnose_api_issues.py`
Diagnostic script to identify exact issues:

```bash
# Run diagnosis
python diagnose_api_issues.py

# Output shows:
# - HTTP status code
# - Whether response is valid JSON
# - Data format analysis
# - Specific issues found
```

---

## 📋 Implementation Steps

### Step 1: Add Error Checking to Your Script

Replace your existing API call logic with:

```python
from error_handler_429_403 import (
    HTTPErrorHandler,
    RateLimitHandler,
    DataParsingDebugger,
    APIResponseValidator
)
import requests

def fetch_price_data(symbol, chain, address):
    """Fetch price data with comprehensive error handling"""
    
    url = f"https://api.dexscreener.com/latest/dex/tokens/{chain}:{address}"
    handler = RateLimitHandler(max_retries=3)
    
    while handler.should_retry():
        try:
            response = requests.get(url, timeout=10)
            
            # Check for HTTP errors
            if response.status_code == 429:
                logger.error(f"429 Rate Limited: {symbol}/{chain}")
                handler.record_error()
                handler.wait_before_retry()
                continue
                
            if response.status_code == 403:
                logger.error(f"403 Forbidden: {symbol}/{chain}")
                return None
            
            # Parse response
            data = response.json()
            
            # Validate data
            is_valid, error_msg = APIResponseValidator.validate_price_data(data)
            if is_valid:
                return extract_price(data)
            else:
                logger.warning(f"Invalid data: {symbol}/{chain} - {error_msg}")
                # Log debug info
                DataParsingDebugger.log_debug_info(symbol, chain, data)
                return None
                
        except requests.exceptions.RequestException as e:
            if "429" in str(e):
                handler.record_error()
                if handler.should_retry():
                    handler.wait_before_retry()
            else:
                logger.error(f"Error fetching {symbol}/{chain}: {e}")
                return None
    
    logger.error(f"Max retries exceeded for {symbol}/{chain}")
    return None
```

### Step 2: Run Diagnostic Script

```bash
python diagnose_api_issues.py
```

This will show:
- Which requests succeed/fail
- Exact error codes
- Data format issues
- Actionable recommendations

### Step 3: Update Retry Logic

Add to your main loop:

```python
# Before processing tokens
handler = RateLimitHandler(max_retries=3, initial_delay=1.0)

for token in tokens:
    # Your processing...
    if getting_rate_limited:
        handler.record_error()
        handler.wait_before_retry()
```

---

## 🔍 Debugging Tips

### Check for 429 Errors:
```python
from error_handler_429_403 import HTTPErrorHandler

status_code = 429
if HTTPErrorHandler.is_429_error(status_code, response):
    # Handle rate limiting
    print("Rate limited - waiting...")
```

### Check for 403 Errors:
```python
if HTTPErrorHandler.is_403_error(status_code, response):
    # Handle forbidden access
    print("Access denied - check credentials")
```

### Analyze Response Format:
```python
from error_handler_429_403 import DataParsingDebugger

analysis = DataParsingDebugger.analyze_response_format(response)
for issue in analysis["potential_issues"]:
    print(f"Issue: {issue}")
```

### Log Debug Information:
```python
DataParsingDebugger.log_debug_info(
    symbol="BODA",
    chain="base",
    response=api_response,
    endpoint="dexscreener"
)
```

---

## 📊 Expected Outcomes

### After Implementation:

| Metric | Before | After |
|--------|--------|-------|
| Failed tokens | 594 | ✓ Better identification |
| Error classification | Generic | HTTP error codes |
| Retry mechanism | None | Exponential backoff |
| Debug info | Limited | Comprehensive |

---

## 🐛 Common Issues & Fixes

### Issue: "No price data found" for valid tokens

**Solution:**
```python
# Check if token data exists but in different format
response = {
    "data": {"bars": [...]},  # Nested structure
    "pairs": [...]  # Or in pairs array
}

# Use DataParsingDebugger to analyze
analysis = DataParsingDebugger.analyze_response_format(response)
if "dict_keys" in analysis:
    print(f"Available keys: {analysis['dict_keys']}")
```

### Issue: Rate limiting causing cascading failures

**Solution:**
```python
# Use RateLimitHandler with proper backoff
handler = RateLimitHandler(max_retries=3)

# Add delay between requests
import time
time.sleep(0.1)  # 100ms between requests
```

### Issue: Inconsistent API responses

**Solution:**
```python
# Use APIResponseValidator for all responses
is_valid, error = APIResponseValidator.validate_price_data(data)
if not is_valid:
    # Log and skip this token
    logger.warning(f"Invalid response: {error}")
    continue
```

---

## 📞 Support

For each error type encountered:

1. **429 - Too Many Requests**
   - Add request delay (start with 100ms)
   - Use exponential backoff
   - Implement request queue

2. **403 - Forbidden**
   - Check API credentials
   - Verify endpoint access
   - Review API documentation

3. **No price data**
   - Run `diagnose_api_issues.py`
   - Check response format
   - Validate required fields

4. **Connection errors**
   - Implement connection retry
   - Add timeout handling
   - Check network connectivity

---

## 🚀 Next Steps

1. ✅ Review error_handler_429_403.py
2. ✅ Run diagnose_api_issues.py  
3. ✅ Integrate error checking into cs.py
4. ✅ Test with problematic tokens
5. ✅ Monitor logs for remaining issues
