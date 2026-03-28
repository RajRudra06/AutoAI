"use client";

import Link from "next/link";
import { ActivityEvent } from "@/lib/types";
import styles from "@/components/panels.module.css";

type IncidentPanelProps = {
  events: ActivityEvent[];
  title?: string;
  maxItems?: number;
};

const incidentStatuses = new Set(["failed", "stale", "skipped"]);

export function IncidentPanel({
  events,
  title = "Incidents and Recoveries",
  maxItems = 8,
}: IncidentPanelProps) {
  const incidents = events.filter((event) => incidentStatuses.has(event.status)).slice(0, maxItems);

  return (
    <section className={styles.incidentPanel}>
      <header className={styles.sectionHeader}>
        <h3>{title}</h3>
        <span className="mono">{incidents.length} active traces</span>
      </header>

      {incidents.length === 0 ? (
        <p className={styles.placeholder}>No recent stale/failed/skipped lifecycle incidents.</p>
      ) : (
        <div className={styles.incidentList}>
          {incidents.map((event) => (
            <article key={event.event_id} className={styles.incidentItem}>
              <div className={styles.feedTopRow}>
                <span className={`${styles.status} ${styles[`status_${event.status}`]}`}>{event.status}</span>
                <p className="mono">{event.source_name}</p>
              </div>
              <p className={styles.incidentSummary}>{event.summary}</p>
              <Link className={styles.incidentLink} href={`/vehicle/${event.vehicle_id}`}>
                Open {event.vehicle_id}
              </Link>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}