import { AppAchievementResponse } from "@decky/ui/dist/globals/steam-client/App";
import { CurrentUser } from "@decky/ui/dist/globals/steam-client/User";
import { Achievement, AchievementData } from "../models";
import { logger } from "./logger";

// Steam Client API utilities for direct Steam integration

export type SteamUser = Pick<CurrentUser, "strSteamID" | "strAccountName">;

export class SteamClientAPI {
  private achievementCallbacks = new Map<number, (data: any) => void>();
  private userCallbacks = new Set<(user: CurrentUser) => void>();
  private currentUser: CurrentUser | null = null;
  private registrations: Array<{ unregister?: () => void } | void> = [];

  constructor() {
    this.setupCallbacks();
  }

  private setupCallbacks() {
    if (window.SteamClient?.Apps) {
      // Register for achievement changes
      this.registrations.push(
        window.SteamClient.Apps.RegisterForAchievementChanges((data: ArrayBuffer) => {
          // Handle achievement change notifications
          this.achievementCallbacks.forEach(callback => callback(data));
        })
      );
    }

    if (window.SteamClient?.User) {
      // Register for user changes (typed as void, but Steam returns an unregisterable at runtime)
      this.registrations.push(
        window.SteamClient.User.RegisterForCurrentUserChanges((user: CurrentUser) => {
          this.currentUser = user;
          this.userCallbacks.forEach(callback => callback(user));
        }) as { unregister?: () => void } | void
      );
    }
  }

  /**
   * Unregister all SteamClient listeners (call when the plugin is unloaded)
   */
  dispose() {
    this.registrations.forEach(registration => {
      try {
        registration?.unregister?.();
      } catch (error) {
        logger.warn('Failed to unregister SteamClient listener:', error);
      }
    });
    this.registrations = [];
    this.achievementCallbacks.clear();
    this.userCallbacks.clear();
  }

  /**
   * Get current Steam user information
   */
  async getCurrentUser(timeoutMs: number = 3000): Promise<SteamUser | null> {
    try {
      // Fast path: the Steam UI already knows the logged-in user
      const appUser = window.App?.m_CurrentUser;
      if (appUser?.strSteamID) {
        return { strSteamID: appUser.strSteamID, strAccountName: appUser.strAccountName };
      }
      if (this.currentUser) return this.currentUser;
      if (!window.SteamClient?.User) return null;

      // Wait on the listener registered in setupCallbacks instead of registering a new one per call
      return await new Promise<SteamUser | null>((resolve) => {
        const onUser = (user: CurrentUser) => {
          clearTimeout(timer);
          this.userCallbacks.delete(onUser);
          resolve(user);
        };
        const timer = setTimeout(() => {
          this.userCallbacks.delete(onUser);
          resolve(null);
        }, timeoutMs);
        this.userCallbacks.add(onUser);
      });
    } catch (error) {
      logger.error('Failed to get current user:', error);
      return null;
    }
  }

  /**
   * Get achievements for a specific app
   */
  async getMyAchievementsForApp(appId: number): Promise<AchievementData | null> {
    try {
      if (!window.SteamClient?.Apps?.GetMyAchievementsForApp) return null;

      const response: AppAchievementResponse = await window.SteamClient.Apps.GetMyAchievementsForApp(appId.toString());
      
      if (response.result === 1 && response.data?.rgAchievements) { // EResult.OK = 1
        const achievements: Achievement[] = response.data.rgAchievements.map(achievement => ({
          api_name: achievement.strID,
          display_name: achievement.strName,
          description: achievement.strDescription,
          icon: achievement.strImage,
          icon_gray: achievement.strImage, // Use same icon for now
          hidden: achievement.bHidden,
          unlocked: achievement.bAchieved,
          unlock_time: achievement.rtUnlocked || null,
          global_percent: achievement.flAchieved || null
        }));

        const unlocked = achievements.filter(a => a.unlocked).length;
        const total = achievements.length;
        const percentage = total > 0 ? (unlocked / total) * 100 : 0;

        return {
          app_id: appId,
          total,
          unlocked,
          percentage: Math.round(percentage * 100) / 100,
          achievements
        };
      }
      
      // Check for specific result codes
      if (response.result === 2) { // EResult.Fail
        logger.debug(`App ${appId} returned EResult.Fail - likely no achievement registration`);
        return null;
      }
      
      return null;
    } catch (error) {
      // Check for specific error cases
      if (error && typeof error === 'object') {
        const errorObj = error as any;
        if (errorObj.result === 2 && errorObj.message?.includes('no registration for app details')) {
          logger.debug(`App ${appId} has no achievement registration, skipping`);
          return null;
        }
      }
      
      logger.error(`Failed to get achievements for app ${appId}:`, error);
      return null;
    }
  }

  /**
   * Register callback for achievement changes
   */
  onAchievementChanges(appId: number, callback: (data: any) => void): () => void {
    this.achievementCallbacks.set(appId, callback);
    
    return () => {
      this.achievementCallbacks.delete(appId);
    };
  }

  /**
   * Check if SteamClient APIs are available
   */
  isAvailable(): boolean {
    return typeof window.SteamClient !== 'undefined' && 
           window.SteamClient.Apps !== undefined &&
           window.SteamClient.User !== undefined;
  }
}

// Export singleton instance
export const steamClientAPI = new SteamClientAPI();

// Export utility functions for easy access
export const getSteamUser = () => steamClientAPI.getCurrentUser();
export const isSteamClientAvailable = () => steamClientAPI.isAvailable();