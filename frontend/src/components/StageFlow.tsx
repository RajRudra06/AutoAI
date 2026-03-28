"use client";

import { motion } from "framer-motion";
import styles from "@/components/panels.module.css";

type StageFlowProps = {
  stageOrder: string[];
  counts: Record<string, number>;
};

const stageAccentMap: Record<string, string> = {
  IDLE: "#3db3ff",
  DIAGNOSIS_PENDING: "#f9a942",
  DIAGNOSIS_COMPLETE: "#ff4f6c",
  SCHEDULING_COMPLETE: "#ff7f4d",
  ENGAGEMENT_COMPLETE: "#3ddc97",
};

export function StageFlow({ stageOrder, counts }: StageFlowProps) {
  const max = Math.max(1, ...stageOrder.map((stage) => counts[stage] ?? 0));

  return (
    <section className={styles.flowPanel}>
      <header className={styles.sectionHeader}>
        <h3>Lifecycle Pressure Map</h3>
        <span className="mono">live stage occupancy</span>
      </header>

      <div className={styles.flowGrid}>
        {stageOrder.map((stage, index) => {
          const count = counts[stage] ?? 0;
          const intensity = Math.max(0.18, count / max);

          return (
            <motion.div
              className={styles.flowStage}
              key={stage}
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
              style={{
                borderColor: stageAccentMap[stage] ?? "#4bf0e2",
                boxShadow: `0 0 24px color-mix(in srgb, ${stageAccentMap[stage] ?? "#4bf0e2"} ${Math.round(intensity * 100)}%, transparent)`,
              }}
            >
              <p className={`${styles.stageName} mono`}>{stage}</p>
              <div className={styles.stageBarWrap}>
                <motion.div
                  className={styles.stageBar}
                  style={{
                    background: stageAccentMap[stage] ?? "#4bf0e2",
                  }}
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.round(intensity * 100)}%` }}
                  transition={{ duration: 0.6 }}
                />
              </div>
              <p className={styles.stageCount}>{count}</p>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
