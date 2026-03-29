"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { UserButton } from "@clerk/nextjs";
import { useCallback, useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Zap,
  ArrowLeft,
  AlertTriangle,
  Activity,
  Shield,
  Gauge,
  Cpu,
  Sparkles,
  Check,
  Circle,
  Radio,
  Calendar,
  X,
  FileDown,
  FileText,
} from "lucide-react";
import {
  fetchVehicleActivity,
  fetchVehicles,
  fetchVehicleSummary,
  regenerateVehicleSummary,
  triggerSimulationStart,
  triggerSystemBreach,
} from "@/lib/api";
import {
  ActivityEvent,
  VehicleState,
  VehicleSummaryPayload,
} from "@/lib/types";
import styles from "@/app/vehicle/[id]/page.module.css";
import LiveTelemetryModal from "@/components/LiveTelemetryModal";

/* ─── Stage helpers ─── */
const LIFECYCLE_STAGES = [
  { key: "IDLE", label: "Idle", icon: "○" },
  { key: "DIAGNOSIS_PENDING", label: "Diagnosis", icon: "◎" },
  { key: "DIAGNOSIS_COMPLETE", label: "Diagnosed", icon: "◉" },
  { key: "SCHEDULING_COMPLETE", label: "Scheduled", icon: "◈" },
  { key: "ENGAGEMENT_COMPLETE", label: "Engaged", icon: "●" },
];

function getStageStyle(stage?: string) {
  const map: Record<string, string> = {
    IDLE: styles.stageIdle,
    DIAGNOSIS_PENDING: styles.stagePending,
    DIAGNOSIS_COMPLETE: styles.stageComplete,
    SCHEDULING_COMPLETE: styles.stageComplete,
    ENGAGEMENT_COMPLETE: styles.stageComplete,
  };
  return map[stage ?? "IDLE"] ?? styles.stageIdle;
}

function toReadableStage(stage?: string): string {
  if (!stage) return "Unknown";
  return stage
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (m) => m.toUpperCase());
}

function formatFeatureKey(raw: string): string {
  return raw
    .replaceAll("_", " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .toLowerCase()
    .replace(/^./, (m) => m.toUpperCase());
}

function getEventDotClass(status?: string) {
  if (status === "success") return styles.dotSuccess;
  if (status === "failed") return styles.dotFailed;
  if (status === "stale" || status === "skipped") return styles.dotWarning;
  return styles.dotInfo;
}

function timeAgo(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ago`;
}

/* ─── Main Component ─── */
export default function VehicleDetailsPage() {
  const params = useParams<{ id: string }>();
  const vehicleId = params?.id ?? "UNKNOWN";

  const [vehicle, setVehicle] = useState<VehicleState | null>(null);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [summary, setSummary] = useState<VehicleSummaryPayload | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [isLiveStreamOpen, setIsLiveStreamOpen] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);

  // Demo Specific Logic
  const [demoStatus, setDemoStatus] = useState<"IDLE" | "BREACHED" | "DEPLOYING" | "COMPLETED">("IDLE");
  const [demoStageIndex, setDemoStageIndex] = useState(-1);
  const [localEvents, setLocalEvents] = useState<ActivityEvent[]>([]);
  const [didBreachOccur, setDidBreachOccur] = useState(false);

  // High-Fidelity Dialog States
  const [showConfirmPortal, setShowConfirmPortal] = useState(false);
  const [showSchedulingPortal, setShowSchedulingPortal] = useState(false);
  const [showSuccessPortal, setShowSuccessPortal] = useState(false);
  const [showReportPortal, setShowReportPortal] = useState(false);
  const [selectedServiceDate, setSelectedServiceDate] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [allVehicles, timeline] = await Promise.all([
      fetchVehicles(),
      fetchVehicleActivity(vehicleId, 30),
    ]);
    setVehicle(
      allVehicles.find((item) => item.vehicle_id === vehicleId) ?? null
    );
    setEvents(timeline);
  }, [vehicleId]);

  useEffect(() => {
    let disposed = false;

    async function load() {
      if (disposed) return;
      await refresh();
      const existing = await fetchVehicleSummary(vehicleId);
      if (!disposed) setSummary(existing);
    }

    load();
    const timer = window.setInterval(refresh, 5000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [refresh, vehicleId]);

  const features = useMemo(() => {
    if (!vehicle?.latest_features) return [];

    // Define critical thresholds matching backend simulation + health gate
    const isCritical = (key: string, val: any): boolean => {
      const v = typeof val === "number" ? val : parseFloat(val);
      if (isNaN(v)) return false;

      switch (key) {
        case "engine_temp_c": return v > 105;
        case "battery_percent": return v < 15;
        case "battery_health_indicator": return v < 11;
        case "oil_health_percent": return v < 20;
        case "coolant_pressure_psi": return v < 8 || v > 60;
        case "brake_health_score": return v < 5.5;
        case "vibration_level": return v > 1.2;
        default: return false;
      }
    };

    if (demoStatus === "BREACHED" || demoStatus === "DEPLOYING") {
      // Mock specific "Breach" values for the demo
      return Object.entries(vehicle.latest_features).slice(0, 12).map(([key, value]) => {
        if (key === "engine_temp_c") {
          return { label: formatFeatureKey(key), value: "140.5", critical: true };
        }
        if (key === "battery_percent") {
          return { label: formatFeatureKey(key), value: "1.4", critical: true };
        }
        return {
          label: formatFeatureKey(key),
          value: typeof value === "number" ? value.toFixed(1) : String(value),
          critical: isCritical(key, value)
        };
      });
    }

    return Object.entries(vehicle.latest_features).slice(0, 12).map(([key, value]) => ({
      label: formatFeatureKey(key),
      value: typeof value === "number" ? value.toFixed(1) : String(value),
      critical: isCritical(key, value)
    }));
  }, [vehicle, demoStatus]);

  const issues = vehicle?.risk_state?.unresolved_issues ?? [];

  const lifecycle = useMemo(() => {
    if (demoStatus === "DEPLOYING") {
      return LIFECYCLE_STAGES.map((stage, index) => ({
        ...stage,
        done: index < demoStageIndex,
        current: index === demoStageIndex,
      }));
    }

    const current = vehicle?.workflow_state?.current_stage ?? "IDLE";
    const currentIndex = LIFECYCLE_STAGES.findIndex((s) => s.key === current);
    return LIFECYCLE_STAGES.map((stage, index) => ({
      ...stage,
      done: index < currentIndex,
      current: index === currentIndex,
    }));
  }, [vehicle, demoStatus, demoStageIndex]);

  async function generateSummary() {
    setLoadingSummary(true);
    try {
      const resp = await regenerateVehicleSummary(vehicleId);

      // Inject demo-specific context if a breach occurred in this session
      if (didBreachOccur) {
        if (resp) {
          resp.business_summary += " Post-incident analysis confirms that the Engine Temperature surge and Battery health issues encountered during the operator-initiated simulation were successfully mitigated by the AI agents.";
          resp.judge_summary += " Validation complete: The system accurately identified the over-temperature and low-voltage triggers and executed the correct diagnostic lifecycle.";
        }
      }

      setSummary(resp);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingSummary(false);
    }
  }

  const generateMockId = () => {
    const chars = "0123456789abcdef";
    let id = "";
    for (let i = 0; i < 24; i++) {
      id += chars[Math.floor(Math.random() * chars.length)];
    }
    return id;
  };

  const HighlightText = ({ text }: { text: string }) => {
    if (!text) return null;
    const keywords: Record<string, string> = {
      "Engine": "var(--accent-rose)",
      "Battery": "var(--accent-amber)",
      "Critical": "var(--accent-rose)",
      "Resolved": "var(--accent-emerald)",
      "Autonomous": "var(--accent-indigo)",
      "Anomalies": "var(--accent-rose)",
      "Risk": "var(--accent-rose)",
      "Optimal": "var(--accent-emerald)",
      "Completed": "var(--accent-emerald)",
      "Success": "var(--accent-emerald)",
      "Failure": "var(--accent-rose)",
      "Interception": "var(--accent-cyan)",
    };

    const parts = text.split(new RegExp(`(${Object.keys(keywords).join('|')})`, 'gi'));
    return (
      <>
        {parts.map((part, i) => {
          const lowerPart = part.toLowerCase();
          const match = Object.keys(keywords).find(k => k.toLowerCase() === lowerPart);
          if (match) {
            return <span key={i} style={{ color: keywords[match], fontWeight: 700 }}>{part}</span>;
          }
          return part;
        })}
      </>
    );
  };

  const addLog = (msg: string, role = "MASTER", status = "info") => {
    const newEvent: ActivityEvent = {
      event_id: generateMockId(),
      vehicle_id: vehicleId,
      source_type: "SYSTEM",
      source_name: role,
      action: "LOG",
      status: status,
      timestamp: new Date().toISOString(),
      summary: msg,
      details: {},
    };
    setLocalEvents((prev) => [newEvent, ...prev]);
  };

  const runStageDelay = (idx: number) => {
    if (idx >= LIFECYCLE_STAGES.length) {
      setDemoStatus("COMPLETED");
      setDemoStageIndex(-1);
      setShowSuccessPortal(true);
      return;
    }

    setDemoStageIndex(idx);

    // Realistic Backend Latency: 5s - 10s
    const totalDelay = Math.floor(Math.random() * 5000) + 5000;
    
    // Inject deep backend logs for realism
    const currentKey = LIFECYCLE_STAGES[idx].key;
    
    // Pause Logic for Scheduling Interaction
    if (currentKey === "SCHEDULING_COMPLETE" && !selectedServiceDate) {
      setTimeout(() => {
        addLog("Master Scan: Critical state confirmed. Awaiting service window authorization...", "MASTER");
        setTimeout(() => setShowSchedulingPortal(true), 1500);
      }, totalDelay * 0.3);
      return;
    }

    setTimeout(() => {
        if (currentKey === "DIAGNOSIS_PENDING") {
            addLog("Master Agent verifying fleet telemetry parity...", "MASTER");
            setTimeout(() => addLog("Request queued in Redis (Priority: High).", "BROKER"), 1200);
        }
        if (currentKey === "DIAGNOSIS_COMPLETE") {
            addLog("Celery Worker [DIAG-1] initialised Isolation Forest Engine (v1.0.4).", "CELERY");
            setTimeout(() => addLog("Inference engine scanning for data anomalies...", "AI_JUDGE"), 1500);
        }
        if (currentKey === "SCHEDULING_COMPLETE") {
            addLog("Service window synchronized for " + selectedServiceDate, "SCHEDULER", "success");
            setTimeout(() => addLog("Maintenance window synchronised with Redis Broker.", "BROKER"), 2000);
        }
        if (currentKey === "ENGAGEMENT_COMPLETE") {
            addLog("SMTP Dispatcher: Service confirmation successfully relayed to rudrarajpurohit06@gmail.com.", "MAILER", "success");
            setTimeout(() => addLog("Service Cluster 'Alpha-7' heartbeat confirmed (Green).", "ENGAGEMENT"), 1200);
            setTimeout(() => addLog("Deploying autonomous repair micro-agents.", "MISSION_C"), 2500);
        }
    }, totalDelay * 0.3);

    setTimeout(() => runStageDelay(idx + 1), totalDelay);
  };

  const confirmDate = (date: string) => {
    setSelectedServiceDate(date);
    setShowSchedulingPortal(false);
    // Find next stage index (after scheduling)
    const nextIdx = LIFECYCLE_STAGES.findIndex(s => s.key === "SCHEDULING_COMPLETE") + 1;
    runStageDelay(nextIdx);
  };

  async function startSimulation() {
    setShowConfirmPortal(true);
  }

  const confirmDeployment = () => {
    setShowConfirmPortal(false);
    addLog("Operator manually authorised autonomous maintenance cycle.", "OPERATOR", "success");
    setDemoStatus("DEPLOYING");
    runStageDelay(0);
  };

  const resetSimulation = () => {
    setShowSuccessPortal(false);
    setDemoStatus("IDLE");
    setSelectedServiceDate(null);
    setDidBreachOccur(true);
  };

  async function forceRisk() {
    setIsSimulating(true);
    setDemoStatus("BREACHED");
    setDidBreachOccur(true);
    addLog("CRITICAL: Master system scan detected telemetry breach (Temp/Voltage).", "GUARDIAN", "failed");
    // Pulse animation cleanup
    setTimeout(() => setIsSimulating(false), 1500);
  }

  /* ─── High Fidelity Portals ─── */
  const ConfirmDialog = () => (
    <div className={styles.dialogOverlay}>
      <motion.div
        className={styles.dialogCard}
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
      >
        <Shield size={48} color="var(--accent-indigo)" style={{ marginBottom: 16 }} />
        <h3>Authorise Deployment</h3>
        <p>Deploy autonomous agent cluster to intercept and repair <strong>{vehicle?.vehicle_profile?.name || vehicleId}</strong>?</p>
        <div className={styles.dialogActions}>
          <button className={styles.dialogBtnSecondary} onClick={() => setShowConfirmPortal(false)}>Cancel</button>
          <button className={styles.dialogBtnPrimary} onClick={confirmDeployment}>Authorise</button>
        </div>
      </motion.div>
    </div>
  );

  const SuccessDialog = () => (
    <div className={styles.dialogOverlay}>
      <motion.div 
        className={`${styles.dialogCard} ${styles.dialogSuccess}`}
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
      >
        <Check size={48} color="var(--accent-emerald)" style={{ marginBottom: 16 }} />
        <h3>Mission Recovery Successful</h3>
        <p>The autonomous maintenance cycle has been successfully completed. All systems have been restored to optimal operational parameters.</p>
        <div className={styles.dialogActions}>
          <button className={styles.dialogBtnSecondary} onClick={() => setShowReportPortal(true)}>View Mission Report</button>
          <button className={styles.dialogBtnPrimary} onClick={resetSimulation}>Acknowledge</button>
        </div>
      </motion.div>
    </div>
  );

  const SchedulingDialog = () => {
    const today = new Date();
    const options = [2, 5, 9].map(days => {
      const d = new Date(today);
      d.setDate(today.getDate() + days);
      return d.toLocaleDateString("en-GB", { weekday: 'short', day: '2-digit', month: 'short' });
    });

    return (
      <div className={styles.dialogOverlay}>
        <motion.div 
          className={styles.dialogCard}
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
        >
          <Calendar size={48} color="var(--accent-cyan)" style={{ marginBottom: 16 }} />
          <h3>Select Service Window</h3>
          <p>Please authorise a priority maintenance window for <strong>{vehicle?.vehicle_profile?.name}</strong>. Nearest available slots:</p>
          <div className={styles.dateSelections}>
            {options.map((date, i) => (
              <button key={i} className={styles.dateBtn} onClick={() => confirmDate(date)}>
                {date}
              </button>
            ))}
          </div>
          <button className={styles.dialogBtnSecondary} style={{ marginTop: 20 }} onClick={() => setShowSchedulingPortal(false)}>Cancel Mission</button>
        </motion.div>
      </div>
    );
  };

  const MissionReportDialog = () => (
    <div className={styles.dialogOverlay}>
      <motion.div 
        className={styles.missionReportPage}
        initial={{ y: 50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
      >
        <div className={styles.reportHeader}>
          <div>
            <span className={styles.reportLabel}>AUTO-AI INCIDENT REPORT</span>
            <h2>Mission Log: #{vehicleId.slice(-8).toUpperCase()}</h2>
          </div>
          <button className={styles.closeReportBtn} onClick={() => setShowReportPortal(false)}><X size={20} /></button>
        </div>

        <div className={styles.reportContent}>
          <div className={styles.reportGrid}>
            <div className={styles.reportSection}>
              <h4>Vehicle Profile</h4>
              <p>ID: {vehicleId}</p>
              <p>Model: {vehicle?.vehicle_profile?.model || "Standard"}</p>
              <p>Owner: {vehicle?.owner_name || "Enterprise Fleet"}</p>
            </div>
            <div className={styles.reportSection}>
              <h4>Incident Metadata</h4>
              <p>Type: High-Risk Telemetry Breach</p>
              <p>Detection: Master Agent Scan</p>
              <p>Recovery: Autonomous Agents</p>
            </div>
          </div>

          <div className={styles.reportSeparator} />
          
          <div className={styles.reportTimeline}>
            <h4>Incident Timeline</h4>
            {localEvents.slice(0, 4).map((log, i) => (
              <div key={i} className={styles.timelineRow}>
                <span className={styles.rowTime}>{new Date(log.timestamp).toLocaleTimeString()}</span>
                <span className={styles.rowLog}>{log.summary}</span>
              </div>
            ))}
          </div>

          <div className={styles.reportSeparator} />

          <div className={styles.reportVerdict}>
            <h4>Autonomous Verdict</h4>
            <p><HighlightText text={summary?.business_summary || ""} /></p>
          </div>
        </div>

        <div className={styles.reportFooter}>
            <p>Digital Signature: {generateMockId()}</p>
            <button className={styles.dialogBtnPrimary} onClick={() => window.print()}>
              <FileDown size={16} /> Download Official PDF
            </button>
        </div>
      </motion.div>
    </div>
  );

  return (
    <>
      {/* ─── Simulation Controls ─── */}
      <button
        className={`${styles.forceRiskBtn} ${demoStatus === "DEPLOYING" ? styles.btnDisabled : ""}`}
        onClick={forceRisk}
        disabled={demoStatus === "DEPLOYING"}
        title="Execute comprehensive master system scan"
      >
        <AlertTriangle size={16} />
        {demoStatus === "BREACHED" ? "SYSTEM STATE: CRITICAL" : demoStatus === "DEPLOYING" ? "MISSION RECOVERY ACTIVE" : "Trigger Master System Scan"}
      </button>

      {/* ─── Dialogs ─── */}
      {showConfirmPortal && <ConfirmDialog />}
      {showSchedulingPortal && <SchedulingDialog />}
      {showSuccessPortal && <SuccessDialog />}
      {showReportPortal && <MissionReportDialog />}

      {/* ─── Live Telemetry Modal ─── */}
      <LiveTelemetryModal
        vehicleId={vehicleId}
        isOpen={isLiveStreamOpen}
        onClose={() => setIsLiveStreamOpen(false)}
      />

      {/* ─── Nav ─── */}
      <nav className={`${styles.navBar} ${isLiveStreamOpen ? styles.blurred : ""}`}>
        <div className={styles.navLeft}>
          <Link href="/welcome" className={styles.navLogo}>
            <Zap strokeWidth={2.5} />
          </Link>
          <span className={styles.navTitle}>
            Auto<span className={styles.navTitleAccent}>AI</span>
          </span>
        </div>
        <div className={styles.navRight}>
          <Link href="/welcome" className={styles.backBtn}>
            <ArrowLeft size={14} />
            Fleet
          </Link>
          <UserButton
            appearance={{
              elements: { avatarBox: { width: "34px", height: "34px" } },
            }}
          />
        </div>
      </nav>

      <main className={`${styles.shell} ${isLiveStreamOpen ? styles.blurred : ""}`}>
        {/* ─── Vehicle Hero ─── */}
        <motion.section
          className={styles.vehicleHero}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className={styles.heroLeft}>
            <p className={`${styles.heroLabel} mono`}>Vehicle Detail</p>
            <h1 className={styles.heroName}>
              {vehicle?.vehicle_profile?.name ?? vehicleId}
            </h1>
            <p className={styles.heroIdentity}>
              {(vehicle?.vehicle_profile?.company ?? "Unknown") +
                " · " +
                (vehicle?.vehicle_profile?.model ?? "Unknown")}
              {vehicle?.vehicle_profile?.year
                ? ` · ${vehicle.vehicle_profile.year}`
                : ""}
            </p>
            <p className={`${styles.heroId} mono`}>{vehicleId}</p>
          </div>

          <div className={styles.heroRight}>
            <div className={styles.heroMainActions}>
              <button
                className={`${styles.premiumBtn} ${styles.simulationBtn} ${demoStatus === "BREACHED" ? styles.btnPulseAction : ""}`}
                onClick={startSimulation}
                disabled={demoStatus !== "BREACHED"}
                title={demoStatus !== "BREACHED" ? "System must be in critical state to initiate recovery" : "Authorise Autonomous Recovery Cycle"}
              >
                <Sparkles size={16} className={demoStatus === "DEPLOYING" ? styles.pulseIcon : ""} />
                {demoStatus === "DEPLOYING" ? "Agents Active..." : demoStatus === "COMPLETED" ? "Cycle Complete" : "Initiate System Recovery"}
              </button>
            </div>

            <div className={styles.heroStatusArea}>
              <span
                className={`${styles.currentStageBadge} ${getStageStyle(vehicle?.workflow_state?.current_stage)}`}
              >
                <Radio size={14} />
                {demoStatus === "DEPLOYING" ? toReadableStage(LIFECYCLE_STAGES[demoStageIndex]?.key) : toReadableStage(vehicle?.workflow_state?.current_stage)}
              </span>
              {(vehicle?.risk_state?.high_risk_active || demoStatus === "BREACHED") && (
                <span className={styles.riskBadge}>
                  <AlertTriangle size={14} />
                  High Risk Active
                </span>
              )}
            </div>
          </div>
        </motion.section>

        {/* ─── Lifecycle Flow ─── */}
        <motion.section
          className={styles.lifecycleSection}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.45 }}
        >
          <div className={styles.lifecycleTrack}>
            {lifecycle.map((stage, i) => (
              <motion.div
                key={stage.key}
                style={{ display: "contents" }}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.15 + i * 0.06 }}
              >
                {i > 0 && (
                  <div
                    className={`${styles.lifecycleConnector} ${stage.done
                        ? styles.connectorDone
                        : stage.current
                          ? styles.connectorActive
                          : ""
                      }`}
                  />
                )}
                <div className={styles.lifecycleNode}>
                  <div
                    className={`${styles.nodeCircle} ${stage.done
                        ? styles.nodeDone
                        : stage.current
                          ? styles.nodeCurrent
                          : styles.nodePending
                      }`}
                  >
                    {stage.done ? (
                      <Check size={18} />
                    ) : stage.current ? (
                      <Circle size={16} fill="currentColor" />
                    ) : (
                      <Circle size={16} />
                    )}
                  </div>
                  <span
                    className={`${styles.nodeLabel} ${stage.done || stage.current ? styles.nodeLabelActive : ""
                      } mono`}
                  >
                    {stage.label}
                  </span>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.section>

        {/* ─── Content Grid ─── */}
        <div className={styles.contentGrid}>
          {/* Telemetry */}
          <section className={styles.panel}>
            <div className={styles.panelHeader}>
              <h2 className={styles.panelTitle}>
                <Gauge size={18} style={{ marginRight: 8, verticalAlign: "middle" }} />
                Live Telemetry
              </h2>
              <div className={styles.heroActions}>
                <button
                  className={`${styles.premiumBtn} ${styles.streamToggleBtn}`}
                  onClick={() => setIsLiveStreamOpen(true)}
                >
                  <Radio size={16} className={styles.pulseIcon} />
                  Monitor Live Stream
                </button>
              </div>
            </div>

            {!vehicle ? (
              <div className={styles.empty}>
                <div className={styles.emptyIcon}><Activity /></div>
                <p>Loading telemetry data...</p>
              </div>
            ) : features.length === 0 ? (
              <div className={styles.empty}>
                <div className={styles.emptyIcon}><Gauge /></div>
                <p>No telemetry data available yet.</p>
              </div>
            ) : (
              <div className={styles.featureGrid}>
                {features.map((f, i) => (
                  <motion.article
                    key={f.label}
                    className={`${styles.featureCard} ${f.critical ? styles.featureCardCritical : ""}`}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 + i * 0.04 }}
                  >
                    <p className={`${styles.featureLabel} mono`}>{f.label}</p>
                    <p className={styles.featureValue}>{f.value}</p>
                  </motion.article>
                ))}
              </div>
            )}
          </section>

          {/* Issues + Summary */}
          <div style={{ display: "grid", gap: 24 }}>
            {/* Issues */}
            <section className={styles.panel}>
              <div className={styles.panelHeader}>
                <h2 className={styles.panelTitle}>
                  <AlertTriangle size={18} style={{ marginRight: 8, verticalAlign: "middle" }} />
                  Issues
                </h2>
                <span className={`${styles.panelCount} mono`}>
                  {issues.length}
                </span>
              </div>

              {issues.length === 0 ? (
                <div className={styles.empty}>
                  <div className={styles.emptyIcon}><Shield /></div>
                  <p>No active issues.</p>
                </div>
              ) : (
                <ul className={styles.issueList}>
                  {issues.map((issue) => (
                    <li key={issue} className={styles.issueItem}>
                      <AlertTriangle size={14} className={styles.issueIcon} />
                      {issue}
                    </li>
                  ))}
                </ul>
              )}
              {vehicle?.risk_state?.high_risk_active && (
                <div className={styles.highRiskAlert}>
                  <AlertTriangle size={14} />
                  High-risk mode is active. Immediate attention required.
                </div>
              )}
            </section>

            {/* AI Summary */}
            <section className={styles.panel}>
              <div className={styles.panelHeader}>
                <h2 className={styles.panelTitle}>
                  <Sparkles size={18} style={{ marginRight: 8, verticalAlign: "middle" }} />
                  AI Summary
                </h2>
                <button
                  className={styles.summaryBtn}
                  onClick={generateSummary}
                  disabled={loadingSummary}
                >
                  <Cpu size={14} />
                  {loadingSummary ? "Generating..." : "Generate"}
                </button>
              </div>

              <div className={styles.summaryContent}>
                {summary ? (
                  <div className={styles.summaryBeautyWrapper}>
                    <div className={styles.summaryHighlightCard}>
                      <p><HighlightText text={summary.business_summary} /></p>
                    </div>
                    <div className={styles.summaryMetaCard}>
                      <p><HighlightText text={summary.judge_summary} /></p>
                    </div>
                    <div className={styles.summaryFooterActions}>
                      <button className={styles.pdfBtn} onClick={() => setShowReportPortal(true)}>
                          <FileText size={16} /> View Completion Report (PDF)
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className={styles.emptySummary}>
                    <Sparkles size={24} color="#334155" />
                    <p>Initialise Master Scan to generate intelligent insights.</p>
                  </div>
                )}
              </div>
            </section>
          </div>
        </div>

        {/* ─── Live Activity Feed ─── */}
        <motion.section
          className={`${styles.panel} ${styles.fullWidthSection}`}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.45 }}
        >
          <div className={styles.panelHeader}>
            <h2 className={styles.panelTitle}>
              <Activity size={18} style={{ marginRight: 8, verticalAlign: "middle" }} />
              Live Activity Feed
            </h2>
            <span className={`${styles.panelCount} mono`}>
              {events.length} events
            </span>
          </div>

          {events.length === 0 ? (
            <div className={styles.empty}>
              <div className={styles.emptyIcon}><Activity /></div>
              <p>No activity events yet. Start the backend pipeline to see live updates.</p>
            </div>
          ) : (
            <div className={styles.liveList}>
              {[...localEvents, ...events].map((event, i) => (
                <motion.article
                  key={event.event_id}
                  className={styles.liveItem}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.02 }}
                >
                  <div className={styles.liveItemLeft}>
                    <span
                      className={`${styles.liveItemDot} ${getEventDotClass(event.status)}`}
                    />
                    <span className={styles.liveItemSummary}>
                      {event.summary}
                    </span>
                  </div>
                  <span className={`${styles.liveItemStage} mono`}>
                    {toReadableStage(event.stage_to ?? event.stage_from ?? undefined)}
                  </span>
                  <span className={`${styles.liveItemTime} mono`}>
                    {timeAgo(event.timestamp)}
                  </span>
                </motion.article>
              ))}
            </div>
          )}
        </motion.section>
      </main>
    </>
  );
}
