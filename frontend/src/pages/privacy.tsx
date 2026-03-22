import { Link } from "react-router-dom";
import { APP_NAME } from "@/lib/constants";
import { usePageTitle } from "@/hooks/use-page-title";

export function PrivacyPage() {
  usePageTitle("Privacy Policy");

  return (
    <div className="dark min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-3xl px-4 py-12">
        <div className="mb-8">
          <Link
            to="/"
            className="text-sm text-muted-foreground hover:text-primary transition-colors"
          >
            &larr; Back to {APP_NAME}
          </Link>
        </div>

        <h1 className="text-3xl font-bold mb-2">Privacy Policy</h1>
        <p className="text-sm text-muted-foreground mb-8">
          Last updated: March 22, 2026
        </p>

        <div className="prose prose-invert prose-sm max-w-none space-y-6">
          <section>
            <h2 className="text-xl font-semibold mb-3">1. Introduction</h2>
            <p className="text-muted-foreground leading-relaxed">
              {APP_NAME} ("the Service"), operated by SageMaster ("we", "us", "our"), is committed
              to protecting your privacy. This Privacy Policy explains how we collect, use, store,
              and protect your personal data when you use our Service.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">2. Data We Collect</h2>

            <h3 className="text-lg font-medium mt-4 mb-2">2.1 Account Data</h3>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li><strong>Email address</strong> — used for authentication, account recovery, and service communications.</li>
              <li><strong>Hashed password</strong> — stored using bcrypt; we never store plain-text passwords.</li>
              <li><strong>Account creation timestamp</strong> — for account management.</li>
            </ul>

            <h3 className="text-lg font-medium mt-4 mb-2">2.2 Telegram Data</h3>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li><strong>Telegram session string</strong> — encrypted at rest using AES-256-GCM encryption. Used to maintain your Telegram connection for signal monitoring.</li>
              <li><strong>Telegram phone number</strong> — used only during the authentication handshake. Not stored after connection.</li>
              <li><strong>Channel messages</strong> — from channels you configure for monitoring. Messages are processed in real-time for signal extraction and are not permanently stored in raw form.</li>
            </ul>

            <h3 className="text-lg font-medium mt-4 mb-2">2.3 Signal & Routing Data</h3>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li><strong>Parsed signal data</strong> — extracted trading parameters (symbol, direction, entry, SL, TP).</li>
              <li><strong>Routing configurations</strong> — your webhook URLs, symbol mappings, and risk settings.</li>
              <li><strong>Signal logs</strong> — records of signals processed, including status (success, failed, ignored) and timestamps.</li>
              <li><strong>SageMaster webhook URLs</strong> — stored to route signals to your SageMaster accounts.</li>
            </ul>

            <h3 className="text-lg font-medium mt-4 mb-2">2.4 Technical Data</h3>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li><strong>IP address</strong> — for rate limiting and security.</li>
              <li><strong>Error logs</strong> — sent to Sentry for monitoring and debugging (no personal data included).</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">3. How We Use Your Data</h2>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li>To provide and maintain the signal routing Service.</li>
              <li>To authenticate your identity and manage your account.</li>
              <li>To send service-related communications (verification emails, password resets).</li>
              <li>To monitor and improve Service reliability and performance.</li>
              <li>To detect and prevent abuse, fraud, and unauthorized access.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">4. Legal Basis for Processing (GDPR)</h2>
            <p className="text-muted-foreground leading-relaxed">
              We process your personal data under the following legal bases:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li><strong>Contract performance</strong> — processing necessary to provide the Service you signed up for (account data, signal routing, Telegram connection).</li>
              <li><strong>Legitimate interest</strong> — security monitoring, error logging, and service improvement.</li>
              <li><strong>Consent</strong> — where explicitly provided (e.g., accepting these terms at registration).</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">5. Data Storage & Security</h2>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li>All data is stored on secure cloud infrastructure (Railway, PostgreSQL).</li>
              <li>Telegram session strings are encrypted using <strong>AES-256-GCM</strong> with per-user encryption keys.</li>
              <li>Passwords are hashed using <strong>bcrypt</strong> and never stored in plain text.</li>
              <li>All API communication uses HTTPS/TLS encryption in transit.</li>
              <li>Access to production systems is restricted to authorized personnel only.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">6. Data Sharing</h2>
            <p className="text-muted-foreground leading-relaxed">
              We do not sell, trade, or rent your personal data. We may share data with:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li><strong>SageMaster</strong> — trading signals are routed to your SageMaster webhook URLs as configured by you.</li>
              <li><strong>OpenAI</strong> — signal text is sent to OpenAI's API for AI parsing. OpenAI's data usage policy applies.</li>
              <li><strong>Sentry</strong> — error data (no personal information) for monitoring.</li>
              <li><strong>Resend</strong> — email addresses for transactional email delivery.</li>
              <li><strong>Law enforcement</strong> — only when required by law or valid legal process.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">7. Your Rights (GDPR)</h2>
            <p className="text-muted-foreground leading-relaxed">
              Under GDPR and applicable data protection laws, you have the right to:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li><strong>Access</strong> — request a copy of all data we hold about you (available via Settings &gt; Export Data).</li>
              <li><strong>Rectification</strong> — request correction of inaccurate data.</li>
              <li><strong>Erasure</strong> — request deletion of your account and all associated data (available via Settings &gt; Delete Account).</li>
              <li><strong>Data portability</strong> — receive your data in a structured, machine-readable format (JSON export).</li>
              <li><strong>Withdraw consent</strong> — at any time, by deleting your account.</li>
            </ul>
            <p className="text-muted-foreground leading-relaxed mt-2">
              To exercise any of these rights, use the in-app features in Settings or contact us at{" "}
              <a href="mailto:support@sagemaster.com" className="text-primary hover:underline">
                support@sagemaster.com
              </a>
              .
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">8. Data Retention</h2>
            <ul className="list-disc pl-6 space-y-1 text-muted-foreground">
              <li><strong>Account data</strong> — retained for the lifetime of your account.</li>
              <li><strong>Signal logs</strong> — retained for 90 days, then automatically purged.</li>
              <li><strong>Telegram session data</strong> — retained while your Telegram connection is active. Deleted immediately when you disconnect.</li>
              <li><strong>Upon account deletion</strong> — all data is permanently deleted within 30 days.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">9. Cookies</h2>
            <p className="text-muted-foreground leading-relaxed">
              {APP_NAME} uses only essential cookies and local storage for authentication (JWT tokens)
              and user preferences. We do not use tracking cookies, advertising cookies, or
              third-party analytics cookies.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">10. Children's Privacy</h2>
            <p className="text-muted-foreground leading-relaxed">
              The Service is not intended for use by individuals under 18 years of age. We do not
              knowingly collect personal data from minors.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">11. Changes to This Policy</h2>
            <p className="text-muted-foreground leading-relaxed">
              We may update this Privacy Policy from time to time. We will notify you of material
              changes via email or through the Service. The "Last updated" date at the top of this
              page indicates when the policy was last revised.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">12. Contact</h2>
            <p className="text-muted-foreground leading-relaxed">
              For questions about this Privacy Policy or your personal data, contact us at{" "}
              <a href="mailto:support@sagemaster.com" className="text-primary hover:underline">
                support@sagemaster.com
              </a>
              .
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

export default PrivacyPage;
