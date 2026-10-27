"""
Check if user has set custom artwork via SteamGridDB plugin
"""
import base64
import mimetypes
from pathlib import Path
from typing import Dict, Optional, List


class SteamGridDBService:
    def __init__(self):
        # Common Steam installation paths on Steam Deck and Linux
        self.steam_paths = [
            Path.home() / ".local/share/Steam",
            Path("/home/deck/.steam/steam"),
            Path("/home/deck/.local/share/Steam"),
            Path("/home/deck/.steam/root"),  # Alternative Steam path
        ]
    
    def _find_steam_userdata_paths(self) -> List[Path]:
        """Find all valid Steam userdata paths"""
        userdata_paths = []
        
        for steam_path in self.steam_paths:
            if steam_path.exists():
                userdata_path = steam_path / "userdata"
                if userdata_path.exists():
                    userdata_paths.append(userdata_path)
        
        return userdata_paths
    
    def _check_grid_directory(self, grid_path: Path, app_id: int) -> Dict[str, Optional[str]]:
        """Check a specific grid directory for custom artwork files"""
        artwork = {"grid": None, "hero": None, "logo": None, "icon": None}
        
        if not grid_path.exists():
            return artwork
        
        # SteamGridDB plugin creates files with these naming patterns
        # Based on Steam's grid file naming conventions
        artwork_patterns = {
            "grid": [
                f"{app_id}p.png", f"{app_id}p.jpg", f"{app_id}p.jpeg",  # Portrait/vertical grid
                f"{app_id}.png", f"{app_id}.jpg", f"{app_id}.jpeg"       # Legacy grid format
            ],
            "hero": [
                f"{app_id}_hero.png", f"{app_id}_hero.jpg", f"{app_id}_hero.jpeg",
                f"{app_id}h.png", f"{app_id}h.jpg", f"{app_id}h.jpeg"    # Hero/header images
            ],
            "logo": [
                f"{app_id}_logo.png", f"{app_id}_logo.jpg", f"{app_id}_logo.jpeg",
                f"{app_id}l.png", f"{app_id}l.jpg", f"{app_id}l.jpeg"    # Logo images
            ],
            "icon": [
                f"{app_id}_icon.png", f"{app_id}_icon.jpg", f"{app_id}_icon.jpeg",
                f"{app_id}i.png", f"{app_id}i.jpg", f"{app_id}i.jpeg"    # Icon images
            ]
        }
        
        # Check for each artwork type
        for art_type, patterns in artwork_patterns.items():
            for pattern in patterns:
                art_file = grid_path / pattern
                if art_file.exists() and art_file.is_file():
                    # Verify it's actually an image file by checking size
                    try:
                        if art_file.stat().st_size > 0:
                            artwork[art_type] = str(art_file)
                            break  # Found valid file, move to next art type
                    except OSError:
                        continue
        
        return artwork
    
    def _file_path_to_data_url(self, file_path: str) -> Optional[str]:
        """Convert a file path to a data URL for frontend use"""
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists() or not file_path_obj.is_file():
                return None
                
            # Get MIME type
            mime_type, _ = mimetypes.guess_type(str(file_path_obj))
            if not mime_type or not mime_type.startswith('image/'):
                return None
                
            # Read and encode file
            with open(file_path_obj, 'rb') as f:
                file_content = f.read()
                
            encoded_content = base64.b64encode(file_content).decode('utf-8')
            return f"data:{mime_type};base64,{encoded_content}"
            
        except Exception as e:
            return None
    
    def get_user_custom_artwork(self, app_id: int, as_data_urls: bool = False) -> Dict[str, Optional[str]]:
        """
        Check if user has set custom artwork for this game via SteamGridDB plugin
        
        Args:
            app_id: Steam application ID
            as_data_urls: If True, return data URLs instead of file paths
            
        Returns:
            Dictionary with artwork types as keys and file paths or data URLs as values
        """
        try:
            final_artwork = {"grid": None, "hero": None, "logo": None, "icon": None}
            
            # Get all userdata paths
            userdata_paths = self._find_steam_userdata_paths()
            
            if not userdata_paths:
                return final_artwork
            
            # Check each userdata directory
            for userdata_path in userdata_paths:
                # Iterate through all user directories (Steam can have multiple users)
                for user_dir in userdata_path.iterdir():
                    if not user_dir.is_dir() or not user_dir.name.isdigit():
                        continue
                    
                    # Check the main grid directory
                    grid_path = user_dir / "config" / "grid"
                    artwork = self._check_grid_directory(grid_path, app_id)
                    
                    # Update final_artwork with any found files (first found wins)
                    for art_type, file_path in artwork.items():
                        if file_path and final_artwork[art_type] is None:
                            final_artwork[art_type] = file_path
            
            # Convert to data URLs if requested
            if as_data_urls:
                for art_type, file_path in final_artwork.items():
                    if file_path:
                        data_url = self._file_path_to_data_url(file_path)
                        final_artwork[art_type] = data_url
            
            return final_artwork
            
        except Exception as e:
            return {"grid": None, "hero": None, "logo": None, "icon": None}
    


# Global instance
steamgriddb_service = SteamGridDBService()