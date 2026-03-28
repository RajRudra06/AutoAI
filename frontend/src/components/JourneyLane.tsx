"use client";

import { ActivityEvent } from "@/lib/types";
import styles from "@/components/panels.module.css";

type JourneyLaneProps = {
  vehicleId: string;
  events: ActivityEvent[];
};

function toTime(ts?: string): string {
  if (!ts) return "--:--:--";
  return new Date(ts).toLocaleTimeString();
}

export function JourneyLane({ vehicleId, events }: JourneyLaneProps) {
  const ordered = [...events].sort((a, b) => +new Date(a.timestamp) - +new Date(b.timestamp));
  const lanes = ordered
    .map((event) => event.stage_to)
    .filter((stage): stage is string => Boolean(stage))
    .filter((stage, idx, arr) => idx === 0 || arr[idx - 1] !== stage);

  const first = ordered[0];
  const last = ordered[ordered.length - 1];

  return (
    <section className={styles.journeyPanel}>
      <header className={styles.sectionHeader}>
        <h3>Vehicle Lane Context</h3>
        <span className="mono">{vehicleId}</span>
      </header>

      {lanes.length === 0 ? (
        <p className={styles.placeholder}>No lane transitions yet for this vehicle.</p>
      ) : (
        <div className={styles.laneWrap}>
          {lanes.map((stage, index) => (
            <div className={styles.laneChip} key={`${stage}-${index}`}>
              <span className="mono">{index + 1}</span>
              <p>{stage}</p>
            </div>
          ))}
        </div>
      )}

      <div className={styles.journeyMeta}>
        <p className="mono">First Seen: {toTime(first?.timestamp)}</p>
        <p className="mono">Latest Event: {toTime(last?.timestamp)}</p>
        <p className="mono">Event Count: {events.length}</p>
      </div>
    </section>
  );
}