// components/achievements/RecentAchievementItem.tsx
import { VFC, memo } from "react";
import { PanelSectionRow, showModal, ButtonItem } from "@decky/ui";
import { RecentAchievement } from "../../models";
import { formatTime, getRarityInfo, convertRecentToAchievement } from "../../services/formatters";
import { AchievementDetailsModal } from "./AchievementDetailsModal";

interface RecentAchievementItemProps {
  achievement: RecentAchievement;
}

export const RecentAchievementItem: VFC<RecentAchievementItemProps> = memo(({ achievement }) => {
  const handleClick = () => {
    showModal(<AchievementDetailsModal 
      achievement={convertRecentToAchievement(achievement)} 
      gameName={achievement.game_name}
    />);
  };

  const rarity = getRarityInfo(achievement.global_percent);

  return (
    <PanelSectionRow>
      <ButtonItem 
        layout="below" 
        onClick={handleClick}
      >
        <div style={{ 
          display: "flex", 
          alignItems: "flex-start", 
          justifyContent: "flex-start",
          gap: "12px", 
          padding: "8px 4px",
          width: "100%",
          textAlign: "left"
        }}>
        {/* Achievement Icon */}
        <div style={{ flexShrink: 0, marginTop: "2px" }}>
          {achievement.icon ? (
            <img
              src={achievement.icon}
              alt={achievement.achievement_name}
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "4px",
                objectFit: "cover"
              }}
              onError={(e) => {
                e.currentTarget.style.display = "none";
              }}
            />
          ) : (
            <div style={{
              width: "48px",
              height: "48px",
              backgroundColor: "#333",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "20px"
            }}>
              🏆
            </div>
          )}
        </div>

        {/* Achievement Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: "14px",
            fontWeight: "bold",
            overflow: "hidden",
            textOverflow: "ellipsis",
            display: "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            lineHeight: "1.3",
            marginBottom: "2px"
          }}>
            {achievement.achievement_name}
          </div>
          
          <div style={{
            fontSize: "12px",
            opacity: 0.8,
            overflow: "hidden",
            textOverflow: "ellipsis",
            display: "-webkit-box",
            WebkitLineClamp: 1,
            WebkitBoxOrient: "vertical",
            lineHeight: "1.3",
            marginBottom: "4px"
          }}>
            {achievement.game_name}
          </div>

          <div style={{
            fontSize: "11px",
            opacity: 0.6,
            display: "flex",
            alignItems: "center",
            gap: "8px",
            lineHeight: "1.3"
          }}>
            <span style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap"
            }}>
              {formatTime(achievement.unlock_time)}
            </span>
            <span style={{ 
              color: rarity.color,
              flexShrink: 0
            }}>
              {achievement.global_percent ? `${achievement.global_percent.toFixed(1)}%` : rarity.text}
            </span>
          </div>
        </div>
        </div>
      </ButtonItem>
    </PanelSectionRow>
  );
});