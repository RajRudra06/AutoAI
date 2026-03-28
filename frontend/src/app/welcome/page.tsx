"use client";

import Link from "next/link";
import { SignOutButton, useUser } from "@clerk/nextjs";
import { useEffect, useMemo, useState } from "react";
import { fetchVehicles } from "@/lib/api";
import { VehicleState } from "@/lib/types";
import styles from "@/app/welcome/page.module.css";

function readVehicleIdsFromMetadata(metadata: unknown): string[] {
  if (!metadata || typeof metadata !== "object") return [];
  const value = (metadata as Record<string, unknown>).vehicleIds;
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

export default function WelcomePage() {
  const { user } = useUser();
  const [vehicles, setVehicles] = useState<VehicleState[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const rows = await fetchVehicles();
        if (!cancelled) setVehicles(rows);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const allowedIds = readVehicleIdsFromMetadata(user?.publicMetadata);

  const myVehicles = useMemo(() => {
    if (!allowedIds.length) return vehicles;
    const allow = new Set(allowedIds);
    return vehicles.filter((vehicle) => allow.has(vehicle.vehicle_id));
  }, [vehicles, allowedIds]);

  const issueVehicles = myVehicles.filter(
    (vehicle) => vehicle.risk_state?.high_risk_active || (vehicle.risk_state?.unresolved_issues?.length ?? 0) > 0,
  );

  return (
    <main className={styles.shell}>
      <header className={styles.hero}>
        <div>
          <p className="mono">WELCOME</p>
          <h1>Hi {user?.firstName ?? "Driver"}, here are your vehicles.</h1>
          <p className={styles.subtitle}>
            Clean view only: vehicle status, issue alerts, and click-through to live summary + lifecycle.
          </p>
        </div>

        <SignOutButton>
          <button className={styles.openBtn}>Sign Out</button>
        </SignOutButton>
      </header>

      <section className={styles.grid}>
        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            <h2>My Vehicles</h2>
            <span className="mono">{myVehicles.length}</span>
          </div>

          {loading ? (
            <p className={styles.empty}>Loading your vehicles...</p>
          ) : myVehicles.length === 0 ? (
            <p className={styles.empty}>
              No vehicles are assigned to your account yet. Add `vehicleIds` in Clerk user public metadata.
            </p>
          ) : (
            <div className={styles.vehicleGrid}>
              {myVehicles.map((vehicle) => {
                const hasIssue =
                  vehicle.risk_state?.high_risk_active || (vehicle.risk_state?.unresolved_issues?.length ?? 0) > 0;
                return (
                  <article key={vehicle.vehicle_id} className={styles.vehicleCard}>
                    <h3>{vehicle.vehicle_id}</h3>
                    <span className={`${styles.badge} ${hasIssue ? styles.badgeBad : styles.badgeOk}`}>
                      {hasIssue ? "Needs Attention" : "Healthy"}
                    </span>
                    <p className={styles.vehicleMeta}>Stage: {vehicle.workflow_state?.current_stage ?? "UNKNOWN"}</p>
                    <p className={styles.vehicleMeta}>Pipeline: {vehicle.pipeline_associated?.pipeline_status ?? "UNKNOWN"}</p>
                    <Link className={styles.openBtn} href={`/vehicle/${vehicle.vehicle_id}`}>
                      Open Vehicle
                    </Link>
                  </article>
                );
              })}
            </div>
          )}
        </section>

        <section className={styles.panel}>
          <div className={styles.panelHeader}>
            <h2>Issue Window</h2>
            <span className="mono">{issueVehicles.length}</span>
          </div>

          {issueVehicles.length === 0 ? (
            <p className={styles.empty}>No bad vehicles right now.</p>
          ) : (
            <div className={styles.issueList}>
              {issueVehicles.map((vehicle) => (
                <article key={vehicle.vehicle_id} className={styles.issueItem}>
                  <h3>{vehicle.vehicle_id}</h3>
                  <p>
                    {(vehicle.risk_state?.unresolved_issues ?? []).slice(0, 2).join("; ") ||
                      "High risk detected. Immediate review recommended."}
                  </p>
                  <Link className={styles.openBtn} href={`/vehicle/${vehicle.vehicle_id}`}>
                    View Issues
                  </Link>
                </article>
              ))}
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
