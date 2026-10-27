// hooks/useAchievements.tsx
import { useState, useCallback } from "react";
import { toaster } from "@decky/api";
import {
  AchievementData,
  RecentAchievement,
  OverallProgress,
  GameInfo
} from "../models";
import { hybridAPI } from "../services/hybridApi";
import { STEAM_API_DEFAULTS } from "../constants/steam";
import { logger } from "../utils/logger";

export interface UseAchievementsReturn {
  // State
  achievements: AchievementData | null;
  recentAchievements: RecentAchievement[];
  recentlyPlayedGames: GameInfo[];
  overallProgress: OverallProgress | null;
  isLoading: boolean;
  loadingMessage: string;

  // Actions
  fetchAchievements: (appId?: number) => Promise<void>;
  fetchRecentAchievements: (forceRefresh?: boolean) => Promise<void>;
  fetchRecentlyPlayedGames: () => Promise<void>;
  fetchOverallProgress: (forceRefresh?: boolean) => Promise<void>;
  handleRefresh: (appId?: number) => Promise<void>;
}

export const useAchievements = (): UseAchievementsReturn => {
  const [achievements, setAchievements] = useState<AchievementData | null>(null);
  const [recentAchievements, setRecentAchievements] = useState<RecentAchievement[]>([]);
  const [recentlyPlayedGames, setRecentlyPlayedGames] = useState<GameInfo[]>([]);
  const [overallProgress, setOverallProgress] = useState<OverallProgress | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("");

  const fetchAchievements = useCallback(async (appId?: number) => {
    setIsLoading(true);
    setLoadingMessage("Loading achievements...");
    try {
      const result = await hybridAPI.getAchievements(appId);
      if (result && !result.error) {
        setAchievements(result);
      } else if (result?.error) {
        toaster.toast({
          title: "Achievement Error",
          body: result.error,
          critical: true
        });
        setAchievements(null);
      }
    } catch (error) {
      logger.error("Failed to fetch achievements:", error);
      toaster.toast({
        title: "Error",
        body: "Failed to fetch achievements",
        critical: true
      });
      setAchievements(null);
    } finally {
      setIsLoading(false);
      setLoadingMessage("");
    }
  }, []);

  const fetchRecentAchievements = useCallback(async (forceRefresh: boolean = false) => {
    setIsLoading(true);
    setLoadingMessage(forceRefresh ? "Refreshing recent achievements..." : "Loading recent achievements...");
    try {
      const result = await hybridAPI.getRecentAchievements(STEAM_API_DEFAULTS.RECENT_ACHIEVEMENTS_LIMIT, forceRefresh);
      if (result) {
        setRecentAchievements(result);
      }
    } catch (error) {
      logger.error("Failed to fetch recent achievements:", error);
      toaster.toast({
        title: "Error",
        body: "Failed to fetch recent achievements",
        critical: true
      });
    } finally {
      setIsLoading(false);
      setLoadingMessage("");
    }
  }, []);

  const fetchRecentlyPlayedGames = useCallback(async () => {
    setIsLoading(true);
    setLoadingMessage("Loading recently played games...");
    try {
      const result = await hybridAPI.getRecentlyPlayedGames(STEAM_API_DEFAULTS.RECENT_GAMES_UI_COUNT);
      if (result) {
        setRecentlyPlayedGames(result);
      }
    } catch (error) {
      logger.error("Failed to fetch recently played games:", error);
      toaster.toast({
        title: "Error",
        body: "Failed to fetch recently played games",
        critical: true
      });
    } finally {
      setIsLoading(false);
      setLoadingMessage("");
    }
  }, []);

  const fetchOverallProgress = useCallback(async (forceRefresh: boolean = false) => {
    setIsLoading(true);
    setLoadingMessage(forceRefresh ? "Recalculating overall progress..." : "Loading overall progress...");
    
    const pollForResult = async (maxAttempts: number = STEAM_API_DEFAULTS.PROGRESS_POLL_MAX_ATTEMPTS, delay: number = STEAM_API_DEFAULTS.PROGRESS_POLL_DELAY): Promise<void> => {
      for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
          const result = await hybridAPI.getAchievementProgress(forceRefresh);
          
          if (result && !result.error) {
            setOverallProgress(result);
            return; // Success - exit polling
          } else if (result?.error?.includes("in progress")) {
            // Calculation still in progress - continue polling
            setLoadingMessage(`Calculating progress... (${Math.round(attempt * delay / 1000)}s)`);
            await new Promise(resolve => setTimeout(resolve, delay));
            continue;
          } else if (result?.error) {
            // Real error - show toast and exit
            toaster.toast({
              title: "Error",
              body: result.error,
              critical: true
            });
            return;
          }
        } catch (error) {
          logger.error(`Failed to fetch overall progress (attempt ${attempt}):`, error);
          if (attempt === maxAttempts) {
            toaster.toast({
              title: "Error",
              body: "Failed to fetch overall progress after multiple attempts",
              critical: true
            });
          } else {
            await new Promise(resolve => setTimeout(resolve, delay));
          }
        }
      }
      
      // If we get here, all attempts failed
      toaster.toast({
        title: "Timeout",
        body: "Progress calculation timed out. Please try again.",
        critical: true
      });
    };
    
    try {
      await pollForResult();
    } finally {
      setIsLoading(false);
      setLoadingMessage("");
    }
  }, []);

  const handleRefresh = useCallback(async (appId?: number) => {
    try {
      await hybridAPI.refreshCache(appId);
      if (appId) {
        await fetchAchievements(appId);
      }
      toaster.toast({
        title: "Refreshed",
        body: "Achievement data updated"
      });
    } catch (error) {
      logger.error("Failed to refresh:", error);
      toaster.toast({
        title: "Error",
        body: "Failed to refresh data",
        critical: true
      });
    }
  }, [fetchAchievements]);

  // REMOVED: Auto-refresh for recent achievements to prevent high CPU usage
  // Recent achievements are cached for 2 minutes and will refresh naturally when accessed

  return {
    // State
    achievements,
    recentAchievements,
    recentlyPlayedGames,
    overallProgress,
    isLoading,
    loadingMessage,

    // Actions
    fetchAchievements,
    fetchRecentAchievements,
    fetchRecentlyPlayedGames,
    fetchOverallProgress,
    handleRefresh
  };
};