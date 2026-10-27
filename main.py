"""
Main plugin class that orchestrates all services
"""
import decky
import traceback
import asyncio
import gc
import shutil
from pathlib import Path
from typing import Dict, List, Optional

# Import constants
from constants import LIMITS, DELAYS, CONCURRENCY, TIMEOUTS, DEFAULTS

from services.settings import SettingsService
from services.game_detector import GameDetectorService
from services.achievement import AchievementService
from services.cache import FileCacheService
from services.steam_scanner import SteamScannerService
from services.steamgriddb import steamgriddb_service
from steam_api import SteamAPI


class Plugin:
    """
    Main plugin class for Steam Achievement Tracker
    Orchestrates all services and handles plugin lifecycle
    """

    def __init__(self):
        # Initialize paths
        self.plugin_dir = Path(decky.DECKY_PLUGIN_DIR)
        self.settings_dir = Path(decky.DECKY_PLUGIN_SETTINGS_DIR)
        self.cache_dir = Path(decky.DECKY_PLUGIN_RUNTIME_DIR) / "cache"
        
        # Initialize services
        self.settings_service = SettingsService(self.settings_dir)
        self.game_detector = GameDetectorService()
        self.cache_service = FileCacheService(self.cache_dir)
        self.steam_scanner = SteamScannerService()
        
        # These will be initialized after settings are loaded
        self.achievement_service = None
        self.api: Optional[SteamAPI] = None
        
        # State
        self.steam_api_key = None
        self.current_user_id = None
        self.test_app_id = None
    
    async def _main(self):
        """Initialize the plugin"""
        try:
            decky.logger.info("=== Steam Achievement Tracker Starting ===")
            
            # Ensure directories exist
            self.settings_dir.mkdir(parents=True, exist_ok=True)
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            # Load settings
            await self.settings_service.load()
            self.steam_api_key = self.settings_service.api_key
            self.current_user_id = self.settings_service.user_id
            self.test_app_id = self.settings_service.test_app_id

            decky.logger.info(f"Loaded settings - API Key set: {bool(self.steam_api_key)}, User ID: {self.current_user_id}, Test App: {self.test_app_id}")
            
            # Note: User detection moved to frontend - backend relies on manual configuration

            # Initialize API and achievement service
            if self.steam_api_key and self.current_user_id:
                self.api = SteamAPI(self.steam_api_key, self.current_user_id, self.cache_dir)
                self.achievement_service = AchievementService(
                    self.api,
                    self.cache_service,
                    self.steam_api_key,
                    self.current_user_id
                )
                decky.logger.info("API and achievement service initialized successfully")

            else:
                decky.logger.warning(f"Cannot initialize API - missing {'API key' if not self.steam_api_key else 'user ID'}")

            decky.logger.info(f"Plugin initialization complete - API ready: {bool(self.api)}")
        except Exception as e:
            decky.logger.error(f"Init failed: {e}")
            decky.logger.error(traceback.format_exc())
    
    async def _unload(self):
        """Cleanup when plugin is unloaded"""
        decky.logger.info("Steam Achievement Tracker unloading")
        
        # Clean up achievement service first
        if self.achievement_service:
            try:
                await self.achievement_service.close()
            except Exception as e:
                decky.logger.warning(f"Error during achievement service cleanup: {e}")
            finally:
                self.achievement_service = None
        
        # Then clean up API
        if self.api:
            try:
                await self.api.close()
            except Exception as e:
                decky.logger.warning(f"Error during API cleanup: {e}")
            finally:
                self.api = None
    
    async def _migration(self):
        """Handle plugin migrations"""
        decky.logger.info("Running migrations...")
        
        # Migrate old settings if they exist
        old_settings_path = self.plugin_dir / "settings.json"
        new_settings_path = self.settings_dir / "settings.json"
        
        if old_settings_path.exists() and not new_settings_path.exists():
            decky.logger.info(f"Migrating settings from {old_settings_path}")
            try:
                shutil.move(str(old_settings_path), str(new_settings_path))
                decky.logger.info("Settings migration completed")
            except Exception as e:
                decky.logger.error(f"Failed to migrate settings: {e}")
    
    # ==================== Settings Management ====================

    def _get_settings_dict(self) -> Dict:
        """Helper method to build settings dictionary"""
        refresh_interval = self.settings_service.settings.get('refresh_interval', DEFAULTS["REFRESH_INTERVAL"]) if self.settings_service.settings else DEFAULTS["REFRESH_INTERVAL"]
        auto_refresh = self.settings_service.settings.get('auto_refresh', DEFAULTS["AUTO_REFRESH"]) if self.settings_service.settings else DEFAULTS["AUTO_REFRESH"]
        
        return {
            "steam_api_key": self.settings_service.api_key or "",
            "steam_user_id": self.settings_service.user_id or "",
            "test_app_id": self.settings_service.test_app_id,
            "api_key_set": bool(self.settings_service.api_key),
            "user_id_set": bool(self.settings_service.user_id),
            "auto_refresh": auto_refresh,
            "refresh_interval": refresh_interval,
            "tracked_game": self.settings_service.get_tracked_game()
        }
    
    def _update_plugin_state(self):
        """Update plugin state from settings service"""
        self.steam_api_key = self.settings_service.api_key
        self.current_user_id = self.settings_service.user_id
        self.test_app_id = self.settings_service.test_app_id

    async def load_settings(self) -> Dict:
        """Load and return settings for UI (callable from frontend)"""
        try:
            await self.settings_service.load()
            self._update_plugin_state()
            return self._get_settings_dict()
        except Exception as e:
            decky.logger.error(f"Failed to load settings: {e}")
            return {}


    async def reload_settings(self) -> Dict:
        """Force reload settings from disk and return them"""
        try:
            decky.logger.info("Force reloading settings from disk")
            
            await self.settings_service.load()
            self._update_plugin_state()
            
            # Reinitialize API if needed
            if self.steam_api_key and self.current_user_id:
                await self._reinitialize_api()
            
            decky.logger.info(f"Settings reloaded - API Key: {bool(self.steam_api_key)}, User ID: {self.current_user_id}")
            return self._get_settings_dict()
                
        except Exception as e:
            decky.logger.error(f"Failed to reload settings: {e}")
            return {"error": str(e)}
        
    async def set_auto_refresh(self, enabled: bool) -> bool:
        """Set and save the auto-refresh enabled state"""
        try:
            decky.logger.info(f"Setting auto-refresh to {enabled}")
            
            # Get the current settings from the service's internal state
            current_settings = self.settings_service.settings.copy() if self.settings_service.settings else {}
            
            # Update auto_refresh
            current_settings['auto_refresh'] = enabled
            
            # Save settings using the service
            success = await self.settings_service.save(current_settings)
            
            if success:
                decky.logger.info(f"Auto-refresh setting saved: {enabled}")
            
            return success
        except Exception as e:
            decky.logger.error(f"Failed to set auto-refresh: {e}")
            return False
    
    async def set_steam_api_key(self, api_key: str) -> bool:
        """Set Steam API key"""
        try:
            success = await self.settings_service.set_api_key(api_key)
            if success:
                self.steam_api_key = api_key
                await self._reinitialize_api()
                decky.logger.info("API key set and services reinitialized")
            return success
        except Exception as e:
            decky.logger.error(f"Failed to set API key: {e}")
            return False

    async def set_steam_user_id(self, user_id: str) -> bool:
        """Set Steam user ID"""
        try:
            success = await self.settings_service.set_user_id(user_id)
            if success:
                self.current_user_id = user_id
                await self._reinitialize_api()
                decky.logger.info("Steam user ID set and services reinitialized")
            return success
        except Exception as e:
            decky.logger.error(f"Failed to set user ID: {e}")
            return False
    
    async def set_tracked_game(self, app_id: int, name: str) -> bool:
        """Set tracked game"""
        return await self.settings_service.set_tracked_game(app_id, name)

    async def clear_tracked_game(self) -> bool:
        """Clear tracked game"""
        try:
            decky.logger.info("Main: Clearing tracked game...")
            success = await self.settings_service.clear_tracked_game()
            
            if success:
                decky.logger.info("Main: Tracked game cleared successfully, reloading settings...")
                # Force reload settings to ensure our internal state is updated
                await self.settings_service.load()
                decky.logger.info("Main: Settings reloaded after clearing tracked game")
            else:
                decky.logger.error("Main: Failed to clear tracked game")
            
            return success
        except Exception as e:
            decky.logger.error(f"Main: Error in clear_tracked_game: {e}")
            return False

    async def set_refresh_interval(self, interval: int) -> bool:
        """Set and save the auto-refresh interval"""
        try:
            decky.logger.info(f"Setting refresh interval to {interval} seconds")
            
            # Get the current settings from the service's internal state
            current_settings = self.settings_service.settings.copy() if self.settings_service.settings else {}
            
            # Update refresh interval
            current_settings['refresh_interval'] = interval
            
            # Save settings using the service
            success = await self.settings_service.save(current_settings)
            
            if success:
                decky.logger.info(f"Refresh interval saved: {interval} seconds")
            else:
                decky.logger.error("Failed to save refresh interval")
            
            return success
        except Exception as e:
            decky.logger.error(f"Failed to set refresh interval: {e}")
            return False
    
    async def set_test_game(self, app_id: int) -> bool:
        """Set test game ID"""
        success = await self.settings_service.set_test_game(app_id)
        if success:
            self.test_app_id = app_id
        return success
    
    async def clear_test_game(self) -> bool:
        """Clear test game ID"""
        success = await self.settings_service.clear_test_game()
        if success:
            self.test_app_id = None
        return success
    
    # ==================== Game Detection ====================
    
    async def get_current_game(self) -> Optional[Dict]:
        """Get currently running game"""
        result = await self.game_detector.get_current_game(self.test_app_id, self.api)
        # Return None if there's an error to maintain compatibility with existing code
        return result if result and not result.get("error") else None
    
    async def get_installed_games(self) -> List[Dict]:
        """Get locally installed Steam games by scanning installation files"""
        return await self.steam_scanner.get_installed_games(self.current_user_id)
    
    async def get_user_games(self) -> List[Dict]:
        """Get user's full Steam library (requires Steam API key)"""
        if not self.achievement_service:
            decky.logger.warning("Achievement service not initialized for get_user_games")
            return []
        return await self.achievement_service.get_user_games()
    
    async def get_game_artwork(self, app_id: int) -> Dict:
        """Get game artwork paths (grid, hero, logo, icon) with SteamGridDB fallback"""
        try:
            # First try local Steam artwork
            artwork = self.steam_scanner.get_game_artwork(app_id)
            result = {"grid": None, "hero": None, "logo": None, "icon": None}
            
            # Convert Path objects to data URLs for frontend use
            if artwork and isinstance(artwork, dict):
                for key, path in artwork.items():
                    if path:
                        try:
                            # Convert file path to data URL
                            data_url = steamgriddb_service._file_path_to_data_url(str(path))
                            result[key] = data_url
                        except Exception as e:
                            decky.logger.warning(f"Failed to convert {path} to data URL: {e}")
                            result[key] = None
            
            # If no local artwork found, try SteamGridDB fallback
            if not any(result.values()):
                decky.logger.info(f"No local artwork found for app {app_id}, trying SteamGridDB fallback")
                try:
                    steamgriddb_artwork = steamgriddb_service.get_user_custom_artwork(app_id, as_data_urls=True)
                    # Merge SteamGridDB results
                    for key, url in steamgriddb_artwork.items():
                        if url and not result.get(key):
                            result[key] = url
                except Exception as sgdb_error:
                    decky.logger.warning(f"SteamGridDB fallback failed for app {app_id}: {sgdb_error}")
            
            return result
        except Exception as e:
            decky.logger.error(f"Failed to get game artwork for {app_id}: {e}")
            return {"grid": None, "hero": None, "logo": None, "icon": None}
    
    async def get_steamgriddb_artwork(self, app_id: int) -> Dict:
        """Get artwork directly from SteamGridDB (uses existing plugin settings if available)"""
        try:
            return steamgriddb_service.get_user_custom_artwork(app_id, as_data_urls=True)
        except Exception as e:
            decky.logger.error(f"Failed to get SteamGridDB artwork for {app_id}: {e}")
            return {"hero": None, "grid": None, "grid_small": None}
    
    # ==================== Achievement Functions ====================
    
    async def get_achievements(self, app_id: int = None) -> Dict:
        """Get achievements for a game"""
        if not self.achievement_service:
            return {"error": "Achievement service not initialized"}
        
        if not app_id:
            game = await self.get_current_game()
            if not game:
                return {"error": "No game running"}
            app_id = game["app_id"]
        
        return await self.achievement_service.get_achievements(app_id)
    
    async def get_recent_achievements(self, limit: int = 10) -> List[Dict]:
        """Get recent achievements"""
        if not self.achievement_service:
            return []
        return await self.achievement_service.get_recent_achievements(limit)
    
    async def get_achievement_progress(self, force_refresh: bool = False) -> Dict:
        """Get overall achievement progress with Python-side caching and processing"""
        decky.logger.info(f"get_achievement_progress called - force_refresh: {force_refresh}")
        decky.logger.info(f"Achievement service initialized: {bool(self.achievement_service)}")
        decky.logger.info(f"Steam API key set: {bool(self.steam_api_key)}")
        decky.logger.info(f"User ID set: {bool(self.current_user_id)}")
        
        if not self.achievement_service:
            decky.logger.warning("Achievement service not initialized - missing API key or user ID")
            return {
                "error": "Achievement service not initialized - API key or user ID missing",
                "total_games": 0,
                "games_with_achievements": 0,
                "total_achievements": 0,
                "unlocked_achievements": 0,
                "average_completion": 0,
                "perfect_games": [],
                "perfect_games_count": 0
            }
        
        decky.logger.info("Calling achievement_service.get_achievement_progress...")
        # The achievement service clears API caches itself after a fresh calculation
        return await self.achievement_service.get_achievement_progress(force_refresh)
    
    async def _process_single_game(self, game: Dict) -> Optional[Dict]:
        """Process a single game for recently played - simplified version"""
        try:
            # Create base game object
            base_game = {
                "app_id": game["appid"],
                "name": game["name"], 
                "playtime_forever": game.get("playtime_forever", 0),
                "playtime_2weeks": game.get("playtime_2weeks", 0),
                "img_icon_url": game.get("img_icon_url", ""),
                "img_logo_url": game.get("img_logo_url", ""),
                "header_image": "",
                "has_achievements": False,
                "total_achievements": 0,
                "unlocked_achievements": 0,
                "achievement_percentage": 0.0
            }
            
            # Fetch app details
            try:
                app_details = await self.api.get_app_details(game["appid"])
                if app_details and not app_details.get("error"):
                    base_game["header_image"] = app_details.get("header_image", "")
            except Exception:
                pass  # Continue without header image
                
            # Fetch player achievement data (includes both schema and progress)
            try:
                achievement_data = await self.achievement_service.get_achievements(game["appid"])
                if achievement_data and not achievement_data.get("error"):
                    base_game["has_achievements"] = achievement_data.get("total", 0) > 0
                    base_game["total_achievements"] = achievement_data.get("total", 0)
                    base_game["unlocked_achievements"] = achievement_data.get("unlocked", 0)
                    
                    # Calculate percentage
                    if base_game["total_achievements"] > 0:
                        base_game["achievement_percentage"] = round((base_game["unlocked_achievements"] / base_game["total_achievements"]) * 100, 1)
                    else:
                        base_game["achievement_percentage"] = 0.0
            except Exception:
                pass  # Continue with has_achievements = False
            
            return base_game
            
        except Exception as e:
            decky.logger.error(f"Failed to process game {game.get('name', 'Unknown')}: {e}")
            return None
    
    async def get_recently_played_games(self, count: int = 20) -> List[Dict]:
        """Get recently played games with memory-optimized streaming processing"""
        if not self.achievement_service:
            return []
        
        try:
            if not self.api:
                return []
                
            response = await self.api.get_recently_played_games()
            if not response or response.get("error") or "response" not in response or "games" not in response["response"]:
                if response and response.get("error"):
                    decky.logger.error(f"Failed to get recently played games: {response['error']}")
                return []
            
            # Extract and limit games immediately to free up response memory
            games = response["response"]["games"][:min(count, LIMITS["MAX_GAMES"])]
            if len(games) != count:
                decky.logger.info(f"Limited games to {len(games)} to prevent memory issues (requested {count})")
            
            # Clear large response object immediately to free memory
            response = None
            
            decky.logger.info(f"Processing {len(games)} games directly...")
            
            all_enhanced_games = []
            
            for game in games:
                enhanced_game = await self._process_single_game(game)
                if enhanced_game:
                    all_enhanced_games.append(enhanced_game)
            
            decky.logger.info(f"Successfully processed {len(all_enhanced_games)} games")
            return all_enhanced_games
            
        except Exception as e:
            decky.logger.error(f"Failed to get recently played games: {e}")
            return []
    
    # ==================== Cache Management ====================
    
    async def refresh_cache(self, app_id: int = None) -> bool:
        """Refresh cache"""
        # Clear main cache service files
        cache_success = await self.cache_service.clear_cache(app_id)
        
        # Also clear Steam API cache if API is initialized
        if self.api:
            try:
                # Clear in-memory caches
                self.api.clear_memory_cache(app_id)
                
                if app_id:
                    # Clear specific game cache from Steam API cache
                    steam_cache_file = self.api.cache_dir / f"game_{app_id}.json"
                    if steam_cache_file.exists():
                        steam_cache_file.unlink()
                        decky.logger.info(f"Cleared Steam API cache for app {app_id}")
                else:
                    # Clear all Steam API cache files
                    if self.api.cache_dir.exists():
                        for cache_file in self.api.cache_dir.glob("game_*.json"):
                            cache_file.unlink()
                        decky.logger.info("Cleared all Steam API cache files")
            except Exception as e:
                decky.logger.warning(f"Failed to clear Steam API cache: {e}")
        
        return cache_success
    
    async def is_desktop_mode(self) -> bool:
        """Check if currently in Gaming Mode"""
        return self.steam_scanner.check_is_desktop_mode()
    
    # ==================== Private Methods ====================
    
    async def _reinitialize_api(self):
        """Reinitialize API after settings change"""
        try:
            # Clean up achievement service first
            if self.achievement_service:
                try:
                    await self.achievement_service.close()
                except Exception as e:
                    decky.logger.warning(f"Error closing existing achievement service: {e}")
                finally:
                    self.achievement_service = None
            
            # Then properly close existing API session
            if self.api:
                try:
                    await self.api.close()
                    # Give time for full cleanup
                    await asyncio.sleep(DELAYS["CLEANUP"])
                except Exception as e:
                    decky.logger.warning(f"Error closing existing API session: {e}")
                finally:
                    self.api = None
                    # Force garbage collection to clean up any remaining references
                    gc.collect()
            
            if self.steam_api_key and self.current_user_id:
                self.api = SteamAPI(self.steam_api_key, self.current_user_id, self.cache_dir)
                self.achievement_service = AchievementService(
                    self.api,
                    self.cache_service,
                    self.steam_api_key,
                    self.current_user_id
                )
                decky.logger.info("API and services reinitialized")
        except Exception as e:
            decky.logger.error(f"Failed to reinitialize API: {e}")
            # Ensure cleanup even on error
            self.api = None
            self.achievement_service = None
            gc.collect()