"use client";

import { QueueWorkerHealth } from "@/lib/types";
import styles from "@/components/panels.module.css";

type QueueHealthPanelProps = {
  health: QueueWorkerHealth;
  connected: boolean;
};

type HealthRow = {
  label: string;
  value: number;
  color: "good" | "warn" | "critical";
  note: string;
};

function toChartBars(values: number[]): number[] {
  if (!values.length) return [0];
  const max = Math.max(1, ...values);
  return values.map((value) => Math.max(8, Math.round((value / max) * 100)));
}

function classify(value: number): HealthRow["color"] {
  if (value < 34) return "good";
  if (value < 67) return "warn";
  return "critical";
}

export function QueueHealthPanel({ health, connected }: QueueHealthPanelProps) {
  const onlineWorkers = health.worker_heartbeat.online_worker_count;
  const workerTarget = Math.max(1, Object.keys(health.worker_heartbeat.workers).length);

  const workerPressure = Math.max(0, 100 - Math.round((onlineWorkers / workerTarget) * 100));
  const queuePressure = Math.min(100, Math.round(health.total_queue_depth * 4));
  const hotspotPressure = Math.min(100, Math.round(health.max_queue_depth * 10));

  const rows: HealthRow[] = [
    {
      label: "Realtime Link",
      value: connected ? 8 : 62,
      color: connected ? "good" : "warn",
      note: connected ? "WebSocket stream healthy" : "Falling back to polling",
    },
    {
      label: "Queue Backlog",
      value: queuePressure,
      color: classify(queuePressure),
      note: `${health.total_queue_depth} queued jobs across all queues`,
    },
    {
      label: "Queue Hotspot",
      value: hotspotPressure,
      color: classify(hotspotPressure),
      note: `largest queue depth is ${health.max_queue_depth}`,
    },
    {
      label: "Worker Heartbeat",
      value: workerPressure,
      color: classify(workerPressure),
      note: `${onlineWorkers} online worker(s), status ${health.worker_heartbeat.status}`,
    },
  ];

  const latencyBars = toChartBars(health.latency_ms_trend ?? []);
  const retryBars = toChartBars(health.retry_signal_trend ?? []);

  return (
    <section className={styles.healthPanel}>
      <header className={styles.sectionHeader}>
        <h3>Queue and Worker Health</h3>
        <span className="mono">live broker + heartbeat</span>
      </header>

      <div className={styles.healthRows}>
        {rows.map((row) => (
          <article className={styles.healthRow} key={row.label}>
            <div className={styles.healthRowTop}>
              <p className="mono">{row.label}</p>
              <span>{row.value}%</span>
            </div>
            <div className={styles.healthBarTrack}>
              <div className={`${styles.healthBarFill} ${styles[`health_${row.color}`]}`} style={{ width: `${row.value}%` }} />
            </div>
            <p className={styles.healthNote}>{row.note}</p>
          </article>
        ))}
      </div>

      <div className={styles.trendGrid}>
        <article className={styles.trendCard}>
          <div className={styles.trendHeader}>
            <p className="mono">Latency Trend</p>
            <span>{health.avg_latency_ms.toFixed(1)} ms avg</span>
          </div>
          <div className={styles.sparklineBars}>
            {latencyBars.map((height, idx) => (
              <span key={`lat-${idx}`} className={styles.sparkBarLatency} style={{ height: `${height}%` }} />
            ))}
          </div>
        </article>

        <article className={styles.trendCard}>
          <div className={styles.trendHeader}>
            <p className="mono">Retry Signal</p>
            <span>{health.retry_signal_percent.toFixed(1)}% pressure</span>
          </div>
          <div className={styles.sparklineBars}>
            {retryBars.map((height, idx) => (
              <span key={`ret-${idx}`} className={styles.sparkBarRetry} style={{ height: `${height}%` }} />
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}