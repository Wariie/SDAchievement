import aiohttp
import asyncio
import json
import time
import decky
from pathlib import Path
from typing import Optional, Dict, Any, List
import ssl
import sys
import os

# Add lib path
plugin_dir = os.path.dirname(os.path.realpath(__file__))
lib_path = os.path.join(plugin_dir, "externals", "cachetools", "src")
sys.path.insert(0, lib_path)

# Use cachetools for better LRU+TTL caching (available via submodule)
from cachetools import TTLCache

logger = decky.logger

# Import constants
from constants import CACHE_TTL, NETWORK, CONCURRENCY, MEMORY_LIMITS, DEFAULTS

def create_error_response(message: str) -> Dict[str, str]:
    """Create standardized error response"""
    return {"error": message}

class SteamAPI:
    BASE_URL = "https://api.steampowered.com"
    STORE_URL = "https://store.steampowered.com/api"

    def __init__(self, api_key: Optional[str] = None, steam_id: Optional[str] = None, cache_dir: Optional[Path] = None):
        self.api_key = api_key
        self.steam_id = steam_id
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache_dir = cache_dir or Path("/tmp/steam_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self._request_semaphore = asyncio.Semaphore(CONCURRENCY["MAX_API_REQUESTS"])  # Rate limiting from constants
        
        # Initialize bounded TTL caches with consistent naming
        self.achievement_cache = TTLCache(
            maxsize=MEMORY_LIMITS["MAX_ACHIEVEMENT_CACHE_SIZE"],
            ttl=CACHE_TTL["ACHIEVEMENT_TTL"]
        )
        self.schema_cache = TTLCache(
            maxsize=MEMORY_LIMITS["MAX_SCHEMA_CACHE_SIZE"], 
            ttl=CACHE_TTL["SCHEMA_TTL"]
        )
        
        # Verified SSL context; prefer certifi's CA bundle (shipped with Decky) in case the system store is missing
        try:
            import certifi
            self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            self.ssl_context = ssl.create_default_context()

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(ssl=self.ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def _ensure_session(self):
        if not self.session:
            connector = aiohttp.TCPConnector(
                ssl=self.ssl_context,
                limit=5,
                limit_per_host=3,
                enable_cleanup_closed=True,
                force_close=True,
                ttl_dns_cache=60,
                use_dns_cache=True
            )
            timeout = aiohttp.ClientTimeout(
                total=NETWORK["CONNECTION_TIMEOUT"],
                connect=NETWORK["CONNECT_TIMEOUT"],
                sock_read=NETWORK["READ_TIMEOUT"]
            )
            self.session = aiohttp.ClientSession(
                connector=connector, 
                timeout=timeout
            )

    async def _get(self, url: str, params: Dict[str, Any]) -> Dict[str, Any] | None:
        await self._ensure_session()
        
        async with self._request_semaphore:
            response_data = None
            response_text = None
            try:
                async with self.session.get(url, params=params) as resp:
                    if resp.status == 200:
                        response_data = await resp.json()
                        return response_data
                    elif resp.status == 429:  # Rate limited
                        logger.warning(f"Rate limited (status 429) for {url}")
                        return None
                    elif resp.status == 403:  # Invalid API key or private profile
                        logger.warning(f"Access denied (status 403) for {url} - check API key and profile privacy")
                        return None
                    elif resp.status == 400:  # Bad request
                        response_text = await resp.text()
                        logger.error(f"Steam API bad request (400) for {url}")
                        safe_params = {k: ("***" if k == "key" else v) for k, v in params.items()}
                        logger.error(f"Request params: {safe_params}")
                        logger.error(f"Response: {response_text[:DEFAULTS['RESPONSE_TEXT_LIMIT']]}")
                        return None
                    else:
                        logger.error(f"Steam API returned status {resp.status} for {url}")
                        return None
            except Exception as e:
                logger.error(f"Steam API request failed: {url} -> {e}")
                return None

    async def close(self):
        """Properly close the session and clean up resources"""
        if self.session and not self.session.closed:
            await self.session.close()
            # Give time for connection cleanup
        self.session = None
        
        # Clear in-memory cache to prevent memory leaks
        self.achievement_cache.clear()
        self.schema_cache.clear()
        
        try:
            self._cleanup_old_cache_files()
        except Exception as e:
            logger.warning(f"Cache cleanup error: {e}")
    
    def _cleanup_old_cache_files(self):
        """Clean up cache files older than 7 days"""
        try:
            current_time = time.time()
            cutoff_time = current_time - CACHE_TTL["CACHE_FILE_MAX_AGE"]
            
            if self.cache_dir.exists():
                for cache_file in self.cache_dir.glob("game_*.json"):
                    if cache_file.stat().st_mtime < cutoff_time:
                        cache_file.unlink()
                        logger.debug(f"Cleaned up old cache file: {cache_file}")
        except Exception as e:
            logger.warning(f"Failed to cleanup cache files: {e}")
    
    def _cleanup_expired_memory_cache(self):
        """Clean up expired entries from caches (TTL automatically handled)"""
        try:
            # TTLCache/SimpleTTLCache handle expiration automatically
            # Just log current cache sizes for monitoring
            logger.debug(f"Cache cleanup: Achievement cache size: {len(self.achievement_cache)}, Schema cache size: {len(self.schema_cache)}")
        except Exception as e:
            logger.warning(f"Failed to cleanup memory cache: {e}")
    
    def clear_memory_cache(self, app_id: int = None):
        """Clear in-memory caches for specific app or all apps"""
        try:
            if app_id:
                # Clear specific app from achievement cache
                cache_key = f"{app_id}_{self.steam_id}"
                if cache_key in self.achievement_cache:
                    del self.achievement_cache[cache_key]
                    logger.info(f"Cleared in-memory achievement cache for app {app_id}")
                
                # Also clear schema cache for the app
                schema_key = f"schema_{app_id}"
                if schema_key in self.schema_cache:
                    del self.schema_cache[schema_key]
                    logger.info(f"Cleared in-memory schema cache for app {app_id}")
            else:
                # Clear all caches
                self.achievement_cache.clear()
                self.schema_cache.clear()
                logger.info("Cleared all in-memory caches")
        except Exception as e:
            logger.warning(f"Failed to clear in-memory cache: {e}")

    # ---------------------------
    # User & Games
    # ---------------------------


    async def get_owned_games(self, steam_id: Optional[str] = None) -> Dict:
        steam_id = steam_id or self.steam_id
        if not self.api_key or not steam_id:
            return create_error_response("Missing API key or Steam ID")
        
        result = await self._get(
            f"{self.BASE_URL}/IPlayerService/GetOwnedGames/v1/",
            {"key": self.api_key, "steamid": steam_id, "include_appinfo": "1", "include_played_free_games": "1", "skip_unvetted_apps": "false"},
        )
        
        return result if result else {"error": "Failed to fetch owned games"}

    async def get_recently_played_games(self, steam_id: Optional[str] = None) -> Dict:
        steam_id = steam_id or self.steam_id
        if not self.api_key or not steam_id:
            return create_error_response("Missing API key or Steam ID")
        
        result = await self._get(
            f"{self.BASE_URL}/IPlayerService/GetRecentlyPlayedGames/v1/",
            {"key": self.api_key, "steamid": steam_id},
        )
        
        return result if result else {"error": "Failed to fetch recently played games"}

    async def get_recent_achievements(self, limit: int = 10) -> List[Dict]:
        """Get recently unlocked achievements across all games"""
        try:
            if not self.api_key or not self.steam_id:
                logger.warning("Missing API key or steam ID for recent achievements")
                return []

            # Get recently played games - Steam API can be slow to update (5-15 min delay)
            response = await self.get_recently_played_games()
            if not response:
                logger.warning("No recently played games response from Steam API")
                return []

            games = response.get("response", {}).get("games", [])
            if not games:
                logger.info("No recently played games found")
                return []
                
            logger.info(f"Checking {len(games)} recently played games for new achievements")
            recent_achievements = []

            tasks = [
                self.get_player_achievements(game["appid"]) 
                for game in games
            ]
            
            achievements_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, (game, achievements_data) in enumerate(zip(games, achievements_results)):
                if isinstance(achievements_data, Exception):
                    logger.warning(f"Failed to get achievements for {game['appid']}: {achievements_data}")
                    continue
                
                # Skip apps without achievement support
                if achievements_data and achievements_data.get("error"):
                    if "has no achievement support" in achievements_data.get("error", ""):
                        logger.debug(f"Skipping app {game['appid']} - no achievement support")
                        continue
                    else:
                        logger.warning(f"Error getting achievements for {game['appid']}: {achievements_data.get('error')}")
                        continue
                    
                if achievements_data and "achievements" in achievements_data:
                    for ach in achievements_data["achievements"]:
                        if ach["unlocked"] and ach["unlock_time"]:
                            # Ensure global_percent is a proper number
                            global_percent = ach.get("global_percent")
                            if global_percent is not None:
                                try:
                                    global_percent = float(global_percent)
                                except (ValueError, TypeError):
                                    global_percent = 0.0
                            else:
                                global_percent = 0.0
                                
                            recent_achievements.append({
                                "game_name": game.get("name", f"App {game['appid']}"),
                                "game_id": game["appid"],
                                "achievement_name": ach["display_name"],
                                "achievement_desc": ach["description"],
                                "unlock_time": ach["unlock_time"],
                                "icon": ach["icon"],
                                "global_percent": global_percent
                            })

            # Sort by unlock time and return most recent
            recent_achievements.sort(key=lambda x: x["unlock_time"], reverse=True)
            
            if recent_achievements:
                latest_unlock = recent_achievements[0]["unlock_time"]
                from datetime import datetime
                latest_date = datetime.fromtimestamp(latest_unlock).strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"Found {len(recent_achievements)} recent achievements, latest: {latest_date}")
            else:
                logger.info("No recent achievements found - Steam API may have delay (5-15 minutes normal)")
            
            return recent_achievements[:limit]

        except Exception as e:
            logger.error(f"Failed to get recent achievements: {e}")
            return []

    # ---------------------------
    # Achievements & Stats
    # ---------------------------

    async def get_schema_for_game(self, app_id: int) -> Dict:
        if not self.api_key:
            return {"error": "Missing API key"}
        
        # Check schema cache first (TTL handled automatically by LRU cache)
        cache_key = f"schema_{app_id}"
        cached_data = self.schema_cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Using cached schema data for app {app_id}")
            return cached_data
        
        result = await self._get(
            f"{self.BASE_URL}/ISteamUserStats/GetSchemaForGame/v2/",
            {"key": self.api_key, "appid": app_id, "l": "english"},
        )
        
        if result and not result.get("error"):
            # Cache successful results (TTL handled automatically)
            self.schema_cache[cache_key] = result
            logger.debug(f"Cached schema data for app {app_id}")
        
        return result if result else {"error": f"Failed to fetch schema for app {app_id}"}

    async def get_player_achievements_raw(self, app_id: int, steam_id: Optional[str] = None) -> Dict:
        steam_id = steam_id or self.steam_id
        if not self.api_key or not steam_id:
            return create_error_response("Missing API key or Steam ID")
        
        # Validate app_id
        if not app_id or app_id <= 0:
            return {"error": f"Invalid app_id: {app_id}"}
        
        logger.debug(f"Requesting achievements for app_id={app_id}, steam_id={steam_id}")
        result = await self._get(
            f"{self.BASE_URL}/ISteamUserStats/GetPlayerAchievements/v1/",
            {"key": self.api_key, "steamid": steam_id, "appid": app_id, "l": "english"},
        )
        
        if result:
            # Check for Steam API error responses
            player_stats = result.get("playerstats", {})
            if player_stats.get("success") is False:
                error_msg = player_stats.get("error", "Unknown error")
                if "no registration for app details" in error_msg.lower():
                    logger.debug(f"App {app_id} has no achievement registration")
                    return {"error": f"App {app_id} has no achievement support"}
                else:
                    logger.warning(f"Steam API error for app {app_id}: {error_msg}")
                    return {"error": f"Steam API error: {error_msg}"}
        
        return result if result else {"error": f"Failed to fetch achievements for app {app_id}"}

    async def get_player_achievements(self, app_id: int, steam_id: Optional[str] = None) -> Dict:
        """Get formatted achievement data for a player"""
        steam_id = steam_id or self.steam_id
        if not self.api_key or not steam_id:
            return create_error_response("Missing API key or Steam ID")

        # Clean up expired cache entries periodically (every 10th call)
        if len(self.achievement_cache) % DEFAULTS["CACHE_CLEANUP_FREQUENCY"] == 0:
            self._cleanup_expired_memory_cache()
        
        # Check cache first (TTL handled automatically by LRU cache)
        cache_key = f"{app_id}_{steam_id}"
        cached_data = self.achievement_cache.get(cache_key)
        if cached_data is not None:
            logger.debug(f"Using cached achievement data for app {app_id}")
            return cached_data

        try:
            # Get player achievements first (most important)
            player = await self.get_player_achievements_raw(app_id, steam_id)
            if player and player.get("error"):
                return player
            
            # Get schema (needed for achievement details)
            schema = await self.get_schema_for_game(app_id)
            if schema and schema.get("error"):
                return {"error": f"Failed to get schema: {schema.get('error')}"}
            
            # Parse schema achievements
            schema_achs = {}
            game_data = schema.get("game", {})
            if game_data:
                available_stats = game_data.get("availableGameStats", {})
                if available_stats and "achievements" in available_stats:
                    schema_achs = {a["name"]: a for a in available_stats["achievements"]}

            # Parse player achievements
            player_achs = {}
            playerstats = player.get("playerstats", {})
            if playerstats and "achievements" in playerstats:
                player_achs = {a["apiname"]: a for a in playerstats["achievements"]}

            # Get global achievement percentages
            global_stats = await self._get(
                f"{self.BASE_URL}/ISteamUserStats/GetGlobalAchievementPercentagesForApp/v2/",
                {"gameid": app_id},
            )
            
            # Parse global achievements
            global_achs = {}
            if global_stats and not global_stats.get("error"):
                global_achievement_data = global_stats.get("achievementpercentages", {})
                if global_achievement_data and "achievements" in global_achievement_data:
                    global_achs = {a["name"]: a["percent"] for a in global_achievement_data["achievements"]}
                    logger.debug(f"Found {len(global_achs)} global achievement percentages for app {app_id}")
                else:
                    logger.debug(f"No global achievement percentages found for app {app_id}")
            else:
                logger.debug(f"Failed to get global achievement percentages for app {app_id}: {global_stats.get('error', 'Unknown error') if global_stats else 'No response'}")

            # Validate that we have achievements data
            if not schema_achs:
                logger.warning(f"No achievements found in schema for app {app_id}")
                return {
                    "app_id": app_id,
                    "total": 0,
                    "unlocked": 0,
                    "percentage": 0.0,
                    "achievements": [],
                    "error": "No achievements found for this game"
                }

            achievements: List[Dict[str, Any]] = []
            unlocked_count = 0

            # Combine all data
            for api_name, sch in schema_achs.items():
                pl = player_achs.get(api_name, {})
                unlocked = pl.get("achieved", 0) == 1
                if unlocked:
                    unlocked_count += 1

                # Get global percentage
                global_percent = global_achs.get(api_name)
                if global_percent is not None:
                    try:
                        global_percent = float(global_percent)
                    except (ValueError, TypeError):
                        logger.warning(f"Achievement {api_name}: invalid global_percent value: {global_percent}")
                        global_percent = None
                else:
                    global_percent = None

                achievements.append({
                    "api_name": api_name,
                    "display_name": sch.get("displayName", api_name),
                    "description": sch.get("description", ""),
                    "icon": sch.get("icon", ""),
                    "icon_gray": sch.get("icongray", ""),
                    "hidden": sch.get("hidden", 0) == 1,
                    "unlocked": unlocked,
                    "unlock_time": pl.get("unlocktime"),
                    "global_percent": global_percent
                })

            total = len(achievements)
            percentage = round((unlocked_count / total) * 100, 2) if total > 0 else 0.0

            result = {
                "app_id": app_id,
                "total": int(total),  # Ensure these are integers
                "unlocked": int(unlocked_count),
                "percentage": float(percentage),  # Ensure this is a float
                "achievements": achievements
            }
            
            # Cache the result (TTL handled automatically)
            self.achievement_cache[cache_key] = result
            
            logger.info(f"Achievement data for app {app_id}: {unlocked_count}/{total} ({percentage}%)")
            return result

        except Exception as e:
            logger.error(f"Failed to get player achievements for app {app_id}: {e}")
            return create_error_response(f"Failed to fetch achievement data: {str(e)}")



    # ---------------------------
    # Store API (no key required)
    # ---------------------------

    async def get_app_details(self, app_id: int) -> Dict:
        """Get game details from Steam Store API"""
        try:
            # Check cache first
            cache_file = self.cache_dir / f"game_{app_id}.json"
            if cache_file.exists():
                cache_age = time.time() - cache_file.stat().st_mtime
                if cache_age < CACHE_TTL["APP_DETAILS_TTL"]:
                    # Use async file reading to avoid blocking
                    loop = asyncio.get_event_loop()
                    content = await loop.run_in_executor(None, cache_file.read_text)
                    return json.loads(content)

            await self._ensure_session()
            url = f"{self.STORE_URL}/appdetails"
            params = {"appids": app_id}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if str(app_id) in data and data[str(app_id)]["success"]:
                        game_data = data[str(app_id)]["data"]
                        info = {
                            "app_id": app_id,
                            "name": game_data.get("name", ""),
                            "has_achievements": game_data.get("achievements", {}).get("total", 0) > 0,
                            "total_achievements": game_data.get("achievements", {}).get("total", 0),
                            "header_image": game_data.get("header_image", ""),
                            "categories": [cat.get("description", "") for cat in game_data.get("categories", [])]
                        }
                        
                        # Cache the result
                        try:
                            cache_file.write_text(json.dumps(info))
                        except Exception as e:
                            logger.warning(f"Failed to cache app details: {e}")
                        
                        return info
                        
        except Exception as e:
            logger.error(f"Failed to get app details for {app_id}: {e}")
            return {"error": f"Failed to fetch app details for {app_id}: {str(e)}"}
        
        # Fallback data if API call fails but no exception occurred
        return {"app_id": app_id, "name": f"App {app_id}", "has_achievements": False, "total_achievements": 0}

    def clear_all_caches(self):
        self.achievement_cache.clear()
        self.schema_cache.clear()