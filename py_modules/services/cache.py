"""
Cache management service
"""
import json
import time
import asyncio
import decky
from pathlib import Path
from typing import Dict, Optional
from constants import TIME_CONSTANTS, CACHE_TTL


class FileCacheService:
    """Handles file-based caching operations with TTL support"""
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    async def get_overall_progress(self) -> Optional[Dict]:
        """Get cached overall progress if valid"""
        try:
            cache_file = self.cache_dir / "overall_progress.json"
            
            if cache_file.exists():
                cache_age = time.time() - cache_file.stat().st_mtime
                
                # Use cache if less than 24 hours old
                if cache_age < CACHE_TTL["PROGRESS_FILE_TTL"]:
                    # Use thread executor for non-blocking file read
                    loop = asyncio.get_event_loop()
                    
                    def read_file():
                        with open(cache_file, 'r') as f:
                            return f.read()
                    
                    content = await loop.run_in_executor(None, read_file)
                    cached_data = json.loads(content)
                    
                    decky.logger.info(f"Found cached progress (age: {cache_age/TIME_CONSTANTS['ONE_HOUR']:.1f} hours)")
                    return cached_data
            
            return None
            
        except Exception as e:
            decky.logger.warning(f"Failed to read cache: {e}")
            return None
    
    async def save_overall_progress(self, data: Dict) -> bool:
        """Save overall progress to cache"""
        try:
            cache_file = self.cache_dir / "overall_progress.json"
            
            # Use thread executor for non-blocking file write
            loop = asyncio.get_event_loop()
            content = json.dumps(data, indent=2)
            
            def write_file():
                with open(cache_file, 'w') as f:
                    f.write(content)
            
            await loop.run_in_executor(None, write_file)
            
            decky.logger.info("Overall progress cached successfully")
            return True
            
        except Exception as e:
            decky.logger.warning(f"Failed to cache progress: {e}")
            return False
    
    async def clear_cache(self, app_id: int = None, cache_type: str = "all") -> bool:
        """Clear cache files for a specific game or all games by cache type"""
        try:
            if app_id:
                # Remove specific cache files based on type
                if cache_type == "all" or cache_type == "achievements":
                    cache_files = [
                        self.cache_dir / f"achievements_{app_id}.json",
                        self.cache_dir / f"game_{app_id}.json"
                    ]
                    for cache_file in cache_files:
                        if cache_file.exists():
                            cache_file.unlink()
                
                if cache_type == "all" or cache_type == "progress":
                    progress_file = self.cache_dir / "overall_progress.json" 
                    if progress_file.exists():
                        progress_file.unlink()
                        
                decky.logger.info(f"Cache refreshed for app {app_id} (type: {cache_type})")
            else:
                # Clear cache files by type
                if cache_type == "all":
                    if self.cache_dir.exists():
                        for cache_file in self.cache_dir.glob("*.json"):
                            cache_file.unlink()
                    decky.logger.info("All cache cleared")
                elif cache_type == "achievements":
                    if self.cache_dir.exists():
                        for cache_file in self.cache_dir.glob("achievements_*.json"):
                            cache_file.unlink()
                        for cache_file in self.cache_dir.glob("game_*.json"):
                            cache_file.unlink()
                    decky.logger.info("Achievement cache cleared")
                elif cache_type == "progress":
                    progress_file = self.cache_dir / "overall_progress.json"
                    if progress_file.exists():
                        progress_file.unlink()
                    decky.logger.info("Progress cache cleared")
            
            return True
        except Exception as e:
            decky.logger.error(f"Failed to refresh cache: {e}")
            return False
    
