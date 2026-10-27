// components/modals/TroubleshootingModal.tsx
import { VFC, useState, useEffect } from "react";
import {
  ConfirmModal,
  PanelSection,
  PanelSectionRow,
  ButtonItem,
} from "@decky/ui";
import { toaster } from "@decky/api";
import { hybridAPI } from "../../services/hybridApi";
import { UseSettingsReturn } from "../../hooks/useSettings";
import { FaBug, FaCheck, FaExclamationTriangle, FaInfoCircle, FaKey, FaSync, FaTimes, FaTrash, FaWifi } from "../../utils/icons";

interface TroubleshootingModalProps {
  settings: UseSettingsReturn;
  onFullRefresh?: () => Promise<void>;
  closeModal?: () => void;
}

interface DiagnosticResult {
  name: string;
  status: "pass" | "fail" | "warning" | "checking";
  message: string;
  icon: any;
}

export const TroubleshootingModal: VFC<TroubleshootingModalProps> = ({
  settings,
  onFullRefresh,
  closeModal
}) => {
  const [diagnostics, setDiagnostics] = useState<DiagnosticResult[]>([]);
  const [isRunningDiagnostics, setIsRunningDiagnostics] = useState(false);

  const runDiagnostics = async () => {
    setIsRunningDiagnostics(true);
    const results: DiagnosticResult[] = [];

    // API Key Check
    results.push({
      name: "Steam API Key",
      status: settings.apiKeySet ? "pass" : "fail",
      message: settings.apiKeySet ? "API key configured" : "API key not set - some features unavailable",
      icon: FaKey
    });

    // User ID Check
    results.push({
      name: "Steam User ID",
      status: settings.steamUserId ? "pass" : "warning",
      message: settings.steamUserId ? `User ID: ${settings.steamUserId}` : "User ID not detected",
      icon: FaInfoCircle
    });


    // API Connectivity (if API key is set)
    if (settings.apiKeySet) {
      results.push({
        name: "Steam API Connection",
        status: "checking",
        message: "Testing API connection...",
        icon: FaWifi
      });

      try {
        // Test with a simple API call
        await hybridAPI.getCurrentGame();
        results[results.length - 1] = {
          name: "Steam API Connection",
          status: "pass",
          message: "API responding normally",
          icon: FaWifi
        };
      } catch (error) {
        results[results.length - 1] = {
          name: "Steam API Connection",
          status: "fail",
          message: "API connection failed - check your API key",
          icon: FaWifi
        };
      }
    }

    setDiagnostics(results);
    setIsRunningDiagnostics(false);
  };

  useEffect(() => {
    runDiagnostics();
  }, []);

  const handleReloadSettings = async () => {
    try {
      await settings.handleReloadSettings();
      toaster.toast({
        title: "✅ Settings Reloaded",
        body: "Configuration refreshed successfully"
      });
      // Re-run diagnostics after reload
      setTimeout(runDiagnostics, 500);
    } catch (error) {
      toaster.toast({
        title: "❌ Reload Failed",
        body: "Could not reload settings",
        critical: true
      });
    }
  };

  const handleClearCache = async () => {
    try {
      await hybridAPI.refreshCache();
      toaster.toast({
        title: "✅ Cache Refreshed",
        body: "Backend cache has been refreshed."
      });
      setTimeout(runDiagnostics, 500);
    } catch (error) {
      toaster.toast({
        title: "❌ Cache Error",
        body: "Couldn't refresh cache. Try 'Reset Everything' instead.",
        critical: true
      });
    }
  };

  const handleForceRefreshAll = async () => {
    try {
      toaster.toast({
        title: "🔄 Resetting...",
        body: "Clearing all data and reloading. This may take a moment."
      });

      await hybridAPI.refreshCache();
      
      if (onFullRefresh) {
        await onFullRefresh();
      }
      
      toaster.toast({
        title: "✅ Reset Complete",
        body: "Everything cleared and reloaded fresh!"
      });

      setTimeout(runDiagnostics, 1000);
    } catch (error) {
      toaster.toast({
        title: "❌ Reset Failed", 
        body: "Something went wrong. Try restarting the plugin.",
        critical: true
      });
    }
  };

  const getStatusColor = (status: DiagnosticResult['status']) => {
    switch (status) {
      case "pass": return "#4CAF50";
      case "fail": return "#F44336";
      case "warning": return "#FF9500";
      case "checking": return "#2196F3";
      default: return "#666";
    }
  };

  const getStatusIcon = (result: DiagnosticResult) => {
    switch (result.status) {
      case "pass": return <FaCheck style={{ color: "#4CAF50" }} />;
      case "fail": return <FaTimes style={{ color: "#F44336" }} />;
      case "warning": return <FaExclamationTriangle style={{ color: "#FF9500" }} />;
      case "checking": return <FaSync style={{ color: "#2196F3" }} className="spin" />;
      default: return <result.icon />;
    }
  };

  return (
    <ConfirmModal
      strTitle="🔧 Troubleshooting"
      strDescription="Diagnostic tools and common fixes"
      onCancel={() => closeModal?.()}
      onOK={() => closeModal?.()}
      strOKButtonText="Close"
      bHideCloseIcon={false}
    >
      <div style={{ padding: "0", margin: "0" }}>
        {/* System Diagnostics */}
        <PanelSection title="System Diagnostics">
          <PanelSectionRow>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
              <span style={{ fontSize: "12px", opacity: 0.8 }}>
                System health check
              </span>
              <ButtonItem
                layout="inline"
                onClick={runDiagnostics}
                disabled={isRunningDiagnostics}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px" }}>
                  <FaSync style={{ fontSize: "10px" }} />
                  {isRunningDiagnostics ? "Checking..." : "Refresh"}
                </div>
              </ButtonItem>
            </div>
          </PanelSectionRow>

          {diagnostics.map((result, index) => (
            <PanelSectionRow key={index}>
              <div style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 12px",
                backgroundColor: `${getStatusColor(result.status)}15`,
                borderRadius: "6px",
                border: `1px solid ${getStatusColor(result.status)}40`
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  {getStatusIcon(result)}
                  <div>
                    <div style={{ fontSize: "12px", fontWeight: "bold" }}>
                      {result.name}
                    </div>
                    <div style={{ fontSize: "10px", opacity: 0.7 }}>
                      {result.message}
                    </div>
                  </div>
                </div>
              </div>
            </PanelSectionRow>
          ))}
        </PanelSection>

        {/* Common Solutions */}
        <PanelSection title="Common Solutions">
          <PanelSectionRow>
            <div style={{ fontSize: "12px", opacity: 0.8, marginBottom: "12px" }}>
              Try these solutions in order based on your issue:
            </div>
          </PanelSectionRow>

          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={handleReloadSettings}
            >
              <div style={{
                display: "flex",
                textAlign: "left",
                gap: "12px",
                padding: "6px 0"
              }}>
                <FaSync style={{ 
                  fontSize: "18px", 
                  color: "#4a9eff", 
                  width: "18px", 
                  textAlign: "center", 
                  display: "inline-block",
                  marginTop: "2px"
                }} />
                <div>
                  <div style={{ fontSize: "14px", fontWeight: "bold" }}>
                    Step 1: Reload Settings
                  </div>
                  <div style={{ fontSize: "11px", opacity: 0.7, marginTop: "2px" }}>
                    Settings or API key changes not working
                  </div>
                </div>
              </div>
            </ButtonItem>
          </PanelSectionRow>

          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={handleClearCache}
            >
              <div style={{
                display: "flex",
                textAlign: "left",
                gap: "12px",
                padding: "6px 0"
              }}>
                <FaTrash style={{ 
                  fontSize: "18px", 
                  color: "#ff9500", 
                  width: "18px", 
                  textAlign: "center", 
                  display: "inline-block",
                  marginTop: "2px"
                }} />
                <div>
                  <div style={{ fontSize: "14px", fontWeight: "bold" }}>
                    Step 2: Refresh Data
                  </div>
                  <div style={{ fontSize: "11px", opacity: 0.7, marginTop: "2px" }}>
                    Stale data or incorrect percentages
                  </div>
                </div>
              </div>
            </ButtonItem>
          </PanelSectionRow>

          <PanelSectionRow>
            <ButtonItem
              layout="below"
              onClick={handleForceRefreshAll}
            >
              <div style={{
                display: "flex",
                textAlign: "left",
                gap: "12px",
                padding: "6px 0"
              }}>
                <FaBug style={{ 
                  fontSize: "18px", 
                  color: "#ff4757", 
                  width: "18px", 
                  textAlign: "center", 
                  display: "inline-block",
                  marginTop: "2px"
                }} />
                <div>
                  <div style={{ fontSize: "14px", fontWeight: "bold" }}>
                    Step 3: Reset Everything
                  </div>
                  <div style={{ fontSize: "11px", opacity: 0.7, marginTop: "2px" }}>
                    Corrupted data or empty tabs (last resort)
                  </div>
                </div>
              </div>
            </ButtonItem>
          </PanelSectionRow>
        </PanelSection>

        {/* Help Note */}
        <PanelSection title="">
          <PanelSectionRow>
            <div style={{ 
              fontSize: "10px", 
              opacity: 0.6, 
              backgroundColor: "rgba(74, 158, 255, 0.1)", 
              padding: "10px", 
              borderRadius: "6px",
              border: "1px solid rgba(74, 158, 255, 0.3)",
              textAlign: "center"
            }}>
              <FaInfoCircle style={{ marginRight: "6px" }} />
              <strong>Still having issues?</strong><br/>
              Check diagnostics above for specific problems, or restart the plugin completely.
            </div>
          </PanelSectionRow>
        </PanelSection>
      </div>

      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
      `}</style>
    </ConfirmModal>
  );
};