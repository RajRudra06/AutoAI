"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchVehicleActivity, fetchVehicles, fetchVehicleSummary, regenerateVehicleSummary } from "@/lib/api";
import { ActivityEvent, VehicleState, VehicleSummaryPayload } from "@/lib/types";
import styles from "@/app/vehicle/[id]/page.module.css";

function toReadableStage(stage?: string): string {
  if (!stage) return "Unknown";
  return stage.replaceAll("_", " ").toLowerCase().replace(/^./, (m) => m.toUpperCase());
}

function formatFeatureKey(raw: string): string {
  return raw
    .replaceAll("_", " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .toLowerCase()
    .replace(/^./, (m) => m.toUpperCase());
}

function summaryFeatures(vehicle: VehicleState): Array<{ label: string; value: string }> {
  const features = vehicle.latest_features ?? {};
  return Object.entries(features)
    .slice(0, 6)
    .map(([key, value]) => ({
      label: formatFeatureKey(key),
      value: String(value),
    }));
}

export default function VehicleDetailsPage() {
  const params = useParams<{ id: string }>();
  const vehicleId = params?.id ?? "UNKNOWN";

  const [vehicle, setVehicle] = useState<VehicleState | null>(null);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [summary, setSummary] = useState<VehicleSummaryPayload | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  const refresh = useCallback(async () => {
    const [allVehicles, timeline] = await Promise.all([fetchVehicles(), fetchVehicleActivity(vehicleId, 20)]);
    setVehicle(allVehicles.find((item) => item.vehicle_id === vehicleId) ?? null);
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
    const timer = window.setInterval(() => {
      refresh();
    }, 5000);

    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [refresh, vehicleId]);

  const features = vehicle ? summaryFeatures(vehicle) : [];
  const issues = vehicle?.risk_state?.unresolved_issues ?? [];

  const lifecycle = useMemo(() => {
    const stages = ["IDLE", "DIAGNOSIS_PENDING", "DIAGNOSIS_COMPLETE", "SCHEDULING_COMPLETE", "ENGAGEMENT_COMPLETE"];
    const current = vehicle?.workflow_state?.current_stage;
    const currentIndex = stages.indexOf(current ?? "IDLE");

    return stages.map((stage, index) => ({
      stage,
      done: index < currentIndex,
      current: index === currentIndex,
    }));
  }, [vehicle]);

  async function generateSummary() {
    setLoadingSummary(true);
    try {
      const data = await regenerateVehicleSummary(vehicleId);
      setSummary(data);
    } finally {
      setLoadingSummary(false);
    }
  }

  return (
    <main className={styles.shell}>
      <header className={styles.topbar}>
        <div>
          <p className="mono">VEHICLE</p>
          <h1>{vehicleId}</h1>
          <p className={styles.subtitle}>Live simple summary, issue view, and lifecycle progress.</p>
        </div>

        <Link className={styles.backLink} href="/welcome">
          Back to Welcome
        </Link>
      </header>

      <section className={styles.grid}>
        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            <h2>Live Telemetry Summary</h2>
            <span className="mono">{toReadableStage(vehicle?.workflow_state?.current_stage)}</span>
          </div>

          {!vehicle ? (
            <p className={styles.empty}>Loading vehicle details...</p>
          ) : features.length === 0 ? (
            <p className={styles.empty}>No telemetry summary available yet.</p>
          ) : (
            <div className={styles.featureGrid}>
              {features.map((item) => (
                <article key={item.label} className={styles.featureCard}>
                  <p className="mono">{item.label}</p>
                  <h3>{item.value}</h3>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            <h2>Issue Window</h2>
            <span className="mono">{issues.length}</span>
          </div>

          {issues.length === 0 ? (
            <p className={styles.empty}>No active issues for this vehicle.</p>
          ) : (
            <ul className={styles.issueList}>
              {issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          )}

          {vehicle?.risk_state?.high_risk_active ? <p className={styles.alert}>High-risk mode is active.</p> : null}
        </section>
      </section>

      <section className={styles.grid}>
        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            <h2>Lifecycle Flow</h2>
            <span className="mono">recently serviced flow</span>
          </div>

          <div className={styles.flowList}>
            {lifecycle.map((item) => (
              <div
                key={item.stage}
                className={`${styles.flowItem} ${item.current ? styles.flowCurrent : item.done ? styles.flowDone : ""}`}
              >
                {toReadableStage(item.stage)}
              </div>
            ))}
          </div>
        </section>

        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            <h2>AI Summary</h2>
            <button className={styles.summaryBtn} onClick={generateSummary} disabled={loadingSummary}>
              {loadingSummary ? "Generating..." : "Get Crew AI Summary"}
            </button>
          </div>

          {!summary ? (
            <p className={styles.empty}>No AI summary generated yet.</p>
          ) : (
            <div className={styles.summaryBlocks}>
              <article>
                <p className="mono">Business</p>
                <p>{summary.business_summary}</p>
              </article>
              <article>
                <p className="mono">Judge</p>
                <p>{summary.judge_summary}</p>
              </article>
            </div>
          )}
        </section>
      </section>

      <section className={styles.panel}>
        <div className={styles.panelHeader}>
          <h2>Recent Live Updates</h2>
          <span className="mono">{events.length}</span>
        </div>

        {events.length === 0 ? (
          <p className={styles.empty}>No live updates yet.</p>
        ) : (
          <div className={styles.liveList}>
            {events.map((event) => (
              <article key={event.event_id} className={styles.liveItem}>
                <p>{event.summary}</p>
                <span className="mono">{toReadableStage(event.stage_to ?? event.stage_from ?? "IDLE")}</span>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
