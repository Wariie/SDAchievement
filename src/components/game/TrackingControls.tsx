// components/game/TrackingControls.tsx
import { VFC } from "react";
import { PanelSection, PanelSectionRow, ButtonItem } from "@decky/ui";
import { FaEye, FaTimes, FaPlus } from "../../utils/icons";
import { GameInfo, TrackedGame } from "../../models";
import { logger } from "../../utils/logger";

interface TrackingControlsProps {
  game: GameInfo | null;
  trackedGame?: TrackedGame | null;
  viewMode: "current" | "tracked";
  onSetTracked?: (game: TrackedGame) => Promise<void>;
  onClearTracked?: () => Promise<void>;
  onSelectTracked?: () => void;
}

export const TrackingControls: VFC<TrackingControlsProps> = ({
  game,
  trackedGame,
  viewMode,
  onSetTracked,
  onClearTracked,
  onSelectTracked
}) => {
  // No controls if missing required props
  if (!onSetTracked || !onClearTracked || !onSelectTracked) return null;

  // No game - show select option
  if (!game) {
    return (
      <PanelSection>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onSelectTracked}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <FaEye style={{ fontSize: "14px" }} />
              {viewMode === "current" ? "Track a Game" : "Select Game to Track"}
            </div>
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  return (
    <PanelSection>
      {/* Current game - offer to track */}
      {viewMode === "current" && !trackedGame && (
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            onClick={() => onSetTracked({ app_id: game.app_id, name: game.name })}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px" }}>
              <FaPlus style={{ fontSize: "12px" }} />
              Track This Game
            </div>
          </ButtonItem>
        </PanelSectionRow>
      )}

      {/* Tracked game - offer to change/clear */}
      {viewMode === "tracked" && trackedGame && (
        <>
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={onSelectTracked}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px" }}>
                <FaEye style={{ fontSize: "12px" }} />
                Change Tracked Game
              </div>
            </ButtonItem>
          </PanelSectionRow>
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={async () => {
                try {
                  await onClearTracked();
                } catch (error) {
                  logger.error("TrackingControls: Clear tracked game failed:", error);
                }
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px" }}>
                <FaTimes style={{ fontSize: "12px" }} />
                Clear Tracked Game
              </div>
            </ButtonItem>
          </PanelSectionRow>
        </>
      )}
    </PanelSection>
  );
};