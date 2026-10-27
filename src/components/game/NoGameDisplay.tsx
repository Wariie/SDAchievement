// components/game/NoGameDisplay.tsx
import { VFC } from "react";
import { PanelSection, PanelSectionRow } from "@decky/ui";
import { FaGamepad } from "../../utils/icons";
import { TrackingControls } from "./TrackingControls";
import { TrackedGame } from "../../models";

interface NoGameDisplayProps {
  onSelectTracked?: () => void;
  onSetTrackedGame?: (game: TrackedGame) => Promise<void>;
  onClearTrackedGame?: () => Promise<void>;
  trackedGame?: TrackedGame | null;
  viewMode?: "current" | "tracked";
}

export const NoGameDisplay: VFC<NoGameDisplayProps> = ({ 
  onSelectTracked, 
  onSetTrackedGame, 
  onClearTrackedGame, 
  trackedGame, 
  viewMode = "current" 
}) => {
  return (
    <>
      <PanelSection>
        <PanelSectionRow>
          <div style={{
            textAlign: "center",
            padding: "20px",
            opacity: 0.6
          }}>
            <FaGamepad style={{ fontSize: "32px", marginBottom: "8px" }} />
            <div>No game currently running</div>
          </div>
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
            Game detection is automatic - start a game to see achievements
          </div>
        </PanelSectionRow>
      </PanelSection>

      {/* Show tracking option */}
      {onSelectTracked && onSetTrackedGame && onClearTrackedGame && (
        <TrackingControls 
          game={null}
          trackedGame={trackedGame}
          viewMode={viewMode}
          onSetTracked={onSetTrackedGame}
          onClearTracked={onClearTrackedGame}
          onSelectTracked={onSelectTracked}
        />
      )}
    </>
  );
};