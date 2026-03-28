import { SignIn } from "@clerk/nextjs";
import { Zap, Shield, BarChart3 } from "lucide-react";
import styles from "./page.module.css";

export default function SignInPage() {
  return (
    <main className={styles.shell}>
      {/* ─── Left: Branding ─── */}
      <section className={styles.brandPanel}>
        {/* Floating orbs */}
        <div className={`${styles.orb} ${styles.orb1}`} />
        <div className={`${styles.orb} ${styles.orb2}`} />
        <div className={`${styles.orb} ${styles.orb3}`} />

        <div className={styles.brandContent}>
          <div className={styles.logoMark}>
            <Zap strokeWidth={2.5} />
          </div>

          <h1 className={styles.brandTitleHero}>
            <span className={styles.brandTitleGradient}>AutoAI</span>
          </h1>
          <p className={styles.brandSubtitle}>Control Room</p>

          <p className={styles.brandTaglineHero}>
            Autonomous vehicle lifecycle orchestration — from telemetry
            ingestion to predictive maintenance, powered by multi-agent
            intelligence.
          </p>

          <ul className={styles.featureList}>
            <li className={styles.featureItem}>
              <span className={styles.featureIcon}>
                <Zap />
              </span>
              <div className={styles.featureText}>
                <h3 className={styles.featureTextTitle}>Multi-Agent Orchestration</h3>
                <p className={styles.featureTextDesc}>
                  Six autonomous agents coordinate decisions across sharded
                  pipelines with real-time lifecycle gating.
                </p>
              </div>
            </li>
            <li className={styles.featureItem}>
              <span className={styles.featureIcon}>
                <Shield />
              </span>
              <div className={styles.featureText}>
                <h3 className={styles.featureTextTitle}>Predictive Diagnostics</h3>
                <p className={styles.featureTextDesc}>
                  Isolation Forest ML model detects anomalies and scores risk
                  in real-time across your fleet.
                </p>
              </div>
            </li>
            <li className={styles.featureItem}>
              <span className={styles.featureIcon}>
                <BarChart3 />
              </span>
              <div className={styles.featureText}>
                <h3 className={styles.featureTextTitle}>Live Observability</h3>
                <p className={styles.featureTextDesc}>
                  WebSocket-driven activity streams, queue health monitors,
                  and AI-generated journey summaries.
                </p>
              </div>
            </li>
          </ul>
        </div>
      </section>

      {/* ─── Right: Auth ─── */}
      <section className={styles.authPanel}>
        <div className={styles.authCard}>
          <div className={styles.authHeader}>
            <h2>Welcome back</h2>
            <p>Sign in to access your control room</p>
          </div>
          <SignIn
            appearance={{
              elements: {
                headerTitle: { display: "none" },
                headerSubtitle: { display: "none" },
                formButtonPrimary: {
                  backgroundColor: "#6366f1",
                  border: "none",
                  color: "#ffffff",
                  fontWeight: "600",
                  fontSize: "15px",
                  borderRadius: "8px",
                  padding: "12px 0",
                },
                formFieldInput: {
                  backgroundColor: "#0f172a",
                  borderColor: "rgba(255, 255, 255, 0.2)",
                  borderRadius: "8px",
                  color: "#ffffff",
                  fontSize: "15px",
                  padding: "14px",
                },
                formFieldLabel: {
                  color: "#f8fafc",
                  fontSize: "14px",
                  fontWeight: "600",
                },
                socialButtonsBlockButton: {
                  backgroundColor: "#0f172a",
                  borderColor: "rgba(255, 255, 255, 0.1)",
                  color: "#ffffff",
                },
                socialButtonsBlockButtonText: {
                  color: "#ffffff",
                },
                dividerLine: {
                  backgroundColor: "rgba(255, 255, 255, 0.1)",
                },
                dividerText: {
                  color: "#94a3b8",
                  background: "transparent",
                },
                footerActionLink: {
                  color: "#818cf8",
                  fontWeight: "600",
                },
                footerActionText: {
                  color: "#94a3b8",
                },
                identityPreviewText: {
                  color: "#ffffff",
                },
                identityPreviewEditButton: {
                  color: "#818cf8",
                }
              },
            }}
          />
        </div>
      </section>

      {/* ─── Bottom ─── */}
      <footer className={styles.bottomBar}>
        <span>© 2026 AutoAI — EY Hackathon</span>
        <span>Built with multi-agent intelligence</span>
      </footer>
    </main>
  );
}
