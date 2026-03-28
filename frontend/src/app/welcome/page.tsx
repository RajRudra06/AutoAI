"use client";

import Link from "next/link";
import { SignOutButton, UserButton, useUser } from "@clerk/nextjs";
import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Zap,
  Plus,
  Car,
  AlertTriangle,
  Activity,
  Shield,
  ChevronRight,
  X,
  ArrowRight,
  Trash2,
} from "lucide-react";
import { fetchVehicles, registerVehicle, deleteVehicle } from "@/lib/api";
import { VehicleState } from "@/lib/types";
import styles from "@/app/welcome/page.module.css";

/* ─── Stage Display Helpers ─── */
function getStageDisplay(stage?: string) {
  const stages: Record<string, { label: string; cls: string }> = {
    IDLE: { label: "Idle", cls: styles.stageIdle },
    DIAGNOSIS_PENDING: { label: "Diagnosing", cls: styles.stagePending },
    DIAGNOSIS_COMPLETE: { label: "Diagnosed", cls: styles.stageComplete },
    SCHEDULING_COMPLETE: { label: "Scheduled", cls: styles.stageComplete },
    ENGAGEMENT_COMPLETE: { label: "Engaged", cls: styles.stageComplete },
  };
  return stages[stage ?? "IDLE"] ?? stages.IDLE;
}

function readVehicleIdsFromMetadata(metadata: unknown): string[] {
  if (!metadata || typeof metadata !== "object") return [];
  const value = (metadata as Record<string, unknown>).vehicleIds;
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

/* ─── Animated Counter ─── */
function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (value === display) return;
    const step = value > display ? 1 : -1;
    const timer = setInterval(() => {
      setDisplay((prev) => {
        const next = prev + step;
        if ((step > 0 && next >= value) || (step < 0 && next <= value)) {
          clearInterval(timer);
          return value;
        }
        return next;
      });
    }, 50);
    return () => clearInterval(timer);
  }, [value, display]);

  return <>{display}</>;
}

/* ─── Main Page ─── */
export default function WelcomePage() {
  const { user } = useUser();
  const [vehicles, setVehicles] = useState<VehicleState[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [form, setForm] = useState({
    vehicle_name: "",
    company: "",
    vehicle_type: "",
    model: "",
    year: "",
  });

  /* ─── Load Vehicles ─── */
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoadError(null);
        const rows = await fetchVehicles(user?.id);
        if (!cancelled) setVehicles(rows);
      } catch (err) {
        if (!cancelled) {
          setLoadError(
            err instanceof Error ? err.message : "Unable to load vehicles."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    if (user?.id) load();
    return () => {
      cancelled = true;
    };
  }, [user?.id]);

  const allowedIds = readVehicleIdsFromMetadata(user?.publicMetadata);
  const myVehicles = useMemo(() => {
    if (!allowedIds.length) return vehicles;
    const allowed = new Set(allowedIds);
    return vehicles.filter((v) => allowed.has(v.vehicle_id));
  }, [vehicles, allowedIds]);

  const issueVehicles = myVehicles.filter(
    (v) =>
      v.risk_state?.high_risk_active ||
      (v.risk_state?.unresolved_issues?.length ?? 0) > 0
  );

  const activeVehicles = myVehicles.filter(
    (v) =>
      v.workflow_state?.current_stage &&
      v.workflow_state.current_stage !== "IDLE"
  );

  /* ─── Refresh & Submit ─── */
  async function refreshVehicles() {
    if (!user?.id) return;
    const rows = await fetchVehicles(user.id);
    setVehicles(rows);
  }

  async function onAddVehicle(e: React.FormEvent) {
    e.preventDefault();
    if (!user?.id) return;
    if (
      !form.vehicle_name ||
      !form.company ||
      !form.vehicle_type ||
      !form.model
    ) {
      setFormError("Please fill in all required fields.");
      return;
    }

    setSaving(true);
    setFormError(null);
    try {
      await registerVehicle({
        owner_id: user.id,
        owner_name: user.fullName ?? user.firstName ?? undefined,
        owner_email: user.primaryEmailAddress?.emailAddress,
        vehicle_name: form.vehicle_name,
        company: form.company,
        vehicle_type: form.vehicle_type,
        model: form.model,
        year: form.year ? Number(form.year) : undefined,
      });
      setForm({
        vehicle_name: "",
        company: "",
        vehicle_type: "",
        model: "",
        year: "",
      });
      setShowAddModal(false);
      await refreshVehicles();
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : "Failed to add vehicle"
      );
    } finally {
      setSaving(false);
    }
  }

  async function onDeleteVehicle(vehicleId: string) {
    if (!confirm("Are you sure you want to delete this vehicle?")) return;
    try {
      await deleteVehicle(vehicleId);
      await refreshVehicles();
    } catch (err) {
      alert("Failed to delete vehicle.");
      console.error(err);
    }
  }

  return (
    <>
      {/* ─── Navigation Bar ─── */}
      <nav className={styles.navBar}>
        <div className={styles.navLeft}>
          <div className={styles.navLogo}>
            <Zap strokeWidth={2.5} />
          </div>
          <span className={styles.navTitle}>
            Auto<span className={styles.navTitleAccent}>AI</span>
          </span>
        </div>
        <div className={styles.navRight}>
          <div className={styles.navStatus}>
            <span className={styles.statusDot} />
            <span className="mono">System Online</span>
          </div>
          <UserButton
            appearance={{
              elements: {
                avatarBox: {
                  width: "34px",
                  height: "34px",
                },
              },
            }}
          />
        </div>
      </nav>

      {/* ─── Main Content ─── */}
      <main className={styles.shell}>
        {/* Hero */}
        <motion.section
          className={styles.hero}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className={styles.heroText}>
            <p className={`${styles.heroGreeting} mono`}>Control Room</p>
            <h1 className={styles.heroName}>
              <span className={styles.heroNameGradient}>
                Welcome back, {user?.firstName ?? "Driver"}
              </span>
            </h1>
            <p className={styles.heroSubtitle}>
              Manage your fleet, monitor real-time diagnostics, and track
              predictive maintenance across all your vehicles.
            </p>
          </div>
          <div className={styles.heroActions}>
            <button
              className={styles.btnPrimary}
              onClick={() => setShowAddModal(true)}
            >
              <Plus size={18} />
              Add Vehicle
            </button>
            <SignOutButton>
              <button className={styles.btnSecondary}>Sign Out</button>
            </SignOutButton>
          </div>
        </motion.section>

        {/* Load Error */}
        {loadError ? (
          <div className={styles.loadError}>
            <AlertTriangle size={18} />
            Backend not reachable. Please start backend services.
          </div>
        ) : null}

        {/* Stats Row */}
        <div className={styles.statsRow}>
          {[
            {
              label: "Total Vehicles",
              value: myVehicles.length,
              accent: styles.statAccentIndigo,
              footnote: "in your fleet",
            },
            {
              label: "Active Pipeline",
              value: activeVehicles.length,
              accent: styles.statAccentCyan,
              footnote: "currently processing",
            },
            {
              label: "Active Issues",
              value: issueVehicles.length,
              accent: styles.statAccentAmber,
              footnote: "require attention",
            },
            {
              label: "System Health",
              value: 100 - issueVehicles.length * 12,
              accent: styles.statAccentEmerald,
              footnote: "% operational",
            },
          ].map((stat, i) => (
            <motion.div
              key={stat.label}
              className={`${styles.statCard} ${stat.accent}`}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 + i * 0.07, duration: 0.45 }}
            >
              <p className={`${styles.statLabel} mono`}>{stat.label}</p>
              <p className={styles.statValue}>
                <AnimatedNumber value={Math.max(0, stat.value)} />
              </p>
              <p className={styles.statFootnote}>{stat.footnote}</p>
            </motion.div>
          ))}
        </div>

        {/* Content Grid */}
        <div className={styles.contentGrid}>
          {/* My Fleet */}
          <section className={styles.panel}>
            <div className={styles.panelHeader}>
              <h2 className={styles.panelTitle}>My Fleet</h2>
              <span className={`${styles.panelCount} mono`}>
                {myVehicles.length} vehicles
              </span>
            </div>

            {loading ? (
              <div className={styles.empty}>
                <div className={styles.emptyIcon}>
                  <Activity />
                </div>
                <p>Loading your vehicles...</p>
              </div>
            ) : myVehicles.length === 0 ? (
              <div className={styles.empty}>
                <div className={styles.emptyIcon}>
                  <Car />
                </div>
                <p>
                  No vehicles yet. Click &quot;Add Vehicle&quot; to register
                  your first vehicle to the system.
                </p>
              </div>
            ) : (
              <div className={styles.vehicleGrid}>
                {myVehicles.map((vehicle, i) => {
                  const hasIssue =
                    vehicle.risk_state?.high_risk_active ||
                    (vehicle.risk_state?.unresolved_issues?.length ?? 0) > 0;
                  const stage = getStageDisplay(
                    vehicle.workflow_state?.current_stage
                  );

                  return (
                    <motion.article
                      key={vehicle.vehicle_id}
                      className={styles.vehicleCard}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{
                        delay: 0.1 + i * 0.05,
                        duration: 0.4,
                      }}
                    >
                      <div className={styles.vehicleCardTop}>
                        <h3>
                          {vehicle.vehicle_profile?.name ?? vehicle.vehicle_id}
                        </h3>
                        <span
                          className={`${styles.badge} ${hasIssue ? styles.badgeBad : styles.badgeOk}`}
                        >
                          {hasIssue ? (
                            <AlertTriangle size={16} />
                          ) : (
                            <Shield size={16} />
                          )}
                        </span>
                      </div>

                      <div className={styles.vehicleMeta}>
                        <div className={styles.metaRow}>
                          <span className={`${styles.metaLabel} mono`}>
                            Company
                          </span>
                          <span className={styles.metaValue}>
                            {vehicle.vehicle_profile?.company ?? "Unknown"}
                          </span>
                        </div>
                        <div className={styles.metaRow}>
                          <span className={`${styles.metaLabel} mono`}>
                            Model
                          </span>
                          <span className={styles.metaValue}>
                            {vehicle.vehicle_profile?.model ?? "Unknown"}
                          </span>
                        </div>
                        <div className={styles.metaRow}>
                          <span className={`${styles.metaLabel} mono`}>
                            ID
                          </span>
                          <span className={styles.metaValue}>
                            {vehicle.vehicle_id}
                          </span>
                        </div>
                      </div>

                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                        }}
                      >
                        <span className={`${styles.stageBadge} ${stage.cls}`}>
                          {stage.label}
                        </span>
                        <div style={{ display: "flex", gap: "8px" }}>
                          <button
                            className={styles.openBtn}
                            style={{ color: "#f87171", borderColor: "rgba(248, 113, 113, 0.3)" }}
                            onClick={(e) => {
                              e.preventDefault();
                              onDeleteVehicle(vehicle.vehicle_id);
                            }}
                            title="Delete Vehicle"
                          >
                            <Trash2 size={14} />
                          </button>
                          <Link
                            className={styles.openBtn}
                            href={`/vehicle/${vehicle.vehicle_id}`}
                          >
                            Open <ChevronRight size={14} />
                          </Link>
                        </div>
                      </div>
                    </motion.article>
                  );
                })}
              </div>
            )}
          </section>

          {/* Active Issues */}
          <section className={styles.panel}>
            <div className={styles.panelHeader}>
              <h2 className={styles.panelTitle}>Active Issues</h2>
              <span className={`${styles.panelCount} mono`}>
                {issueVehicles.length}
              </span>
            </div>

            {issueVehicles.length === 0 ? (
              <div className={styles.empty}>
                <div className={styles.emptyIcon}>
                  <Shield />
                </div>
                <p>All clear — no active issues across your fleet.</p>
              </div>
            ) : (
              <div className={styles.issueList}>
                {issueVehicles.map((vehicle, i) => (
                  <motion.article
                    key={vehicle.vehicle_id}
                    className={styles.issueItem}
                    initial={{ opacity: 0, x: 12 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.2 + i * 0.06 }}
                  >
                    <h4>
                      {vehicle.vehicle_profile?.name ?? vehicle.vehicle_id}
                    </h4>
                    <p>
                      {(vehicle.risk_state?.unresolved_issues ?? [])
                        .slice(0, 2)
                        .join("; ") ||
                        "High risk detected. Immediate review recommended."}
                    </p>
                    <Link
                      className={styles.openBtn}
                      href={`/vehicle/${vehicle.vehicle_id}`}
                    >
                      View Details <ArrowRight size={14} />
                    </Link>
                  </motion.article>
                ))}
              </div>
            )}
          </section>
        </div>
      </main>

      {/* ─── Add Vehicle Modal ─── */}
      <AnimatePresence>
        {showAddModal ? (
          <div
            className={styles.modalBackdrop}
            role="dialog"
            aria-modal="true"
            onClick={(e) => {
              if (e.target === e.currentTarget) setShowAddModal(false);
            }}
          >
            <div className={styles.modalCard}>
              <div className={styles.modalHeader}>
                <h3>Register New Vehicle</h3>
                <button
                  className={styles.closeBtn}
                  onClick={() => setShowAddModal(false)}
                  aria-label="Close"
                >
                  <X size={18} />
                </button>
              </div>

              <form className={styles.formGrid} onSubmit={onAddVehicle}>
                <label>
                  Vehicle Name *
                  <input
                    value={form.vehicle_name}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, vehicle_name: e.target.value }))
                    }
                    placeholder="e.g. Family SUV"
                  />
                </label>

                <div className={styles.formRow}>
                  <label>
                    Company *
                    <input
                      value={form.company}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, company: e.target.value }))
                      }
                      placeholder="e.g. Toyota"
                    />
                  </label>
                  <label>
                    Model *
                    <input
                      value={form.model}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, model: e.target.value }))
                      }
                      placeholder="e.g. Fortuner"
                    />
                  </label>
                </div>

                <div className={styles.formRow}>
                  <label>
                    Vehicle Type *
                    <input
                      value={form.vehicle_type}
                      onChange={(e) =>
                        setForm((p) => ({
                          ...p,
                          vehicle_type: e.target.value,
                        }))
                      }
                      placeholder="e.g. SUV"
                    />
                  </label>
                  <label>
                    Year
                    <input
                      value={form.year}
                      onChange={(e) =>
                        setForm((p) => ({ ...p, year: e.target.value }))
                      }
                      placeholder="e.g. 2024"
                      type="number"
                    />
                  </label>
                </div>

                {formError ? (
                  <p className={styles.formError}>{formError}</p>
                ) : null}

                <button
                  className={styles.submitBtn}
                  type="submit"
                  disabled={saving}
                >
                  {saving ? "Registering..." : "Register Vehicle"}
                </button>
              </form>
            </div>
          </div>
        ) : null}
      </AnimatePresence>
    </>
  );
}
