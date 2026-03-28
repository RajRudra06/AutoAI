"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchVehicleSummary, regenerateVehicleSummary } from "@/lib/api";
import { VehicleSummaryPayload } from "@/lib/types";
import styles from "@/components/panels.module.css";

type SummaryPanelProps = {
  vehicleId: string;
};

export function SummaryPanel({ vehicleId }: SummaryPanelProps) {
  const [summary, setSummary] = useState<VehicleSummaryPayload | null>(null);
  const [loading, setLoading] = useState(false);

  const loadSummary = useCallback(async () => {
    setLoading(true);
    try {
      const data = (await fetchVehicleSummary(vehicleId)) ?? (await regenerateVehicleSummary(vehicleId));
      setSummary(data);
    } finally {
      setLoading(false);
    }
  }, [vehicleId]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  return (
    <section className={styles.summaryPanel}>
      <header className={styles.sectionHeader}>
        <h3>Journey Summary</h3>
        <button className={styles.summaryButton} onClick={loadSummary} disabled={loading}>
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </header>

      {!summary ? (
        <p className={styles.placeholder}>No summary found yet for this vehicle.</p>
      ) : (
        <div className={styles.summaryStack}>
          <article>
            <p className="mono">Technical</p>
            <p>{summary.technical_summary}</p>
          </article>
          <article>
            <p className="mono">Business</p>
            <p>{summary.business_summary}</p>
          </article>
          <article>
            <p className="mono">Judge Mode</p>
            <p>{summary.judge_summary}</p>
          </article>
        </div>
      )}
    </section>
  );
}
