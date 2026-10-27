"""
Constants for the Steam Achievement Tracker plugin
Centralized configuration for performance, caching, and API settings
"""

# Processing limits - simplified
LIMITS = {
    "MAX_GAMES": 50,             # Max games limit
}

# Processing delays (seconds) - simplified
DELAYS = {
    "CLEANUP": 0.1,             # Session cleanup delay
    "RATE_LIMIT": 1.0,          # Rate limit delay (reduced from 1.5s)
}

# Concurrency limits - aggressive optimization
CONCURRENCY = {
    "MAX_GAMES": 20,             # Memory usage is only 80MB, go higher
    "MAX_API_REQUESTS": 6,       # More aggressive API rate limit
}

# Network and API settings
NETWORK = {
    "CONNECTION_TIMEOUT": 15,
    "CONNECT_TIMEOUT": 5,
    "READ_TIMEOUT": 10,
}

# Common time constants (replacing magic numbers)
TIME_CONSTANTS = {
    "ONE_MINUTE": 60,
    "TWO_MINUTES": 120,
    "FIVE_MINUTES": 300,
    "ONE_HOUR": 3600,
    "ONE_DAY": 86400,
    "ONE_WEEK": 604800,
}

# Cache TTL settings (seconds) - consistent naming with _TTL suffix
CACHE_TTL = {
    "ACHIEVEMENT_TTL": TIME_CONSTANTS["FIVE_MINUTES"],      # 5 minutes - in-memory achievement data
    "SCHEMA_TTL": TIME_CONSTANTS["ONE_HOUR"],               # 1 hour - schema data changes rarely  
    "APP_DETAILS_TTL": TIME_CONSTANTS["ONE_DAY"],           # 24 hours - app details from store
    "PROGRESS_FILE_TTL": TIME_CONSTANTS["ONE_DAY"],         # 24 hours - overall progress cache file
    "CACHE_FILE_MAX_AGE": TIME_CONSTANTS["ONE_WEEK"],       # 7 days - max age before cleanup
}

# Timeouts and fallbacks
TIMEOUTS = {
    "PROGRESS_CALCULATION": TIME_CONSTANTS["FIVE_MINUTES"],       # 5 minutes for large libraries
}

# Memory management and cache sizes - consistent naming with MAX_ prefix
MEMORY_LIMITS = {
    "MAX_ACHIEVEMENT_CACHE_SIZE": 100,   # Max items in achievement cache
    "MAX_SCHEMA_CACHE_SIZE": 50,         # Max items in schema cache  
}

# Default values and tolerances
DEFAULTS = {
    "REFRESH_INTERVAL": 60,           # Default refresh interval in seconds
    "AUTO_REFRESH": False,            # Default auto-refresh state
    "GAME_COUNT_TOLERANCE": 5,        # Game count processing tolerance
    "RESPONSE_TEXT_LIMIT": 500,       # Response text truncation limit
    "CACHE_CLEANUP_FREQUENCY": 10,    # Cache cleanup check frequency
}