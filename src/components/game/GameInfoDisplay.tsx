// components/game/GameInfoDisplay.tsx
import { VFC } from "react";
import { GameInfo } from "../../models";
import { formatPlaytime } from "../../services/formatters";

interface GameInfoDisplayProps {
  game: GameInfo;
  displayName: string;
}

export const GameInfoDisplay: VFC<GameInfoDisplayProps> = ({
  game,
  displayName
}) => {
  return (
    <div style={{
      position: "relative",
      padding: "12px 16px",
      paddingRight: "16px",
      height: "80px",
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      color: "white"
    }}>
      <h3 style={{
        margin: "0 0 4px 0",
        fontSize: "16px",
        fontWeight: "bold",
        textShadow: "1px 1px 2px rgba(0,0,0,0.7)"
      }}>
        {displayName}
      </h3>

      <div style={{ fontSize: "12px", opacity: 0.9, textShadow: "1px 1px 1px rgba(0,0,0,0.5)" }}>
        {/* Achievement count */}
        {((game.total_achievements && game.total_achievements > 0) || game.has_achievements) && (
          <div>{game.total_achievements || 0} achievements available</div>
        )}
        
        {/* Playtime */}
        {game.playtime_forever !== undefined && game.playtime_forever >= 0 && (
          <div>Playtime: {formatPlaytime(game.playtime_forever)}</div>
        )}
      </div>
    </div>
  );
};