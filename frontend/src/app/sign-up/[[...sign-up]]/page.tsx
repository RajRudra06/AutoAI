import { SignUp } from "@clerk/nextjs";
import { Zap } from "lucide-react";
import styles from "@/app/sign-in/[[...sign-in]]/page.module.css";

export default function SignUpPage() {
  return (
    <main className={styles.shell}>
      {/* ─── Left: Branding ─── */}
      <section className={styles.brandPanel}>
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
            Join the autonomous vehicle lifecycle platform. Register your fleet
            and start monitoring predictive diagnostics in real-time.
          </p>
        </div>
      </section>

      {/* ─── Right: Auth ─── */}
      <section className={styles.authPanel}>
        <div className={styles.authCard}>
          <div className={styles.authHeader}>
            <h2>Create an account</h2>
            <p>Sign up to start your journey</p>
          </div>
          <SignUp
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

      <footer className={styles.bottomBar}>
        <span>© 2026 AutoAI — EY Hackathon</span>
        <span>Built with multi-agent intelligence</span>
      </footer>
    </main>
  );
}
