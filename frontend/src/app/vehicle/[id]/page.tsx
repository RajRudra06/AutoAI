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
} from "@/lib/api";
import {
  ActivityEvent,
  VehicleState,
  VehicleSummaryPayload,
} from "@/lib/types";
import styles from "@/app/vehicle/[id]/page.module.css";
import LiveTelemetryModal from "@/components/LiveTelemetryModal";

/* ─── Global Helpers ─── */

const formatFeatureKey = (key: string) => {
  return key.split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
};

const toReadableStage = (stage?: string) => {
  if (!stage) return "IDLE";
  const cleaned = stage.replace(/_/g, " ");
  if (cleaned.includes("COMPLETE")) return cleaned.replace("COMPLETE", "SUCCESS");
  if (cleaned.includes("PENDING")) return cleaned.replace("PENDING", "ACTIVE");
  return cleaned;
};

const getStageStyle = (stage?: string) => {
  if (!stage || stage === "IDLE") return styles.stageIdle;
  if (stage.includes("COMPLETE") || stage === "SERVICE_COMPLETED") return styles.stageSuccess;
  if (stage.includes("ERROR") || stage.includes("RISK")) return styles.stageError;
  return styles.stageActive;
};

const getEventDotClass = (status?: string) => {
  if (status === "success") return styles.dotSuccess;
  if (status === "failed") return styles.dotFailed;
  if (status === "stale" || status === "skipped") return styles.dotWarning;
  return styles.dotInfo;
};

const timeAgo = (timestamp: string) => {
  const diff = Date.now() - new Date(timestamp).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ago`;
};

const LIFECYCLE_STAGES = [
  { key: "IDLE", label: "IDLE" },
  { key: "DIAGNOSIS_PENDING", label: "DIAGNOSIS" },
  { key: "DIAGNOSIS_COMPLETE", label: "ANALYSIS" },
  { key: "SCHEDULING_COMPLETE", label: "SCHEDULER" },
  { key: "ENGAGEMENT_COMPLETE", label: "ENGAGEMENT" },
  { key: "SERVICE_COMPLETED", label: "COMPLETED" },
];

/* ─── High Fidelity Portals (Decoupled) ─── */

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

const ConfirmDialog = ({ vehicleName, onCancel, onConfirm }: any) => (
  <div className={styles.dialogOverlay}>
    <motion.div
      className={styles.dialogCard}
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
    >
      <Shield size={48} color="var(--accent-indigo)" style={{ marginBottom: 16 }} />
      <h3>Authorise Deployment</h3>
      <p>Deploy autonomous agent cluster to intercept and repair <strong>{vehicleName}</strong>?</p>
      <div className={styles.dialogActions}>
        <button className={styles.dialogBtnSecondary} onClick={onCancel}>Cancel</button>
        <button className={styles.dialogBtnPrimary} onClick={onConfirm}>Authorise</button>
      </div>
    </motion.div>
  </div>
);

const SuccessDialog = ({ onReport, onAcknowledge }: any) => (
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
        <button className={styles.dialogBtnSecondary} onClick={onReport}>View Mission Report</button>
        <button className={styles.dialogBtnPrimary} onClick={onAcknowledge}>Acknowledge</button>
      </div>
    </motion.div>
  </div>
);

const SchedulingDialog = ({ vehicleName, onSelectDate, onCancel }: any) => {
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
        <p>Please authorise a priority maintenance window for <strong>{vehicleName}</strong>. Nearest available slots:</p>
        <div className={styles.dateSelections}>
          {options.map((date, i) => (
            <button key={i} className={styles.dateBtn} onClick={() => onSelectDate(date)}>
              {date}
            </button>
          ))}
        </div>
        <button className={styles.dialogBtnSecondary} style={{ marginTop: 20 }} onClick={onCancel}>Cancel Mission</button>
      </motion.div>
    </div>
  );
};

const MissionReportDialog = ({ vehicle, vehicleId, events, summary, onClose }: any) => (
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
        <button className={styles.closeReportBtn} onClick={onClose}><X size={20} /></button>
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
          {events.slice(0, 4).map((log: any, i: number) => (
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
        <p>Digital Signature: {Math.random().toString(36).substring(7).toUpperCase()}</p>
        <button className={styles.dialogBtnPrimary} onClick={() => window.print()}>
          <FileDown size={16} /> Download Official PDF
        </button>
      </div>
    </motion.div>
  </div>
);

/* ─── Main Component ─── */

export default function VehicleDetailsPage() {
  const params = useParams<{ id: string }>();
  const vehicleId = params?.id ?? "UNKNOWN";

  const [vehicle, setVehicle] = useState<VehicleState | null>(null);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [summary, setSummary] = useState<VehicleSummaryPayload | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [isLiveStreamOpen, setIsLiveStreamOpen] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);

  // Simulation State
  const [demoStatus, setDemoStatus] = useState<"IDLE" | "BREACHED" | "DEPLOYING" | "COMPLETED">("IDLE");
  const [demoStageIndex, setDemoStageIndex] = useState(0);
  const [didBreachOccur, setDidBreachOccur] = useState(false);

  // Dialog States
  const [showConfirmPortal, setShowConfirmPortal] = useState(false);
  const [showSchedulingPortal, setShowSchedulingPortal] = useState(false);
  const [showSuccessPortal, setShowSuccessPortal] = useState(false);
  const [showReportPortal, setShowReportPortal] = useState(false);
  const [selectedServiceDate, setSelectedServiceDate] = useState<string | null>(null);

  const DEFAULT_MOCK: VehicleState = {
    vehicle_id: vehicleId,
    owner_name: "Elite Logistics Corp",
    vehicle_profile: {
      name: "Triton-9 Heavy Hauler",
      model: "Autonomous Class 8",
      year: 2026,
      type: "Electric Heavy Duty"
    },
    latest_features: {
      "engine_temp_c": 92.4,
      "battery_percent": 88.5,
      "tire_pressure_psi": 34.2,
      "vibration_level": 0.04,
      "gps_signal": "98%"
    },
    workflow_state: {
      current_stage: "IDLE",
      flags: { diagnosis_required: false, scheduling_required: false, engagement_required: false }
    },
    risk_state: { high_risk_active: false, unresolved_issues: [] },
    last_updated: new Date().toISOString()
  };

  const refresh = useCallback(async () => {
    try {
      const [allVehicles, timeline] = await Promise.all([
        fetchVehicles(),
        fetchVehicleActivity(vehicleId, 30),
      ]);

      const found = allVehicles.find((v) => v.vehicle_id === vehicleId);
      if (found) {
        setVehicle(found);
      } else {
        setVehicle(DEFAULT_MOCK);
      }
      if (demoStatus === "IDLE") {
        setEvents(timeline);
      }
    } catch (error) {
      setVehicle(DEFAULT_MOCK);
    }
  }, [vehicleId, demoStatus]);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    // Reset simulation on vehicle change
    const resetSimulation = () => {
      setShowSuccessPortal(false);
      setDemoStatus("IDLE");
      setDemoStageIndex(0);
      setSelectedServiceDate(null);
      setDidBreachOccur(false);
    };
    resetSimulation();
    setShowConfirmPortal(false);
    setShowSchedulingPortal(false);
    setShowReportPortal(false);
  }, [vehicleId]);

  const features = useMemo(() => {
    if (!vehicle?.latest_features) return [];
    const isCritical = (key: string, val: any): boolean => {
      if (demoStatus === "BREACHED" && (key === "engine_temp_c" || key === "battery_percent")) return true;
      const v = typeof val === "number" ? val : parseFloat(val);
      if (isNaN(v)) return false;
      return (key === "engine_temp_c" && v > 105) || (key === "battery_percent" && v < 15);
    };
    return Object.entries(vehicle.latest_features).slice(0, 12).map(([key, value]) => ({
      label: formatFeatureKey(key),
      value: typeof value === "number" ? value.toFixed(1) : String(value),
      critical: isCritical(key, value)
    }));
  }, [vehicle]);

  const issues = vehicle?.risk_state?.unresolved_issues ?? [];

  const lifecycle = useMemo(() => {
    const current = demoStatus === "DEPLOYING" ? LIFECYCLE_STAGES[demoStageIndex]?.key : (vehicle?.workflow_state?.current_stage ?? "IDLE");
    const currentIndex = LIFECYCLE_STAGES.findIndex(s => s.key === current);
    return LIFECYCLE_STAGES.map((stage, index) => ({
      ...stage,
      done: index < currentIndex,
      current: index === currentIndex,
      hum: stage.key === "IDLE" && demoStatus === "IDLE"
    }));
  }, [vehicle, demoStatus, demoStageIndex]);

  const addLog = (msg: string, role = "MASTER", status = "info") => {
    const newEvent: ActivityEvent = {
      event_id: Math.random().toString(),
      vehicle_id: vehicleId,
      source_type: "SYSTEM",
      source_name: role,
      status: status,
      summary: msg,
      action: "DEMO_LOG",
      timestamp: new Date().toISOString(),
    };
    setEvents(prev => [newEvent, ...prev]);
  };

  const runStageDelay = (idx: number) => {
    if (idx >= LIFECYCLE_STAGES.length) {
      setDemoStatus("COMPLETED");
      setDemoStageIndex(-1);
      setShowSuccessPortal(true);
      return;
    }
    setDemoStageIndex(idx);
    const stage = LIFECYCLE_STAGES[idx];
    
    // Logic for specific stages
    if (stage.key === "DIAGNOSIS_PENDING") addLog("Master Agent intercepted telemetry breach. Initiating diagnosis...", "MASTER");
    if (stage.key === "DIAGNOSIS_COMPLETE") addLog("Diagnosis Agent identified Engine Thermal Surge. Isolation Forest consensus: HIGH RISK.", "DIAGNOSIS", "failed");
    if (stage.key === "SCHEDULING_COMPLETE" && !selectedServiceDate) {
      setTimeout(() => setShowSchedulingPortal(true), 1500);
      return;
    }
    if (stage.key === "ENGAGEMENT_COMPLETE") {
      addLog("Engagement Agent notifying owner via verified email channel...", "ENGAGEMENT");
      addLog("Service window confirmed for " + (selectedServiceDate || "soon") + ". Dispatching autonomous units.", "SCHEDULER", "success");
    }
    if (stage.key === "SERVICE_COMPLETED") addLog("Service Completion Agent: All systems nominal. Vehicle restored to optimal health.", "COMPLETED", "success");

    setTimeout(() => runStageDelay(idx + 1), 4000 + Math.random() * 2000);
  };

  const forceRisk = () => {
    setIsSimulating(true);
    setDemoStatus("BREACHED");
    setDidBreachOccur(true);
    addLog("Manual override: System stress test initiated. Monitoring sensor breaches...", "OPERATOR", "failed");
    setTimeout(() => setIsSimulating(false), 1200);
  };

  const startSimulation = () => setShowConfirmPortal(true);

  const confirmDeployment = () => {
    setShowConfirmPortal(false);
    addLog("Operator manually authorised autonomous maintenance lifecycle.", "OPERATOR", "success");
    setDemoStatus("DEPLOYING");
    runStageDelay(0);
  };

  const confirmSchedule = (date: string) => {
    setSelectedServiceDate(date);
    setShowSchedulingPortal(false);
    addLog("Operator selected priority slot: " + date, "OPERATOR", "info");
    const nextIdx = LIFECYCLE_STAGES.findIndex(s => s.key === "SCHEDULING_COMPLETE") + 1;
    runStageDelay(nextIdx);
  };

  async function generateSummary() {
    setLoadingSummary(true);
    try {
      const resp = await regenerateVehicleSummary(vehicleId);
      if (didBreachOccur && resp) {
        resp.business_summary += " Post-incident audit: The thermal surge was successfully intercepted and mitigated via the autonomous cluster.";
      }
      setSummary(resp);
    } catch (e) { console.error(e); }
    finally { setLoadingSummary(false); }
  }

  return (
    <>
      <button
        className={`${styles.forceRiskBtn} ${demoStatus === "DEPLOYING" ? styles.btnDisabled : ""}`}
        onClick={forceRisk}
        disabled={demoStatus === "DEPLOYING"}
      >
        <AlertTriangle size={16} />
        {demoStatus === "BREACHED" ? "SYSTEM BREACH DETECTED" : "Trigger Master Scan"}
      </button>

      {showConfirmPortal && <ConfirmDialog vehicleName={vehicle?.vehicle_profile?.name || vehicleId} onCancel={() => setShowConfirmPortal(false)} onConfirm={confirmDeployment} />}
      {showSchedulingPortal && <SchedulingDialog vehicleName={vehicle?.vehicle_profile?.name || vehicleId} onSelectDate={confirmSchedule} onCancel={() => setShowSchedulingPortal(false)} />}
      {showSuccessPortal && <SuccessDialog onReport={() => { setShowSuccessPortal(false); setShowReportPortal(true); }} onAcknowledge={() => setShowSuccessPortal(false)} />}
      {showReportPortal && <MissionReportDialog vehicle={vehicle} vehicleId={vehicleId} events={events} summary={summary} onClose={() => setShowReportPortal(false)} />}

      <LiveTelemetryModal vehicleId={vehicleId} isOpen={isLiveStreamOpen} onClose={() => setIsLiveStreamOpen(false)} />

      <nav className={`${styles.navBar} ${isLiveStreamOpen ? styles.blurred : ""}`}>
        <div className={styles.navLeft}>
          <Link href="/welcome" className={styles.navLogo}><Zap strokeWidth={2.5} /></Link>
          <span className={styles.navTitle}>Auto<span className={styles.navTitleAccent}>AI</span></span>
        </div>
        <div className={styles.navRight}>
          <Link href="/welcome" className={styles.backBtn}><ArrowLeft size={14} /> Fleet</Link>
          <UserButton appearance={{ elements: { avatarBox: { width: "34px", height: "34px" } } }} />
        </div>
      </nav>

      <main className={`${styles.shell} ${isLiveStreamOpen ? styles.blurred : ""}`}>
        <motion.section className={styles.vehicleHero} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <div className={styles.heroLeft}>
            <p className={`${styles.heroLabel} mono`}>Mission Control</p>
            <h1 className={styles.heroName}>{vehicle?.vehicle_profile?.name ?? vehicleId}</h1>
            <p className={styles.heroIdentity}>{(vehicle?.vehicle_profile?.model ?? "Standard Hauler")} · {(vehicle?.vehicle_profile?.year ?? 2026)}</p>
          </div>
          <div className={styles.heroRight}>
            <button
              className={`${styles.premiumBtn} ${styles.simulationBtn} ${demoStatus === "BREACHED" ? styles.btnPulseAction : ""}`}
              onClick={startSimulation}
              disabled={demoStatus !== "BREACHED"}
            >
              <Sparkles size={16} />
              {demoStatus === "DEPLOYING" ? "Agents Active" : "Initiate Recovery"}
            </button>
            <div className={styles.heroStatusArea}>
              <span className={`${styles.currentStageBadge} ${getStageStyle(demoStatus === "DEPLOYING" ? LIFECYCLE_STAGES[demoStageIndex]?.key : vehicle?.workflow_state?.current_stage)}`}>
                <Radio size={14} />
                {demoStatus === "DEPLOYING" ? toReadableStage(LIFECYCLE_STAGES[demoStageIndex]?.key) : toReadableStage(vehicle?.workflow_state?.current_stage)}
              </span>
            </div>
          </div>
        </motion.section>

        <section className={styles.lifecycleSection}>
          <div className={styles.lifecycleTrack}>
            {lifecycle.map((stage, i) => (
              <div key={stage.key} style={{ display: "contents" }}>
                {i > 0 && <div className={`${styles.lifecycleConnector} ${stage.done ? styles.connectorDone : stage.current ? styles.connectorActive : ""}`} />}
                <div className={styles.lifecycleNode}>
                  <div className={`${styles.nodeCircle} ${stage.done ? styles.nodeDone : stage.current ? styles.nodeCurrent : stage.hum ? styles.nodeHum : styles.nodePending}`}>
                    {stage.done ? <Check size={18} /> : stage.current ? <Circle size={16} fill="currentColor" /> : <Circle size={16} />}
                  </div>
                  <span className={`${styles.nodeLabel} ${stage.done || stage.current || stage.hum ? styles.nodeLabelActive : ""} mono`}>{stage.label}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <div className={styles.contentGrid}>
          <section className={styles.panel}>
            <div className={styles.panelHeader}><h2 className={styles.panelTitle}><Gauge size={18} /> Telemetry</h2><button className={styles.premiumBtn} onClick={() => setIsLiveStreamOpen(true)}><Radio size={14} /> Stream</button></div>
            <div className={styles.featureGrid}>
              {features.map((f) => (
                <div key={f.label} className={`${styles.featureCard} ${f.critical ? styles.featureCardCritical : ""}`}>
                  <p className="mono">{f.label}</p>
                  <p className={styles.featureValue}>{f.value}</p>
                </div>
              ))}
            </div>
          </section>

          <div style={{ display: "grid", gap: 24 }}>
            <section className={styles.panel}>
              <div className={styles.panelHeader}><h2 className={styles.panelTitle}><Sparkles size={18} /> AI Summary</h2><button className={styles.summaryBtn} onClick={generateSummary} disabled={loadingSummary}>{loadingSummary ? "Analysing..." : "Regenerate"}</button></div>
              <div className={styles.summaryContent}>
                {summary ? (
                  <div className={styles.summaryBeautyWrapper}>
                    <p><HighlightText text={summary.business_summary} /></p>
                    <button className={styles.pdfBtn} onClick={() => setShowReportPortal(true)}><FileText size={14} /> View PDF Report</button>
                  </div>
                ) : <p>Scan system to generate insights.</p>}
              </div>
            </section>
          </div>
        </div>

        <section className={styles.panel}>
          <div className={styles.panelHeader}><h2 className={styles.panelTitle}><Activity size={18} /> Activity Log</h2></div>
          <div className={styles.liveList}>
            {events.map((e) => (
              <div key={e.event_id} className={styles.liveItem}>
                <span className={`${styles.liveItemDot} ${getEventDotClass(e.status)}`} />
                <span className={styles.liveItemSummary}>{e.summary}</span>
                <span className="mono">{timeAgo(e.timestamp)}</span>
              </div>
            ))}
          </div>
        </section>
      </main>
    </>
  );
}
