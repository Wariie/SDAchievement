"""
Steam localconfig.vdf parser service
Parses Steam's localconfig.vdf file for enhanced game detection and activity data
"""
import re
import time
import struct
import decky
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class LocalConfigParser:
    """Parser for Steam's localconfig.vdf file"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.steam_paths = [
            Path(f"/home/deck/.local/share/Steam/userdata/{user_id}/config/localconfig.vdf"),
            Path(f"/home/deck/.steam/steam/userdata/{user_id}/config/localconfig.vdf"),
            Path(decky.DECKY_USER_HOME) / f".local/share/Steam/userdata/{user_id}/config/localconfig.vdf",
            Path(decky.DECKY_USER_HOME) / f".steam/steam/userdata/{user_id}/config/localconfig.vdf"
        ]
        self.config_path = None
        self.cached_content = None
        self.cache_time = 0
        self.cache_duration = 30  # Cache for 30 seconds
    
    def _find_config_path(self) -> Optional[Path]:
        """Find the localconfig.vdf file path"""
        for path in self.steam_paths:
            if path.exists():
                decky.logger.info(f"Found localconfig.vdf at: {path}")
                return path
        
        decky.logger.warning(f"No localconfig.vdf found for user {self.user_id}")
        return None
    
    def _load_config_content(self) -> Optional[str]:
        """Load and cache the localconfig.vdf content"""
        current_time = time.time()
        
        # Return cached content if still valid
        if (self.cached_content and 
            current_time - self.cache_time < self.cache_duration):
            return self.cached_content
        
        # Find config path if not set
        if not self.config_path:
            self.config_path = self._find_config_path()
            if not self.config_path:
                return None
        
        try:
            with open(self.config_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            self.cached_content = content
            self.cache_time = current_time
            decky.logger.debug(f"Loaded localconfig.vdf ({len(content)} chars)")
            return content
            
        except Exception as e:
            decky.logger.error(f"Failed to load localconfig.vdf: {e}")
            return None
    
    def get_recent_games(self, limit: int = 10) -> List[Dict]:
        """Get recently played games from RecentLocalPlayedGameIDs"""
        content = self._load_config_content()
        if not content:
            return []
        
        try:
            # Find RecentLocalPlayedGameIDs section
            match = re.search(r'"RecentLocalPlayedGameIDs"\s*"([^"]*)"', content)
            if not match:
                decky.logger.debug("No RecentLocalPlayedGameIDs found in localconfig")
                return []
            
            recent_data = match.group(1)
            if not recent_data:
                return []
            
            # Parse the hex data - it's a series of 8-byte entries
            # Each entry: 4 bytes app_id + 4 bytes timestamp (little endian)
            games = []
            try:
                # Convert hex string to bytes
                data_bytes = bytes.fromhex(recent_data)
                
                # Parse entries (8 bytes each)
                for i in range(0, len(data_bytes), 8):
                    if i + 8 > len(data_bytes):
                        break
                    
                    # Unpack little endian: app_id (4 bytes), timestamp (4 bytes)
                    entry = data_bytes[i:i+8]
                    app_id, timestamp = struct.unpack('<LL', entry)
                    
                    if app_id > 0:  # Valid app ID
                        games.append({
                            "app_id": app_id,
                            "last_played": timestamp,
                            "last_played_date": datetime.fromtimestamp(timestamp) if timestamp > 0 else None
                        })
                
                # Sort by last played time (most recent first)
                games.sort(key=lambda x: x["last_played"], reverse=True)
                
                # Limit results
                recent_games = games[:limit]
                
                decky.logger.info(f"Found {len(recent_games)} recent games from localconfig")
                return recent_games
                
            except (ValueError, struct.error) as e:
                decky.logger.error(f"Failed to parse recent games data: {e}")
                return []
                
        except Exception as e:
            decky.logger.error(f"Error parsing recent games: {e}")
            return []
    
    def get_enhanced_game_data(self, app_id: int) -> Dict:
        """Get enhanced data for a specific game from Software section"""
        content = self._load_config_content()
        if not content:
            return {}
        
        try:
            # Look for the specific app in the Software.Valve.Steam.apps section
            app_pattern = rf'"{app_id}"\s*\{{([^}}]*(?:\{{[^}}]*\}}[^}}]*)*)\}}'
            match = re.search(app_pattern, content)
            
            if not match:
                decky.logger.debug(f"No data found for app {app_id} in localconfig")
                return {}
            
            app_section = match.group(1)
            game_data = {"app_id": app_id}
            
            # Extract LastPlayed timestamp
            last_played_match = re.search(r'"LastPlayed"\s*"(\d+)"', app_section)
            if last_played_match:
                timestamp = int(last_played_match.group(1))
                game_data["last_played"] = timestamp
                game_data["last_played_date"] = datetime.fromtimestamp(timestamp)
            
            # Extract total playtime (in minutes)
            playtime_match = re.search(r'"Playtime"\s*"(\d+)"', app_section)
            if playtime_match:
                playtime_minutes = int(playtime_match.group(1))
                game_data["playtime_forever"] = playtime_minutes
                game_data["playtime_hours"] = playtime_minutes / 60.0
            
            # Extract 2-week playtime
            playtime_2wks_match = re.search(r'"Playtime2wks"\s*"(\d+)"', app_section)
            if playtime_2wks_match:
                playtime_2wks = int(playtime_2wks_match.group(1))
                game_data["playtime_2weeks"] = playtime_2wks
                game_data["playtime_2weeks_hours"] = playtime_2wks / 60.0
            
            # Extract PlaytimeDisconnected (offline play)
            offline_match = re.search(r'"PlaytimeDisconnected"\s*"(\d+)"', app_section)
            if offline_match:
                offline_time = int(offline_match.group(1))
                game_data["playtime_offline"] = offline_time
            
            # Check for cloud sync status
            cloud_match = re.search(r'"cloud"\s*\{[^}]*"last_sync_state"\s*"([^"]+)"', app_section)
            if cloud_match:
                game_data["cloud_sync_state"] = cloud_match.group(1)
            
            # Check for autocloud info (indicates recent activity)
            autocloud_match = re.search(r'"autocloud"\s*\{([^}]*)\}', app_section)
            if autocloud_match:
                autocloud_section = autocloud_match.group(1)
                
                # Extract last launch and exit times
                launch_match = re.search(r'"lastlaunch"\s*"(\d+)"', autocloud_section)
                if launch_match:
                    game_data["last_launch"] = int(launch_match.group(1))
                
                exit_match = re.search(r'"lastexit"\s*"(\d+)"', autocloud_section)
                if exit_match:
                    game_data["last_exit"] = int(exit_match.group(1))
            
            # Check badge data (achievements/cards)
            badge_match = re.search(r'"BadgeData"\s*"([^"]+)"', app_section)
            if badge_match:
                game_data["badge_data"] = badge_match.group(1)
            
            decky.logger.debug(f"Enhanced data for app {app_id}: {game_data}")
            return game_data
            
        except Exception as e:
            decky.logger.error(f"Error getting enhanced data for app {app_id}: {e}")
            return {}
    
    def is_game_recently_active(self, app_id: int, minutes: int = 30) -> bool:
        """Check if a game was active recently based on various indicators"""
        try:
            # Get enhanced game data
            game_data = self.get_enhanced_game_data(app_id)
            current_time = time.time()
            threshold = current_time - (minutes * 60)
            
            # Check last played time
            if game_data.get("last_played", 0) > threshold:
                return True
            
            # Check last exit time from autocloud
            if game_data.get("last_exit", 0) > threshold:
                return True
            
            # Check if it's in recent games list
            recent_games = self.get_recent_games(limit=5)
            for game in recent_games:
                if game["app_id"] == app_id and game["last_played"] > threshold:
                    return True
            
            return False
            
        except Exception as e:
            decky.logger.error(f"Error checking recent activity for app {app_id}: {e}")
            return False