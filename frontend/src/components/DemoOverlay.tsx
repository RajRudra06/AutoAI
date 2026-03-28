"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchVehicleSummary, regenerateVehicleSummary } from "@/lib/api";
import { ActivityEvent, VehicleSummaryPayload } from "@/lib/types";
import styles from "@/components/panels.module.css";

type DemoOverlayProps = {
  events: ActivityEvent[];
};

export function DemoOverlay({ events }: DemoOverlayProps) {
  const [open, setOpen] = useState(false);
  const [selectedVehicle, setSelectedVehicle] = useState<string>("UNKNOWN");
  const [summary, setSummary] = useState<VehicleSummaryPayload | null>(null);
  const [loading, setLoading] = useState(false);

  const spotlightVehicles = useMemo(() => {
    const ranked: string[] = [];
    const seen = new Set<string>();

    const priority = [...events].sort((a, b) => {
      const aRisk = (a.risk_level || "").toUpperCase() === "HIGH" ? 1 : 0;
      const bRisk = (b.risk_level || "").toUpperCase() === "HIGH" ? 1 : 0;
      return bRisk - aRisk;
    });

    for (const event of priority) {
      if (!event.vehicle_id || seen.has(event.vehicle_id)) continue;
      seen.add(event.vehicle_id);
      ranked.push(event.vehicle_id);
      if (ranked.length >= 6) break;
    }

    return ranked;
  }, [events]);

  useEffect(() => {
    if (spotlightVehicles.length === 0) return;
    setSelectedVehicle((current) => (current === "UNKNOWN" ? spotlightVehicles[0] : current));
  }, [spotlightVehicles]);

  useEffect(() => {
    if (!selectedVehicle || selectedVehicle === "UNKNOWN") return;

    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const existing = await fetchVehicleSummary(selectedVehicle);
        const resolved = existing ?? (await regenerateVehicleSummary(selectedVehicle));
        if (!cancelled) setSummary(resolved);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [selectedVehicle]);

  const vehicleTimeline = useMemo(() => {
    if (!selectedVehicle || selectedVehicle === "UNKNOWN") return [];
    return events
      .filter((event) => event.vehicle_id === selectedVehicle)
      .slice(0, 5)
      .map((event) => ({
        action: event.action,
        status: event.status,
        stage: event.stage_to ?? event.stage_from ?? "UNKNOWN",
      }));
  }, [events, selectedVehicle]);

  return (
    <div className={styles.demoDock}>
      <button className={styles.demoToggle} onClick={() => setOpen((value) => !value)}>
        {open ? "Close Judge Overlay" : "Launch Judge Overlay"}
      </button>

      {open ? (
        <section className={styles.demoPanel}>
          <header className={styles.sectionHeader}>
            <h3>Judge Mode Storyline</h3>
            <span className="mono">narrative command layer</span>
          </header>

          <div className={styles.demoVehicleRow}>
            <label htmlFor="demo-vehicle" className="mono">
              Spotlight Vehicle
            </label>
            <select
              id="demo-vehicle"
              className={styles.demoSelect}
              value={selectedVehicle}
              onChange={(event) => setSelectedVehicle(event.target.value)}
            >
              {spotlightVehicles.length === 0 ? <option value="UNKNOWN">No vehicle data</option> : null}
              {spotlightVehicles.map((vehicleId) => (
                <option key={vehicleId} value={vehicleId}>
                  {vehicleId}
                </option>
              ))}
            </select>
          </div>

          <div className={styles.demoNarrative}>
            <article>
              <p className="mono">Narrative for Judges</p>
              <p>
                {loading
                  ? "Refreshing storyline..."
                  : (summary?.judge_summary ?? "No judge narrative is available yet for this vehicle.")}
              </p>
            </article>
            <article>
              <p className="mono">Business Lens</p>
              <p>
                {summary?.business_summary ??
                  "Business impact story will appear after at least one full lifecycle progression."}
              </p>
            </article>
          </div>

          <div className={styles.demoBeats}>
            <p className="mono">Walkthrough Beats</p>
            {vehicleTimeline.length === 0 ? (
              <p className={styles.placeholder}>No recent events yet for this spotlight vehicle.</p>
            ) : (
              <ol>
                {vehicleTimeline.map((item, idx) => (
                  <li key={`${item.action}-${idx}`}>
                    <span>{item.action}</span>
                    <span className={`${styles.status} ${styles[`status_${item.status}`]}`}>{item.status}</span>
                    <span className="mono">{item.stage}</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </section>
      ) : null}
    </div>
  );
}