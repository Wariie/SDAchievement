// constants/steam.ts

/**
 * Steam CDN URL templates for game artwork
 */
export const STEAM_CDN_URLS = {
  HEADER: (appId: number) => `https://cdn.akamai.steamstatic.com/steam/apps/${appId}/header.jpg`,
  GRID: (appId: number) => `https://cdn.akamai.steamstatic.com/steam/apps/${appId}/library_600x900.jpg`,
  ICON: (appId: number) => `https://cdn.akamai.steamstatic.com/steam/apps/${appId}/icon.jpg`,
  LOGO: (appId: number) => `https://cdn.akamai.steamstatic.com/steam/apps/${appId}/logo.png`
};


/**
 * Default limits and counts for Steam API calls
 */
export const STEAM_API_DEFAULTS = {
  RECENT_ACHIEVEMENTS_LIMIT: 15,        // More recent achievements for better overview
  RECENT_GAMES_COUNT: 25,               // Match UI count - get what we show
  RECENT_GAMES_UI_COUNT: 25,            // Show more games in UI (better for users with many games)
  PROGRESS_TRANSITION_DURATION: 0.2,    // Faster transitions for snappier UI
  
  // Progress calculation polling settings  
  PROGRESS_POLL_MAX_ATTEMPTS: 15,       // Reasonable attempts for responsiveness
  PROGRESS_POLL_DELAY: 1200             // Faster polling for better responsiveness
};

/**
 * Rarity filter thresholds (percentages)
 */
export const ACHIEVEMENT_RARITY = {
  ALL: 0,
  VERY_RARE: 1,
  RARE: 5,
  UNCOMMON: 10,
  COMMON: 25
};