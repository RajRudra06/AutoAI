"use client";

import { motion } from "framer-motion";
import styles from "@/components/panels.module.css";

type MetricCardProps = {
  label: string;
  value: string | number;
  accent: "blue" | "amber" | "red" | "green" | "cyan";
  footnote?: string;
};

export function MetricCard({ label, value, accent, footnote }: MetricCardProps) {
  return (
    <motion.article
      className={`${styles.card} ${styles[`accent_${accent}`]}`}
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <p className={`${styles.label} mono`}>{label}</p>
      <h3 className={styles.value}>{value}</h3>
      {footnote ? <p className={styles.footnote}>{footnote}</p> : null}
    </motion.article>
  );
}
