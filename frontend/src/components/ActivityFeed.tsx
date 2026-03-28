"use client";

import { ActivityEvent } from "@/lib/types";
import styles from "@/components/panels.module.css";

type ActivityFeedProps = {
  title: string;
  events: ActivityEvent[];
};

export function ActivityFeed({ title, events }: ActivityFeedProps) {
  return (
    <section className={styles.feedPanel}>
      <header className={styles.sectionHeader}>
        <h3>{title}</h3>
        <span className="mono">{events.length} events</span>
      </header>

      <div className={styles.feedList}>
        {events.slice(0, 20).map((event) => (
          <article key={event.event_id} className={styles.feedItem}>
            <div className={styles.feedTopRow}>
              <p className={`${styles.feedSource} mono`}>{event.source_name}</p>
              <span className={`${styles.status} ${styles[`status_${event.status}`]}`}>{event.status}</span>
            </div>
            <h4>{event.action}</h4>
            <p>{event.summary}</p>
            <div className={`${styles.feedBottomRow} mono`}>
              <span>{event.vehicle_id}</span>
              <span>{event.stage_from ?? "UNKNOWN"} -&gt; {event.stage_to ?? "UNKNOWN"}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
