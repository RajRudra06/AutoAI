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
    return Object.entries(vehicle.latest_features).slice(0, 12).map(([key, value]) => ({
      label: formatFeatureKey(key),
      value: typeof value === "number" ? value.toFixed(1) : String(value),
    }));
  }, [vehicle]);

  const issues = vehicle?.risk_state?.unresolved_issues ?? [];

  const lifecycle = useMemo(() => {
    const current = vehicle?.workflow_state?.current_stage ?? "IDLE";
    const currentIndex = LIFECYCLE_STAGES.findIndex((s) => s.key === current);
    return LIFECYCLE_STAGES.map((stage, index) => ({
      ...stage,
      done: index < currentIndex,
      current: index === currentIndex,
    }));
  }, [vehicle]);

  async function generateSummary() {
    setLoadingSummary(true);
    try {
      const resp = await regenerateVehicleSummary(vehicleId);
      setSummary(resp);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingSummary(false);
    }
  }

  async function startSimulation() {
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${baseUrl}/api/simulation/start/${vehicleId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (resp.ok) {
        await refresh();
      }
    } catch (e) {
      console.error("Failed to start simulation:", e);
    }
  }

  return (
    <>
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
            <span
              className={`${styles.currentStageBadge} ${getStageStyle(vehicle?.workflow_state?.current_stage)}`}
            >
              <Radio size={14} />
              {toReadableStage(vehicle?.workflow_state?.current_stage)}
            </span>
            {vehicle?.risk_state?.high_risk_active && (
              <span className={styles.riskBadge}>
                <AlertTriangle size={14} />
                High Risk Active
              </span>
            )}
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
                    className={`${styles.lifecycleConnector} ${
                      stage.done
                        ? styles.connectorDone
                        : stage.current
                          ? styles.connectorActive
                          : ""
                    }`}
                  />
                )}
                <div className={styles.lifecycleNode}>
                  <div
                    className={`${styles.nodeCircle} ${
                      stage.done
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
                    className={`${styles.nodeLabel} ${
                      stage.done || stage.current ? styles.nodeLabelActive : ""
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
                  className={styles.simulationBtn}
                  onClick={startSimulation}
                  title="Start the autonomous service lifecycle"
                >
                  <Sparkles size={16} />
                  Start Service Journey
                </button>
                <button
                  className={styles.streamToggleBtn}
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
                    className={styles.featureCard}
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

              {!summary ? (
                <div className={styles.empty}>
                  <div className={styles.emptyIcon}><Sparkles /></div>
                  <p>Click Generate to create an AI-powered journey summary.</p>
                </div>
              ) : (
                <div className={styles.summaryBlocks}>
                  <article className={styles.summaryBlock}>
                    <p className={`${styles.summaryBlockLabel} mono`}>
                      Business Insight
                    </p>
                    <p className={styles.summaryBlockText}>
                      {summary.business_summary}
                    </p>
                  </article>
                  <article className={styles.summaryBlock}>
                    <p className={`${styles.summaryBlockLabel} mono`}>
                      Judge Summary
                    </p>
                    <p className={styles.summaryBlockText}>
                      {summary.judge_summary}
                    </p>
                  </article>
                </div>
              )}
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
              {events.map((event, i) => (
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
