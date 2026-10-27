// services/hybridApi.tsx
import { GameInfo, AchievementData, RecentAchievement, OverallProgress } from "../models";
import * as pythonApi from "./api";
import { steamClientAPI } from "../utils/steam_client";
import { STEAM_API_DEFAULTS } from "../constants/steam";
import { logger } from "../utils/logger";

export class HybridSteamAPI {

  /**
   * Get current game
   */
  async getCurrentGame(): Promise<GameInfo | null> {
    return await pythonApi.getCurrentGame();
  }

  /**
   * Get achievements - Use Python backend for consistent data with global percentages
   */
  async getAchievements(appId?: number): Promise<AchievementData> {
    const targetAppId = appId || (await this.getCurrentGame())?.app_id;

    if (!targetAppId) {
      return { error: "No game running and no app ID provided" } as AchievementData;
    }

    // Use Python backend which includes global percentage data
    try {
      const result = await pythonApi.getAchievements(targetAppId);
      if (result && !result.error) {
        return result;
      }
    } catch (error) {
      logger.warn('Python backend getAchievements failed:', error);
    }

    // Fallback to Steam client if backend fails
    try {
      const steamResult = await steamClientAPI.getMyAchievementsForApp(targetAppId);
      if (steamResult) {
        return steamResult;
      }
    } catch (error) {
      logger.warn('SteamClient getMyAchievementsForApp failed:', error);
    }

    // No data available
    return { error: "Achievement data not available" } as AchievementData;
  }

  /**
   * Tracked game - Always use Python backend
   */
  async setTrackedGame(appId: number, name: string): Promise<boolean> {
    return await pythonApi.setTrackedGame(appId, name);
  }

  async clearTrackedGame(): Promise<boolean> {
    return await pythonApi.clearTrackedGame();
  }

  /**
   * Get games list - Use full library if API key available, otherwise installed games (with caching)
   */
  async getGames(): Promise<GameInfo[]> {

    // Try to get full user library first (requires Steam API key)
    try {
      const userGames = await pythonApi.getUserGames();
      if (userGames?.length > 0) {
        return userGames;
      }
    } catch (error) {
      logger.warn('Failed to get user games (likely no API key), falling back to installed games:', error);
    }

    // Fallback to installed games (local scanning)
    try {
      const installedGames = await pythonApi.getInstalledGames();
      return installedGames;
    } catch (error) {
      logger.error('Failed to get any games:', error);
      return [];
    }
  }

  /**
   * Get recent achievements - Use Python backend (faster and more reliable)
   * Note: Steam API has 5-15 minute delay for new achievements
   */
  async getRecentAchievements(limit: number = STEAM_API_DEFAULTS.RECENT_ACHIEVEMENTS_LIMIT, forceRefresh: boolean = false): Promise<RecentAchievement[]> {
    if (forceRefresh) {
      logger.info('Force refreshing recent achievements');
    }

    // Use Python backend (faster and more reliable)
    logger.info('Using Python backend for recent achievements');
    try {
      const pythonResult = await pythonApi.getRecentAchievements(limit);

      if (pythonResult?.length > 0) {
        // Convert from Python format to RecentAchievement format
        const mapped = pythonResult.map((achievement: any) => ({
          game_name: achievement.game_name || 'Unknown Game',
          game_id: achievement.game_id || achievement.app_id || 0,
          achievement_name: achievement.achievement_name || achievement.display_name,
          achievement_desc: achievement.achievement_desc || achievement.description,
          unlock_time: achievement.unlock_time || 0,
          icon: achievement.icon,
          global_percent: achievement.global_percent || 0
        }));

        return mapped;
      }
    } catch (error) {
      logger.warn('Python backend getRecentAchievements failed:', error);
    }

    // Return empty data when Python fails
    return [];
  }

  /**
   * Get recently played games - Use Python backend (faster and more reliable)
   */
  async getRecentlyPlayedGames(count: number = STEAM_API_DEFAULTS.RECENT_GAMES_COUNT): Promise<GameInfo[]> {
    // Use Python backend (faster and more reliable)
    logger.info('Using Python backend for recently played games');
    try {
      const pythonResult = await pythonApi.getRecentlyPlayedGames(count);

      if (pythonResult?.length > 0) {
        return pythonResult;
      }
    } catch (error) {
      logger.warn('Python backend getRecentlyPlayedGames failed:', error);
    }

    // No data available
    return [];
  }

  /**
   * Get overall achievement progress - Use Python backend with caching and fast processing
   */
  async getAchievementProgress(forceRefresh: boolean = false): Promise<OverallProgress> {
    logger.info('Using Python backend for overall progress calculation');
    let error: string | undefined;
    try {
      const pythonResult = await pythonApi.getAchievementProgress(forceRefresh);

      // Pass backend errors through so callers can poll on "in progress" and show real failures
      error = pythonResult?.error;
      if (pythonResult && !pythonResult.error) {
        return {
          total_games: pythonResult.total_games || 0,
          games_with_achievements: pythonResult.games_with_achievements || 0,
          total_achievements: pythonResult.total_achievements || 0,
          unlocked_achievements: pythonResult.unlocked_achievements || 0,
          average_completion: pythonResult.average_completion || 0,
          perfect_games: pythonResult.perfect_games || [],
          perfect_games_count: pythonResult.perfect_games_count || 0
        };
      }
    } catch (err) {
      logger.warn('Python backend getAchievementProgress failed:', err);
      throw err;
    }

    // Return empty progress data with the backend error
    return {
      total_games: 0,
      games_with_achievements: 0,
      total_achievements: 0,
      unlocked_achievements: 0,
      average_completion: 0,
      perfect_games: [],
      perfect_games_count: 0,
      error: error || "No progress data returned"
    };
  }

  /**
   * Check if running in Desktop Mode
   */
  async isDesktopMode(): Promise<boolean> {
    return await pythonApi.isDesktopMode();
  }

  /**
   * Refresh achievement cache
   */
  async refreshCache(appId?: number): Promise<boolean> {
    // Backend handles all caching - just call backend refresh
    return await pythonApi.refreshCache(appId);
  }
}

// Export singleton instance
export const hybridAPI = new HybridSteamAPI();