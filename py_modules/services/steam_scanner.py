"""
Steam installation scanner service
Scans local Steam installation to find installed games
"""
import re
import subprocess
import asyncio
import decky
from pathlib import Path
from typing import List, Dict, Optional
from .localconfig_parser import LocalConfigParser


class SteamScannerService:
    """Scans local Steam installation for installed games"""
    
    def __init__(self):
        self.localconfig_parser = None
        self.current_user_id = None
        self.steam_paths = [
            Path.home() / ".local/share/Steam",  # Default Steam path on Steam Deck
            Path("/home/deck/.steam/steam"),      # Alternative path
            Path("/home/deck/.local/share/Steam"), # Another common path
        ]
        self._cached_steam_path = None  # Cache to prevent repeated logs
        
    def get_steam_path(self) -> Optional[Path]:
        """Find the Steam installation path with caching to prevent spam"""
        if self._cached_steam_path is not None:
            return self._cached_steam_path
            
        for path in self.steam_paths:
            if path.exists() and path.is_dir():
                decky.logger.info(f"Found Steam installation at: {path}")
                self._cached_steam_path = path
                return path
        
        decky.logger.warning("Could not find Steam installation path")
        self._cached_steam_path = None
        return None
    
    def get_library_folders(self, steam_path: Path) -> List[Path]:
        """Get all Steam library folders from libraryfolders.vdf"""
        library_folders = []
        
        # Try to read libraryfolders.vdf
        vdf_path = steam_path / "steamapps" / "libraryfolders.vdf"
        if not vdf_path.exists():
            decky.logger.warning(f"libraryfolders.vdf not found at {vdf_path}")
            # Fallback to default steamapps folder
            default_steamapps = steam_path / "steamapps"
            if default_steamapps.exists():
                library_folders.append(default_steamapps)
            return library_folders
        
        try:
            with open(vdf_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Parse VDF format to find library paths
            # Look for "path" entries in the VDF file
            path_pattern = r'"path"\s*"([^"]+)"'
            paths = re.findall(path_pattern, content)
            
            for path_str in paths:
                # Convert Windows paths to proper format
                path_str = path_str.replace('\\\\', '/')
                library_path = Path(path_str) / "steamapps"
                if library_path.exists():
                    library_folders.append(library_path)
                    decky.logger.info(f"Found library folder: {library_path}")
                    
        except Exception as e:
            decky.logger.error(f"Error reading libraryfolders.vdf: {e}")
            # Fallback to default
            default_steamapps = steam_path / "steamapps"
            if default_steamapps.exists():
                library_folders.append(default_steamapps)
                
        return library_folders
    
    async def scan_acf_files_async(self, steamapps_path: Path) -> List[Dict]:
        """Async scan .acf files in a steamapps directory"""
        installed_games = []
        
        try:
            acf_files = list(steamapps_path.glob("appmanifest_*.acf"))
            decky.logger.info(f"Found {len(acf_files)} ACF files in {steamapps_path}")
            
            # Process files in batches to avoid overwhelming the system
            batch_size = 10
            loop = asyncio.get_event_loop()
            
            for i in range(0, len(acf_files), batch_size):
                batch = acf_files[i:i + batch_size]
                tasks = []
                
                for acf_file in batch:
                    task = loop.run_in_executor(None, self._read_acf_file, acf_file)
                    tasks.append(task)
                
                # Wait for batch to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        decky.logger.error(f"Error in ACF batch: {result}")
                        continue
                    if result:
                        installed_games.append(result)
                        
        except Exception as e:
            decky.logger.error(f"Error scanning ACF files in {steamapps_path}: {e}")
            
        return installed_games
    
    def _read_acf_file(self, acf_file: Path) -> Optional[Dict]:
        """Helper method to read and parse a single ACF file"""
        try:
            with open(acf_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return self.parse_acf_content(content)
        except Exception as e:
            decky.logger.error(f"Error reading ACF file {acf_file}: {e}")
            return None
    
    
    def _initialize_localconfig_parser(self, user_id: str):
        """Initialize LocalConfigParser for enhanced data"""
        if self.current_user_id != user_id or not self.localconfig_parser:
            self.current_user_id = user_id
            self.localconfig_parser = LocalConfigParser(user_id)
            decky.logger.info(f"SteamScanner: Initialized LocalConfigParser for user {user_id}")
    
    # Note: Steam user ID detection moved to frontend using SteamClient API
    
    def parse_acf_content(self, content: str) -> Optional[Dict]:
        """Parse ACF file content to extract game info"""
        try:
            # Extract appid
            appid_match = re.search(r'"appid"\s*"(\d+)"', content)
            if not appid_match:
                return None
            app_id = int(appid_match.group(1))
            
            # Extract name
            name_match = re.search(r'"name"\s*"([^"]+)"', content)
            if not name_match:
                return None
            name = name_match.group(1)
            
            # Extract install directory
            installdir_match = re.search(r'"installdir"\s*"([^"]+)"', content)
            installdir = installdir_match.group(1) if installdir_match else ""
            
            # Check if it's installed (state flags)
            state_match = re.search(r'"StateFlags"\s*"(\d+)"', content)
            state = int(state_match.group(1)) if state_match else 0
            
            # State flag 4 means "fully installed"
            is_installed = (state & 4) != 0
            
            if is_installed:
                game_data = {
                    "app_id": app_id,
                    "name": name,
                    "installdir": installdir,
                    "has_achievements": True,  # We'll assume all games might have achievements
                    "achievements": 0,  # Will be filled later if needed
                    "is_running": False,
                    "playtime_forever": 0
                }
                
                # Enhance with localconfig data if available
                if self.localconfig_parser:
                    try:
                        enhanced_data = self.localconfig_parser.get_enhanced_game_data(app_id)
                        if enhanced_data:
                            # Update with enhanced data
                            game_data.update(enhanced_data)
                            
                            # Add formatted fields
                            if enhanced_data.get("playtime_forever"):
                                game_data["playtime_formatted"] = self._format_playtime(enhanced_data["playtime_forever"])
                            
                            if enhanced_data.get("last_played_date"):
                                game_data["last_played_formatted"] = self._format_last_played(enhanced_data["last_played_date"])
                            
                            # Check recent activity
                            game_data["recently_active"] = self.localconfig_parser.is_game_recently_active(app_id)
                    except Exception as e:
                        decky.logger.debug(f"Failed to enhance ACF data for {app_id}: {e}")
                
                return game_data
                
        except Exception as e:
            decky.logger.error(f"Error parsing ACF content: {e}")
            
        return None
    
    def _format_playtime(self, minutes: int) -> str:
        """Format playtime minutes into a readable string"""
        if minutes < 60:
            return f"{minutes} min"
        elif minutes < 1440:  # Less than a day
            hours = minutes / 60
            return f"{hours:.1f} hours"
        else:
            hours = minutes / 60
            return f"{hours:.0f} hours"
    
    def _format_last_played(self, last_played_date) -> str:
        """Format last played date into a readable string"""
        try:
            from datetime import datetime
            now = datetime.now()
            diff = now - last_played_date
            
            if diff.days == 0:
                if diff.seconds < 3600:  # Less than an hour
                    minutes = diff.seconds // 60
                    return f"{minutes} minutes ago"
                else:
                    hours = diff.seconds // 3600
                    return f"{hours} hours ago"
            elif diff.days == 1:
                return "Yesterday"
            elif diff.days < 7:
                return f"{diff.days} days ago"
            else:
                return last_played_date.strftime("%B %d, %Y")
        except Exception:
            return "Unknown"
    
    async def get_installed_games(self, user_id: Optional[str] = None) -> List[Dict]:
        """Get all installed Steam games by scanning ACF files"""
        try:
            decky.logger.info("Starting Steam installed games scan...")
            
            steam_path = self.get_steam_path()
            if not steam_path:
                return []
            
            # Initialize LocalConfigParser if user_id is provided
            if user_id:
                self._initialize_localconfig_parser(user_id)
            else:
                decky.logger.info("No user_id provided - scanning games without enhanced data from localconfig")
            
            library_folders = self.get_library_folders(steam_path)
            if not library_folders:
                decky.logger.warning("No Steam library folders found")
                return []
            
            all_games = []
            for library_folder in library_folders:
                games = await self.scan_acf_files_async(library_folder)
                all_games.extend(games)
                decky.logger.info(f"Found {len(games)} games in {library_folder}")
            
            # Remove duplicates based on app_id
            unique_games = {}
            for game in all_games:
                unique_games[game["app_id"]] = game
            
            final_games = list(unique_games.values())
            # Sort by name for better UX
            final_games.sort(key=lambda x: x["name"].lower())
            
            decky.logger.info(f"Total installed games found: {len(final_games)}")
            
            # Sort by recent activity if localconfig is available
            if self.localconfig_parser:
                try:
                    # Sort by: recently active, then by last played, then by name
                    def sort_key(game):
                        recently_active = game.get("recently_active", False)
                        last_played = game.get("last_played", 0)
                        name = game.get("name", "").lower()
                        
                        # Priority: recently active games first, then by last played, then alphabetical
                        return (not recently_active, -last_played, name)
                    
                    final_games.sort(key=sort_key)
                    decky.logger.info("Sorted games by recent activity")
                except Exception as e:
                    decky.logger.warning(f"Failed to sort by activity: {e}")
            
            return final_games
            
        except Exception as e:
            decky.logger.error(f"Error scanning installed games: {e}")
            return []
        
    def get_game_artwork(self, app_id: int) -> Dict[str, Optional[Path]]:
        """Return paths to artwork files for a given game (grid, hero, logo, icon)."""
        steam_path = self.get_steam_path()
        if not steam_path:
            return {}

        user_paths = list((steam_path / "userdata").glob("*/config/grid"))
        artwork = {"grid": None, "hero": None, "logo": None, "icon": None}

        # Check user-specific artwork overrides
        for grid_path in user_paths:
            for suffix in ["", "_hero", "_logo", "_icon"]:
                file = grid_path / f"{app_id}{suffix}.png"
                if file.exists():
                    key = suffix[1:] if suffix else "grid"
                    artwork[key] = file

        # Fallback: librarycache (official Steam artwork)
        cache_path = steam_path / "appcache/librarycache"
        for key in artwork:
            if not artwork[key]:
                fallback = cache_path / f"{app_id}_{key}.jpg"
                if fallback.exists():
                    artwork[key] = fallback
        
        return artwork
    
    def check_is_desktop_mode(self) -> bool:
        """Quick and lightweight mode detection"""
        try:
            # Single command to check if kwin_x11 is running
            result = subprocess.run(['pgrep', '-x', 'kwin_x11'], 
                                  capture_output=True, 
                                  timeout=3)
            
            is_desktop = result.returncode == 0
            
            return is_desktop
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return False
    
