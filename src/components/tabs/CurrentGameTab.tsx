// components/tabs/CurrentGameTab.tsx
import { VFC, useState, useCallback, useEffect, useMemo } from "react";
import { PanelSection, PanelSectionRow, ButtonItem, ToggleField, showModal } from "@decky/ui";
import { FaChevronDown, FaChevronUp } from "../../utils/icons";
import { GameInfo, AchievementData, SortBy, TrackedGame } from "../../models";
import { GameBanner } from "../game/GameBanner";
import { ProgressDisplay } from "../common/ProgressDisplay";
import { AchievementList } from "../achievements/AchievementList";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { GameSelectionModal } from "../game/GameSelectionModal";
import { steamClientAPI, isSteamClientAvailable } from "../../utils/steam_client";
import { hybridAPI } from "../../services/hybridApi";
import { STEAM_CDN_URLS, ACHIEVEMENT_RARITY } from "../../constants/steam";

interface CurrentGameTabProps {
  currentGame: GameInfo | null;
  achievements: AchievementData | null;
  trackedGame: TrackedGame | null;
  trackedGameAchievements: AchievementData | null;
  games: GameInfo[];
  isLoading: boolean;
  loadingMessage: string;
  onRefreshGame: () => Promise<GameInfo | null>;
  onRefreshAchievements: () => Promise<void>;
  onSetTrackedGame: (game: TrackedGame) => Promise<void>;
  onClearTrackedGame: () => Promise<void>;
  onFetchTrackedAchievements: () => Promise<void>;
}

export const CurrentGameTab: VFC<CurrentGameTabProps> = ({
  currentGame,
  achievements,
  trackedGame,
  trackedGameAchievements,
  games,
  isLoading,
  loadingMessage,
  onRefreshGame,
  onRefreshAchievements,
  onSetTrackedGame,
  onClearTrackedGame,
  onFetchTrackedAchievements
}) => {
  const [filters, setFilters] = useState({
    showHidden: false,
    sortBy: "unlock" as SortBy,
    sortOrder: "desc" as "asc" | "desc",
    rarity: ACHIEVEMENT_RARITY.ALL,
    showUnlockedOnly: false,
    showLockedOnly: false,
    expanded: false
  });
  const [viewMode, setViewMode] = useState<"current" | "tracked">("current");
  const [userSelectedView, setUserSelectedView] = useState(false); // Track if user manually selected a view
  const [achievementNotifications, setAchievementNotifications] = useState(true);

  const steamClientAvailable = isSteamClientAvailable();
  
  const monitorAppAchievements = useCallback((appId: number) => {
    if (!steamClientAvailable) return () => {};
    return steamClientAPI.onAchievementChanges(appId, () => {
      // Refresh backend cache when new achievement unlocked
      hybridAPI.refreshCache();
      // Trigger refresh for current achievements
      onRefreshAchievements();
    });
  }, [steamClientAvailable, onRefreshAchievements]);

  // Monitor for achievement notifications
  useEffect(() => {
    if (!achievementNotifications || !steamClientAvailable || !currentGame?.app_id) return;

    const unsubscribe = monitorAppAchievements(currentGame.app_id);
    return unsubscribe;
  }, [currentGame?.app_id, achievementNotifications, steamClientAvailable, monitorAppAchievements]);

  const displayAchievements = (viewMode === "current" ? achievements : trackedGameAchievements);
  const hasValidAchievements = displayAchievements && !displayAchievements.error;
  const hasAchievementsToShow = hasValidAchievements && displayAchievements.total > 0;

  // Compute the game to display in the banner
  const displayGame = useMemo(() => {
    if (viewMode === "current") {
      return currentGame;
    }
    
    if (trackedGame) {
      return {
        app_id: trackedGame.app_id,
        name: trackedGame.name,
        is_running: false,
        has_achievements: true,
        total_achievements: trackedGameAchievements?.total || 0,
        unlocked_achievements: trackedGameAchievements?.unlocked || 0,
        achievement_percentage: trackedGameAchievements?.percentage || 0,
        header_image: STEAM_CDN_URLS.HEADER(trackedGame.app_id),
        img_icon_url: STEAM_CDN_URLS.ICON(trackedGame.app_id),
        img_logo_url: STEAM_CDN_URLS.LOGO(trackedGame.app_id)
      };
    }
    
    return null;
  }, [viewMode, currentGame, trackedGame, trackedGameAchievements]);

  const handleRefresh = useCallback(async () => {
    if (viewMode === "current") {
      // Always try to refresh current game if we're in current mode or have no display game
      await onRefreshGame();
      if (currentGame) {
        await onRefreshAchievements();
      }
    } else {
      // Refresh tracked game achievements
      await onFetchTrackedAchievements();
    }
  }, [viewMode, onRefreshGame, currentGame, onRefreshAchievements, onFetchTrackedAchievements]);

  const handleSelectTrackedGame = useCallback(() => {

    let modalInstance: any = null;

    modalInstance = showModal(
      <GameSelectionModal
        games={games}
        onSelect={async (game) => {
          await onSetTrackedGame({
            app_id: game.app_id,
            name: game.name
          });
          modalInstance?.Close();
        }}
        closeModal={() => {
          modalInstance?.Close();
        }}
      />
    );
  }, [games, onSetTrackedGame]);

  // Reset manual selection when tracked game changes or is cleared
  useEffect(() => {
    setUserSelectedView(false);
  }, [trackedGame?.app_id]);

  // Auto-switch logic - prioritize current game when available, but respect manual selection
  useEffect(() => {
    // Only auto-switch if user hasn't manually selected a view
    if (!userSelectedView) {
      // Auto-switch to current game when it becomes available
      if (currentGame && viewMode === "tracked") {
        setViewMode("current");
      }
      // Only auto-switch to tracked if no current game and we have a tracked game
      else if (!currentGame && trackedGame && viewMode === "current") {
        setViewMode("tracked");
      }
    }
  }, [currentGame, trackedGame, viewMode, userSelectedView]);


  const getSortDisplayName = (sort: SortBy, order: "asc" | "desc"): string => {
    switch (sort) {
      case "unlock": return order === "desc" ? "Recently Unlocked" : "Oldest Unlocked";
      case "name": return `Name (${order === "asc" ? "A-Z" : "Z-A"})`;
      case "rarity": return `Rarity (${order === "asc" ? "Common First" : "Rare First"})`;
      default: return "Recently Unlocked";
    }
  };

  const getRarityDisplayName = (rarity: number): string => {
    const names = { 
      [ACHIEVEMENT_RARITY.ALL]: "All", 
      [ACHIEVEMENT_RARITY.VERY_RARE]: "Very Rare (≤1%)", 
      [ACHIEVEMENT_RARITY.RARE]: "Rare (≤5%)", 
      [ACHIEVEMENT_RARITY.UNCOMMON]: "Uncommon (≤10%)", 
      [ACHIEVEMENT_RARITY.COMMON]: "Common (≤25%)" 
    };
    return names[rarity as keyof typeof names] || "All";
  };

  const cycleSortOption = () => {
    const sortOptions = [
      { sort: "unlock" as SortBy, order: "desc" as const },
      { sort: "unlock" as SortBy, order: "asc" as const },
      { sort: "name" as SortBy, order: "asc" as const },
      { sort: "name" as SortBy, order: "desc" as const },
      { sort: "rarity" as SortBy, order: "asc" as const },
      { sort: "rarity" as SortBy, order: "desc" as const }
    ];
    
    const currentIndex = sortOptions.findIndex(
      option => option.sort === filters.sortBy && option.order === filters.sortOrder
    );
    const nextOption = sortOptions[(currentIndex + 1) % sortOptions.length];
    
    setFilters(prev => ({ ...prev, sortBy: nextOption.sort, sortOrder: nextOption.order }));
  };

  const cycleFilterRarity = () => {
    const rarities = [
      ACHIEVEMENT_RARITY.ALL,
      ACHIEVEMENT_RARITY.VERY_RARE,
      ACHIEVEMENT_RARITY.RARE,
      ACHIEVEMENT_RARITY.UNCOMMON,
      ACHIEVEMENT_RARITY.COMMON
    ];
    const nextIndex = (rarities.indexOf(filters.rarity) + 1) % rarities.length;
    setFilters(prev => ({ ...prev, rarity: rarities[nextIndex] }));
  };

  return (
    <div style={{ padding: "0", margin: "0" }}>
      {/* Game Banner */}
      <GameBanner
        game={displayGame}
        isLoading={isLoading}
        onRefresh={handleRefresh}
        trackedGame={trackedGame}
        onSetTrackedGame={onSetTrackedGame}
        onClearTrackedGame={onClearTrackedGame}
        onSelectTrackedGame={handleSelectTrackedGame}
        viewMode={viewMode}
        onViewModeChange={trackedGame && currentGame && trackedGame.app_id !== currentGame.app_id ? 
          (mode: "current" | "tracked") => {
            setUserSelectedView(true);
            setViewMode(mode);
          } : undefined}
      />


      {/* Achievement Progress */}
      {hasValidAchievements && (
        <PanelSection title="Progress">
          <PanelSectionRow>
            <ProgressDisplay
              unlocked={displayAchievements.unlocked}
              total={displayAchievements.total}
            />
          </PanelSectionRow>
        </PanelSection>
      )}

      {/* Collapsible Filters and Sort */}
      {hasAchievementsToShow && (
        <PanelSection>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={() => setFilters(prev => ({ ...prev, expanded: !prev.expanded }))}
            >
              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                fontSize: "14px",
                width: "100%"
              }}>
                <span style={{ fontWeight: "500" }}>
                  Filters & Sort
                </span>
                {filters.expanded ? <FaChevronUp size={12} /> : <FaChevronDown size={12} />}
              </div>
            </ButtonItem>
          </PanelSectionRow>

          {filters.expanded && (
            <>
              <PanelSectionRow>
                <ButtonItem
                  layout="below"
                  onClick={cycleSortOption}
                >
                  <div style={{ fontSize: "14px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span>Sort: {getSortDisplayName(filters.sortBy, filters.sortOrder)}</span>
                    <span style={{ fontSize: "12px", opacity: 0.6 }}>→</span>
                  </div>
                </ButtonItem>
              </PanelSectionRow>

          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={cycleFilterRarity}
            >
              <div style={{ fontSize: "14px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span>Rarity: {getRarityDisplayName(filters.rarity)}</span>
                <span style={{ fontSize: "12px", opacity: 0.6 }}>→</span>
              </div>
            </ButtonItem>
          </PanelSectionRow>

          <PanelSectionRow>
            <ToggleField
              label="Show hidden achievements"
              checked={filters.showHidden}
              onChange={(value) => setFilters(prev => ({ ...prev, showHidden: value }))}
            />
          </PanelSectionRow>

          <PanelSectionRow>
            <ToggleField
              label="Unlocked only"
              checked={filters.showUnlockedOnly}
              onChange={(value) => setFilters(prev => ({ 
                ...prev, 
                showUnlockedOnly: value,
                showLockedOnly: value ? false : prev.showLockedOnly
              }))}
            />
          </PanelSectionRow>

          <PanelSectionRow>
            <ToggleField
              label="Locked only"
              checked={filters.showLockedOnly}
              onChange={(value) => setFilters(prev => ({ 
                ...prev, 
                showLockedOnly: value,
                showUnlockedOnly: value ? false : prev.showUnlockedOnly
              }))}
            />
          </PanelSectionRow>

          <PanelSectionRow>
            <div style={{ 
              textAlign: "center", 
              padding: "8px", 
              fontSize: "12px", 
              opacity: 0.7,
              borderRadius: "4px",
              backgroundColor: "rgba(255,255,255,0.05)"
            }}>
              {isLoading ? (
                <span>🔄 Loading achievements...</span>
              ) : (
                <span>🎯 Auto-refreshes when game changes</span>
              )}
            </div>
          </PanelSectionRow>

          {/* Achievement Notifications Toggle - only show if SteamClient available */}
          {steamClientAvailable && viewMode === "current" && (
            <PanelSectionRow>
              <ToggleField
                label="Achievement notifications"
                description="Get notified when achievements are unlocked"
                checked={achievementNotifications}
                onChange={setAchievementNotifications}
              />
            </PanelSectionRow>
          )}
            </>
          )}
        </PanelSection>
      )}

      {/* Achievement List */}
      {hasAchievementsToShow && (
        <PanelSection title="Achievements">
          <div>
            <AchievementList
              achievements={displayAchievements.achievements}
              sortBy={filters.sortBy}
              sortOrder={filters.sortOrder}
              showHidden={filters.showHidden}
              filterRarity={filters.rarity}
              showUnlockedOnly={filters.showUnlockedOnly}
              showLockedOnly={filters.showLockedOnly}
              isLoading={isLoading}
              gameName={displayAchievements === achievements ? currentGame?.name : trackedGame?.name}
            />
          </div>
        </PanelSection>
      )}

      {/* Error message */}
      {displayAchievements?.error && (
        <PanelSection>
          <PanelSectionRow>
            <div style={{ color: "#ff6b6b", fontSize: "14px", padding: "8px" }}>
              {displayAchievements.error}
            </div>
          </PanelSectionRow>
        </PanelSection>
      )}

      {/* Loading indicator */}
      {isLoading && loadingMessage && loadingMessage.trim() && (
        <PanelSection>
          <PanelSectionRow>
            <LoadingSpinner message={loadingMessage} size="small" />
          </PanelSectionRow>
        </PanelSection>
      )}

    </div>
  );
};