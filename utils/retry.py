import time
import functools


def with_retry(max_attempts=3, base_delay=1):
    """
    Decorator that retries a function on failure with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts before giving up
        base_delay: Initial delay in seconds (doubles each retry)

    Usage:
        @with_retry(max_attempts=3, base_delay=1)
        def my_api_call():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        print(f"All {max_attempts} attempts failed: {e}")
                        raise
                    wait = base_delay * (2 ** attempt)
                    print(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                    time.sleep(wait)
        return wrapper
    return decorator