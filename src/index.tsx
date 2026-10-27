// index.tsx - Final Refactored Main Entry Point
import { staticClasses, definePlugin } from "@decky/ui";
import { useState, useEffect, useCallback, useRef, VFC } from "react";

// Import types
import { Tab, GameInfo, TrackedGame, AchievementData } from "./models";

// Import components
import { TabNavigation } from "./components/common/TabNavigation";
import { CurrentGameTab } from "./components/tabs/CurrentGameTab";
import { RecentTab } from "./components/tabs/RecentTab";
import { OverallTab } from "./components/tabs/OverallTab";
import { SettingsTabModal } from "./components/tabs/SettingsTab";

// Import hooks
import { useSettings } from "./hooks/useSettings";
import { useAchievements } from "./hooks/useAchievements";

// Import services
import { hybridAPI } from "./services/hybridApi";
import { steamClientAPI } from "./utils/steam_client";
import { FaTrophy } from "./utils/icons";
import { logger } from "./utils/logger";

// Main Content Component
const Content: VFC = () => {
  const [currentTab, setCurrentTab] = useState<Tab>(() => {
    // Load from localStorage on initialization
    const savedTab = localStorage.getItem('sdachievement-current-tab');
    return (savedTab && Object.values(Tab).includes(savedTab as Tab)) ? savedTab as Tab : Tab.CURRENT_GAME;
  });
  const [currentGame, setCurrentGame] = useState<GameInfo | null>(null);
  const [trackedGame, setTrackedGame] = useState<TrackedGame | null>(null);
  const [trackedGameAchievements, setTrackedGameAchievements] = useState<AchievementData | null>(null);
  const [installedGames, setInstalledGames] = useState<GameInfo[]>([]);
  const [isClearingTrackedGame, setIsClearingTrackedGame] = useState(false);

  // Custom hooks
  const settings = useSettings();
  const achievements = useAchievements();

  // Fetch current game
  const fetchCurrentGame = useCallback(async (): Promise<GameInfo | null> => {
    try {
      const result = await hybridAPI.getCurrentGame();
      if (result) {
        setCurrentGame(result);
        return result;
      }
    } catch (error) {
      logger.error("Failed to fetch current game", error);
    }
    return null;
  }, []);

  // Fetch tracked game achievements
  const fetchTrackedGameAchievements = useCallback(async () => {
    if (!trackedGame) return;

    try {
      const result = await hybridAPI.getAchievements(trackedGame.app_id);
      if (result && !result.error) {
        setTrackedGameAchievements(result);
      }
    } catch (error) {
      logger.error("Failed to fetch tracked game achievements", error);
    }
  }, [trackedGame]);

  // Handle game refresh
  const handleRefreshGame = useCallback(async (): Promise<GameInfo | null> => {
    const game = await fetchCurrentGame();
    if (game) {
      await achievements.fetchAchievements(game.app_id);
    }
    return game;
  }, [fetchCurrentGame, achievements.fetchAchievements]);

  // Handle achievement refresh
  const handleRefreshAchievements = useCallback(async () => {
    if (currentGame) {
      await achievements.handleRefresh(currentGame.app_id);
    }
  }, [currentGame, achievements.handleRefresh]);

  // Handle full refresh (for settings changes)
  const handleFullRefresh = useCallback(async () => {
    const game = await fetchCurrentGame();
    if (game) {
      await achievements.fetchAchievements(game.app_id);
    }
    if (currentTab === Tab.RECENT) {
      await achievements.fetchRecentAchievements();
    }
    if (currentTab === Tab.OVERALL) {
      await achievements.fetchOverallProgress();
    }
  }, [currentTab]); // FIXED: Removed function dependencies that cause infinite loops

  // Initial load
  useEffect(() => {
    const initializePlugin = async () => {
      try {
        // Load settings first (the tracked game is synced from settings by the effect below)
        await settings.loadPluginSettings();

        // Load current game
        const game = await fetchCurrentGame();
        if (game) {
          await achievements.fetchAchievements(game.app_id);
        }

        // Load games list (uses caching for better performance)
        try {
          const gamesList = await hybridAPI.getGames(); // Uses cached version for fast loading

          if (gamesList && Array.isArray(gamesList)) {
            setInstalledGames(gamesList);
          } else {
            logger.error("Failed to get games list:", gamesList);
            // Fallback to perfect games if scanning fails
            if (achievements.overallProgress?.perfect_games) {
              setInstalledGames(achievements.overallProgress.perfect_games);
            }
          }
        } catch (error) {
          logger.error("Failed to get games list:", error);
        }
      } catch (error) {
        logger.error("Failed to initialize plugin:", error);
      }
    };

    initializePlugin();
  }, []);

  // Load data for restored tab after initial setup
  useEffect(() => {
    if (!settings.settingsLoaded) return; // Wait for settings to load
    
    // Load data for the current tab (which might be restored from localStorage)
    switch (currentTab) {
      case Tab.RECENT:
        if (achievements.recentAchievements.length === 0) {
          achievements.fetchRecentAchievements();
        }
        break;
      case Tab.OVERALL:
        if (!achievements.overallProgress) {
          achievements.fetchOverallProgress();
        }
        break;
    }
  }, [settings.settingsLoaded, currentTab]);

  // Auto-refresh effect with optimized dependencies
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  
  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    
    if (settings.autoRefresh && currentTab === Tab.CURRENT_GAME && settings.refreshInterval > 0) {
      intervalRef.current = setInterval(async () => {
        try {
          const game = await fetchCurrentGame();
          if (game?.app_id) {
            await achievements.fetchAchievements(game.app_id);
          }
        } catch (error) {
          logger.error('Auto-refresh error:', error);
        }
      }, settings.refreshInterval * 1000);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [settings.autoRefresh, settings.refreshInterval, currentTab]);

  // Sync tracked game from settings
  useEffect(() => {
    // Only sync if settings are loaded and we're not actively clearing
    if (!settings.settingsLoaded || isClearingTrackedGame) {
      return;
    }
    if (settings.trackedGame && (!trackedGame || settings.trackedGame.app_id !== trackedGame.app_id)) {
      setTrackedGame(settings.trackedGame);

      // Also load achievements if we don't have them
      if (!trackedGameAchievements) {
        const loadTrackedAchievements = async () => {
          try {
            const result = await hybridAPI.getAchievements(settings.trackedGame!.app_id);
            if (result && !result.error) {
              setTrackedGameAchievements(result);
            }
          } catch (error) {
            logger.error("Failed to load tracked game achievements", error);
          }
        };
        loadTrackedAchievements();
      }
    } else if (!settings.trackedGame && trackedGame) {
      setTrackedGame(null);
      setTrackedGameAchievements(null);
    }
  }, [settings.trackedGame, settings.settingsLoaded, trackedGame, trackedGameAchievements, isClearingTrackedGame]);

  // CurrentGameTab is now always available

  // Tab change handler
  const handleTabChange = (tab: Tab) => {
    // Redirect to settings if trying to access API-required tabs without API key
    if ((tab === Tab.RECENT || tab === Tab.OVERALL) && !settings.apiKeySet) {
      setCurrentTab(Tab.SETTINGS);
      localStorage.setItem('sdachievement-current-tab', Tab.SETTINGS);
      if (!settings.settingsLoaded) {
        settings.loadPluginSettings();
      }
      return;
    }

    setCurrentTab(tab);
    // Save to localStorage
    localStorage.setItem('sdachievement-current-tab', tab);

    // Load data when switching tabs
    switch (tab) {
      case Tab.RECENT:
        if (achievements.recentAchievements.length === 0) {
          achievements.fetchRecentAchievements();
        }
        break;
      case Tab.OVERALL:
        if (!achievements.overallProgress) {
          achievements.fetchOverallProgress();
        }
        break;
      case Tab.SETTINGS:
        if (!settings.settingsLoaded) {
          settings.loadPluginSettings();
        }
        break;
    }
  };

  // Update installed games when overall progress changes (fallback if scan failed)
  useEffect(() => {
    if (achievements.overallProgress?.perfect_games && installedGames.length === 0) {
      // Fallback: try to get games list first, then use perfect games
      const tryLoadGamesList = async () => {
        try {
          const gamesList = await hybridAPI.getGames();

          if (gamesList?.length > 0) {
            setInstalledGames(gamesList);
          } else {
            // Use perfect games as final fallback
            if (achievements.overallProgress?.perfect_games) {
              setInstalledGames(achievements.overallProgress.perfect_games);
            }
          }
        } catch (error) {
          logger.error("Fallback games fetch failed, using perfect games:", error);
          if (achievements.overallProgress?.perfect_games) {
            setInstalledGames(achievements.overallProgress.perfect_games);
          }
        }
      };

      tryLoadGamesList();
    }
  }, [achievements.overallProgress, installedGames.length]);

  // Tracked game handlers
  const handleSetTrackedGame = async (game: TrackedGame) => {
    try {
      const success = await hybridAPI.setTrackedGame(game.app_id, game.name);
      if (success) {
        setTrackedGame(game); // This is the state setter, not the API function
        // Also fetch achievements for the newly tracked game
        const result = await hybridAPI.getAchievements(game.app_id);
        if (result && !result.error) {
          setTrackedGameAchievements(result);
        }
        // Reload settings to ensure persistence
        await settings.loadPluginSettings();
      } else {
        logger.error("Failed to save tracked game to backend");
      }
    } catch (error) {
      logger.error("Failed to save tracked game:", error);
    }
  };

  const handleClearTrackedGame = async () => {
    try {

      // Set clearing flag to prevent sync interference
      setIsClearingTrackedGame(true);

      const success = await hybridAPI.clearTrackedGame();

      if (success) {

        // Clear local state
        setTrackedGame(null);
        setTrackedGameAchievements(null);

        // Force reload settings to sync with backend
        await settings.loadPluginSettings();

      } else {
        logger.error("Clear tracked game API returned false");
      }

    } catch (error) {
      logger.error("Failed to clear tracked game:", error);
    } finally {
      // Always clear the flag after operation
      setIsClearingTrackedGame(false);
    }
  };

  // Render tab content
  const renderTabContent = () => {
    switch (currentTab) {
      case Tab.CURRENT_GAME:
        return (
          <CurrentGameTab
            currentGame={currentGame}
            achievements={achievements.achievements}
            trackedGame={trackedGame}
            trackedGameAchievements={trackedGameAchievements}
            games={installedGames}
            isLoading={achievements.isLoading}
            loadingMessage={achievements.loadingMessage}
            onRefreshGame={handleRefreshGame}
            onRefreshAchievements={handleRefreshAchievements}
            onSetTrackedGame={handleSetTrackedGame}
            onClearTrackedGame={handleClearTrackedGame}
            onFetchTrackedAchievements={fetchTrackedGameAchievements}
          />
        );

      case Tab.RECENT:
        return (
          <RecentTab
            recentAchievements={achievements.recentAchievements}
            isLoading={achievements.isLoading}
          />
        );

      case Tab.OVERALL:
        return (
          <OverallTab
            overallProgress={achievements.overallProgress}
            recentlyPlayedGames={achievements.recentlyPlayedGames}
            isLoading={achievements.isLoading}
            onFetchRecentlyPlayed={achievements.fetchRecentlyPlayedGames}
          />
        );

      case Tab.SETTINGS:
        return (
          <SettingsTabModal
            settings={settings}
            games={installedGames}
            trackedGame={trackedGame}
            onFullRefresh={handleFullRefresh}
            onForceRefreshRecent={() => achievements.fetchRecentAchievements(true)}
            onSetTrackedGame={handleSetTrackedGame}
            onClearTrackedGame={handleClearTrackedGame}
          />
        );

      default:
        return null;
    }
  };


  return (
    <>
      <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
        <TabNavigation
          currentTab={currentTab}
          onTabChange={handleTabChange}
          apiKeySet={settings.apiKeySet}
        />
        <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
          {renderTabContent()}
        </div>
      </div>
    </>
  );
};


// Plugin Definition
export default definePlugin(() => {

  return {
    name: "SDAchievement",
    titleView: <div className={staticClasses.Title}>SDAchievement</div>,
    content: <Content />,
    icon: <FaTrophy />,
    onDismount() {
      // Clean up when plugin is completely unloaded
      steamClientAPI.dispose();
    },
  };
});