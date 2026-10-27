"""
Achievement service for fetching and processing achievement data
"""
import time
import asyncio
import decky
from typing import Dict, List


from constants import TIMEOUTS, CONCURRENCY, DELAYS, DEFAULTS, TIME_CONSTANTS
from models.validators import validate_progress_data


async def _as_completed_with_progress(coros, progress_interval):
    """Yield results as tasks complete"""
    tasks = [asyncio.create_task(coro) for coro in coros]
    pending = set(tasks)
    
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            try:
                result = await task
                yield result
            except Exception as e:
                yield e


class AchievementService:
    """Handles all achievement-related operations"""
    
    def __init__(self, api, cache_service, api_key: str, user_id: str):
        self.api = api
        self.cache_service = cache_service
        self.api_key = api_key
        self.user_id = user_id
        self._init_progress_tracking()
    
    async def close(self):
        """Clean up resources when service is no longer needed"""
        try:
            decky.logger.info("Closing AchievementService...")
            
            # Close API if it has a close method
            if self.api and hasattr(self.api, 'close'):
                await self.api.close()
            
            # Clear references
            self.api = None
            self.cache_service = None
            self.api_key = None
            self.user_id = None
            
            decky.logger.info("AchievementService cleanup completed")
            
        except Exception as e:
            decky.logger.warning(f"Error during AchievementService cleanup: {e}")
    
    def _init_progress_tracking(self):
        """Initialize progress tracking attributes"""
        self._progress_lock = asyncio.Lock()  # Prevent concurrent expensive operations
        self._is_processing = False  # Track if progress calculation is running
        self._processing_start_time = 0  # Track when processing started
    
    async def get_achievements(self, app_id: int) -> Dict:
        """Get achievements for a specific game"""
        try:
            if not self.api:
                return {"error": "Steam API not initialized"}

            if not self.api_key or not self.user_id:
                return {"error": "Steam API key or user ID not configured"}

            result = await self.api.get_player_achievements(app_id)
            
            
            return result

        except Exception as e:
            decky.logger.error(f"Failed to get achievements: {e}")
            return {"error": f"Failed to get achievements: {str(e)}"}
    
    async def get_recent_achievements(self, limit: int = 10) -> List[Dict]:
        """Get recently unlocked achievements across all games"""
        try:
            if not self.api or not self.api_key or not self.user_id:
                decky.logger.warning("Missing API key or user ID for recent achievements")
                return []
            
            decky.logger.info(f"Getting recent achievements (limit: {limit})")
            return await self.api.get_recent_achievements(limit)
                        
        except Exception as e:
            decky.logger.error(f"Failed to get recent achievements: {e}")
            return []
    
    async def get_user_games(self) -> List[Dict]:
        """Get all user's owned games with community stats (likely has achievements)"""
        try:
            if not self.api:
                decky.logger.error("Steam API not initialized for get_user_games")
                return []

            if not self.api_key or not self.user_id:
                decky.logger.error("Steam API key or user ID not configured for get_user_games")
                return []

            decky.logger.info("Getting user's owned games")
            
            # Get owned games
            owned_games = await self.api.get_owned_games()
            if not owned_games or owned_games.get("error"):
                decky.logger.error(f"Failed to get owned games: {owned_games.get('error', 'Unknown error') if owned_games else 'No response'}")
                return []
            
            games = owned_games.get("response", {}).get("games", [])
            decky.logger.info(f"Found {len(games)} total owned games")
            
            # Filter games that likely have achievements (has_community_visible_stats)
            # This is much faster than checking schema for each game
            games_with_achievements = []
            for game in games:
                if game.get("has_community_visible_stats", False):
                    games_with_achievements.append({
                        "app_id": game["appid"],
                        "name": game["name"],
                        "has_achievements": True,
                        "achievements": 0,  # We don't know the exact count, but that's okay
                        "playtime_forever": game.get("playtime_forever", 0),
                        "is_running": False
                    })
            
            decky.logger.info(f"Found {len(games_with_achievements)} games with community stats")
            
            # Sort by playtime for better UX (most played first)
            games_with_achievements.sort(key=lambda x: x.get("playtime_forever", 0), reverse=True)
            return games_with_achievements
            
        except Exception as e:
            decky.logger.error(f"Failed to get user games: {e}")
            return []

    async def get_achievement_progress(self, force_refresh: bool = False) -> Dict:
        """Get overall achievement progress across all games"""
        try:
            if not self.api or not self.api_key or not self.user_id:
                return {"error": "Not configured"}
            
            # Block if already processing (unless force_refresh)
            if not force_refresh and self._is_processing:
                # Safety timeout: If processing for more than configured time, reset the flag
                if time.time() - self._processing_start_time > TIMEOUTS["PROGRESS_CALCULATION"]:
                    decky.logger.warning("Progress calculation timeout - resetting processing flag")
                    self._is_processing = False
                else:
                    decky.logger.info("Progress calculation blocked: Another calculation already in progress")
                    cached_data = await self.cache_service.get_overall_progress()
                    if cached_data:
                        return validate_progress_data(cached_data)
                    else:
                        return {"error": "Progress calculation in progress, try again later"}
            
            # Use lock to prevent concurrent expensive operations
            if self._progress_lock.locked() and not force_refresh:
                decky.logger.info("Progress calculation blocked: Lock already acquired")
                cached_data = await self.cache_service.get_overall_progress()
                if cached_data:
                    return validate_progress_data(cached_data)
                else:
                    return {"error": "Progress calculation in progress, try again later"}
            
            async with self._progress_lock:
                self._is_processing = True
                self._processing_start_time = time.time()
                
                # Try to get from cache first (after acquiring lock)
                if not force_refresh:
                    cached_data = await self.cache_service.get_overall_progress()
                    # A result with fetch failures is only trusted for an hour, then recalculated
                    if cached_data and cached_data.get("failed_games"):
                        if time.time() - cached_data.get("last_updated", 0) > TIME_CONSTANTS["ONE_HOUR"]:
                            decky.logger.info(f"Cached progress has {cached_data['failed_games']} failed games and is over an hour old - recalculating")
                            cached_data = None
                    if cached_data:
                        # Validate game count hasn't changed significantly
                        owned_games = await self.api.get_owned_games()
                        if owned_games and not owned_games.get("error"):
                            current_count = len(owned_games.get("response", {}).get("games", []))
                            cached_count = cached_data.get("total_games", 0)
                            
                            if abs(current_count - cached_count) <= DEFAULTS["GAME_COUNT_TOLERANCE"]:
                                decky.logger.info("Using cached overall progress")
                                self._is_processing = False
                                return validate_progress_data(cached_data)
                
                decky.logger.info("Calculating fresh overall achievement progress")
                
                # Get owned games
                owned_games = await self.api.get_owned_games()
                if not owned_games or owned_games.get("error"):
                    error_msg = owned_games.get("error", "Unknown error") if owned_games else "No response from API"
                    self._is_processing = False
                    return {"error": f"Failed to get owned games: {error_msg}"}
                
                games = owned_games.get("response", {}).get("games", [])
                
                # Pre-filter games without community stats to save API calls
                games_with_stats = [game for game in games if game.get("has_community_visible_stats")]
                skipped_games = len(games) - len(games_with_stats)
                
                decky.logger.info(f"Pre-filtered {skipped_games} games without community stats, processing {len(games_with_stats)} games")
                
                total_achievements = 0
                unlocked_achievements = 0
                perfect_games = []
                games_with_achievements = 0
                processed_games = 0
            
                semaphore = asyncio.Semaphore(CONCURRENCY["MAX_GAMES"])  # Limit concurrent games
                progress_interval = max(1, len(games_with_stats) // 4)
                
                async def process_game(game, index):
                    """Process a single game"""
                    async with semaphore:
                        if not game.get("has_community_visible_stats"):
                            return None
                            
                        try:
                            achievements = await self.get_achievements(game["appid"])
                            if isinstance(achievements, dict) and "Failed to fetch" in achievements.get("error", ""):
                                # Transient failure (network / rate limit) - retried after the first pass
                                return {"failed": True, "game": game}
                            if achievements and isinstance(achievements, dict) and not achievements.get("error"):
                                if "total" in achievements and achievements["total"] == 0:
                                    return None
                                
                                if "total" in achievements and achievements["total"] > 0:
                                    result = {
                                        "achievements": achievements,
                                        "game": game,
                                        "is_perfect": achievements["unlocked"] == achievements["total"],
                                        "index": index  # For progress tracking
                                    }
                                    
                                    if result["is_perfect"]:
                                        try:
                                            app_details = await self.api.get_app_details(game["appid"])
                                            result["header_image"] = app_details.get("header_image", "") if app_details else ""
                                        except Exception:
                                            result["header_image"] = ""
                                    
                                    return result
                                    
                        except Exception as e:
                            decky.logger.warning(f"Failed to get achievements for {game.get('name', game['appid'])}: {e}")
                            return {"failed": True, "game": game}
                        return None
                
                # Process all games concurrently with progress logging
                decky.logger.info(f"Processing {len(games_with_stats)} games concurrently (max {CONCURRENCY['MAX_GAMES']} at once)")
                
                start_time = time.time()
                tasks = [process_game(game, i) for i, game in enumerate(games_with_stats)]
                
                def accumulate(result):
                    nonlocal games_with_achievements, total_achievements, unlocked_achievements, processed_games
                    games_with_achievements += 1
                    total_achievements += result["achievements"]["total"]
                    unlocked_achievements += result["achievements"]["unlocked"]
                    processed_games += 1

                    if result["is_perfect"]:
                        perfect_games.append({
                            "name": result["game"].get("name", f"App {result['game']['appid']}"),
                            "app_id": result["game"]["appid"],
                            "has_achievements": True,
                            "total_achievements": result["achievements"]["total"],
                            "unlocked_achievements": result["achievements"]["unlocked"],
                            "achievement_percentage": 100.0,
                            "playtime_forever": result["game"].get("playtime_forever", 0),
                            "header_image": result.get("header_image", "")
                        })

                failed_games = []
                completed_count = 0
                async for result in _as_completed_with_progress(tasks, progress_interval):
                    if isinstance(result, dict) and result.get("failed"):
                        failed_games.append(result["game"])
                    elif result and not isinstance(result, Exception):
                        accumulate(result)

                    completed_count += 1
                    
                    if completed_count % progress_interval == 0 or completed_count == len(tasks):
                        elapsed = time.time() - start_time
                        progress_pct = (completed_count / len(tasks)) * 100
                        
                        try:
                            import psutil
                            memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
                            decky.logger.info(f"Progress: {completed_count}/{len(tasks)} ({progress_pct:.1f}%) - {processed_games} games processed in {elapsed:.1f}s, Memory: {memory_mb:.1f}MB")
                        except:
                            decky.logger.info(f"Progress: {completed_count}/{len(tasks)} ({progress_pct:.1f}%) - {processed_games} games processed in {elapsed:.1f}s")

                # Retry transient failures one at a time so rate-limited games aren't silently dropped
                still_failed = 0
                if failed_games:
                    decky.logger.info(f"Retrying {len(failed_games)} games that failed to fetch")
                    consecutive_failures = 0
                    for game in failed_games:
                        # Stop hammering the API if it keeps failing (still rate limited / offline)
                        if consecutive_failures >= 3:
                            still_failed += 1
                            continue
                        await asyncio.sleep(DELAYS["RATE_LIMIT"])
                        result = await process_game(game, -1)
                        if isinstance(result, dict) and result.get("failed"):
                            still_failed += 1
                            consecutive_failures += 1
                        else:
                            consecutive_failures = 0
                            if result:
                                accumulate(result)
                    if still_failed:
                        decky.logger.warning(f"{still_failed} games could not be fetched - totals may be incomplete")

                average_completion = round((unlocked_achievements / total_achievements * 100) if total_achievements > 0 else 0, 1)
                
                result = {
                    "total_games": len(games),
                    "games_with_achievements": games_with_achievements,
                    "total_achievements": total_achievements,
                    "unlocked_achievements": unlocked_achievements,
                    "average_completion": average_completion,
                    "perfect_games": perfect_games,
                    "perfect_games_count": len(perfect_games),
                    "last_updated": int(time.time()),
                    "processed_games": processed_games,
                    "failed_games": still_failed
                }

                # Cache the result (results with failures expire after an hour, see cache check above)
                await self.cache_service.save_overall_progress(result)
                
                # Validate and return
                result = validate_progress_data(result)
                total_time = time.time() - start_time
                decky.logger.info(f"Progress calculation complete: {result['unlocked_achievements']}/{result['total_achievements']} ({result['average_completion']}%) in {total_time:.1f}s")
                
                if self.api:
                    try:
                        self.api.clear_all_caches()
                    except Exception as e:
                        decky.logger.warning(f"Failed to clear API caches: {e}")
                
                
                self._is_processing = False
                
                return result
                            
        except Exception as e:
            self._is_processing = False
            decky.logger.error(f"Failed to get achievement progress: {e}")
            return {"error": f"Failed to calculate progress: {str(e)}"}