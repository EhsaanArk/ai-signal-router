import { Link } from "react-router-dom";
import { APP_NAME } from "@/lib/constants";
import { usePageTitle } from "@/hooks/use-page-title";

export function TermsPage() {
  usePageTitle("Terms of Service");

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

        <h1 className="text-3xl font-bold mb-2">Terms of Service</h1>
        <p className="text-sm text-muted-foreground mb-8">
          Last updated: March 22, 2026
        </p>

        <div className="prose prose-invert prose-sm max-w-none space-y-6">
          <section>
            <h2 className="text-xl font-semibold mb-3">1. Acceptance of Terms</h2>
            <p className="text-muted-foreground leading-relaxed">
              By accessing or using {APP_NAME} ("the Service"), operated by Sage Intelligence ("we", "us", "our"),
              you agree to be bound by these Terms of Service. If you do not agree to these terms,
              do not use the Service.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">2. Description of Service</h2>
            <p className="text-muted-foreground leading-relaxed">
              {APP_NAME} is a cloud-based signal routing service that intercepts trading signals from
              Telegram channels, parses them using artificial intelligence, and dispatches structured
              webhook payloads to third-party trading platforms configured by the user. The Service
              acts as a middleware bridge — it does not execute, place, or manage trades directly.
              The user is solely responsible for configuring their destination platform and webhook URLs.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">3. Not a Broker, Dealer, or Financial Institution</h2>
            <p className="text-muted-foreground leading-relaxed">
              {APP_NAME} is a software tool, not a broker, dealer, investment advisor, or financial
              institution. We are not registered with any financial regulatory authority. We do not:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li>Hold, manage, or have access to your trading accounts or funds.</li>
              <li>Execute, place, modify, or cancel trades on your behalf.</li>
              <li>Provide financial advice, investment recommendations, or trading signals.</li>
              <li>Guarantee any trading outcomes or returns.</li>
            </ul>
            <p className="text-muted-foreground leading-relaxed mt-2">
              The Service merely relays and routes signals from third-party Telegram channels that
              you choose to connect. We do not endorse, verify, or guarantee the accuracy,
              profitability, or suitability of any trading signal processed through our platform.
              All trading decisions are made by you and the third-party platforms you configure.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">4. Risk Disclaimer</h2>
            <p className="text-muted-foreground leading-relaxed">
              Trading in financial markets involves substantial risk of loss and is not suitable
              for all investors. By using this Service, you acknowledge and accept that:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li>Past performance of any signal provider does not guarantee future results.</li>
              <li>You may lose some or all of your invested capital.</li>
              <li>You are solely responsible for any trading decisions and their outcomes, including trades initiated by webhooks dispatched through this Service.</li>
              <li>AI-based signal parsing may occasionally misinterpret signals, leading to incorrect trade parameters being dispatched.</li>
              <li>Service interruptions, network delays, or technical failures may cause missed, delayed, or duplicated signal dispatches.</li>
              <li>The Service does not verify whether a signal provider is licensed, qualified, or trustworthy.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">5. Beta Service Disclaimer</h2>
            <p className="text-muted-foreground leading-relaxed">
              The Service is currently in <strong>Beta</strong>. Beta features are provided "as-is" and
              "as-available" without warranties of any kind, either express or implied. Beta features
              may contain bugs, errors, or inaccuracies. We make no guarantees about the reliability,
              availability, or accuracy of the Service during the Beta period. You use the Beta
              Service at your own risk.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">6. Limitation of Liability</h2>
            <p className="text-muted-foreground leading-relaxed">
              To the maximum extent permitted by applicable law, {APP_NAME} and its operators shall
              not be liable for any direct, indirect, incidental, special, consequential, or
              punitive damages, including but not limited to loss of profits, trading losses,
              data loss, or other intangible losses, resulting from:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li>Your use or inability to use the Service.</li>
              <li>Any signals parsed, routed, missed, duplicated, or incorrectly interpreted by the Service.</li>
              <li>Any trades executed or not executed by third-party platforms as a result of webhooks dispatched by this Service.</li>
              <li>Unauthorized access to or alteration of your data or transmissions.</li>
              <li>Any interruption or cessation of the Service.</li>
              <li>Actions or omissions of any third-party signal provider, trading platform, or broker.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">7. Indemnification</h2>
            <p className="text-muted-foreground leading-relaxed">
              You agree to indemnify, defend, and hold harmless {APP_NAME}, its operators, affiliates,
              officers, and employees from and against any claims, liabilities, damages, losses, costs,
              or expenses (including reasonable legal fees) arising out of or related to:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li>Your use of the Service.</li>
              <li>Trading losses or financial damages resulting from signals routed through the Service.</li>
              <li>Your violation of these Terms or any applicable law or regulation.</li>
              <li>Your violation of any third party's rights, including signal providers or trading platforms.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">8. Eligibility</h2>
            <p className="text-muted-foreground leading-relaxed">
              You must be at least 18 years of age to use this Service. By using the Service, you
              represent and warrant that you are at least 18 years old and have the legal capacity
              to enter into these Terms. You are responsible for ensuring that your use of the Service
              complies with the laws and regulations of your jurisdiction, including any restrictions
              on trading in financial markets.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">9. User Responsibilities</h2>
            <p className="text-muted-foreground leading-relaxed">You agree to:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li>Provide accurate account information and keep it up to date.</li>
              <li>Maintain the security of your account credentials.</li>
              <li>Use the Service in compliance with all applicable laws and regulations.</li>
              <li>Verify the accuracy of parsed signals before relying on them for trading decisions.</li>
              <li>Not use the Service for any illegal or unauthorized purpose.</li>
              <li>Not attempt to reverse-engineer, decompile, or exploit the Service.</li>
              <li>Not share your account credentials with third parties.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">10. Telegram Integration</h2>
            <p className="text-muted-foreground leading-relaxed">
              To use the Service, you must connect your personal Telegram account. By doing so,
              you acknowledge that:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li>You authorize {APP_NAME} to access messages in the Telegram channels you select for monitoring.</li>
              <li>Your Telegram session data is encrypted at rest using AES-256-GCM encryption.</li>
              <li>We will only read messages from channels you explicitly configure for signal routing.</li>
              <li>You are responsible for complying with Telegram's Terms of Service.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">11. Subscription and Billing</h2>
            <p className="text-muted-foreground leading-relaxed">
              {APP_NAME} offers tiered subscription plans. The Service is currently in Beta and
              available at no cost. Pricing and billing terms will be communicated prior to any
              transition to paid plans. Your continued use of the Service after such notification
              constitutes acceptance of the applicable fees.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">12. Service Availability</h2>
            <p className="text-muted-foreground leading-relaxed">
              We strive to maintain high availability but do not guarantee uninterrupted access.
              The Service may be temporarily unavailable due to maintenance, updates, or
              circumstances beyond our control. We are not liable for any losses resulting from
              service downtime, including missed trading signals.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">13. Termination</h2>
            <p className="text-muted-foreground leading-relaxed">
              We reserve the right to suspend or terminate your account at any time, with or
              without cause, with or without notice. You may delete your account at any time
              through the Settings page. Upon termination, your data will be deleted in
              accordance with our Privacy Policy.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">14. Changes to Terms</h2>
            <p className="text-muted-foreground leading-relaxed">
              We may update these Terms from time to time. We will notify you of material changes
              via email or through the Service. Your continued use after changes take effect
              constitutes acceptance of the updated Terms.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">15. Governing Law</h2>
            <p className="text-muted-foreground leading-relaxed">
              These Terms shall be governed by and construed in accordance with the laws of
              the jurisdiction in which Sage Intelligence operates, without regard to conflict of law
              principles.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">16. Contact</h2>
            <p className="text-muted-foreground leading-relaxed">
              For questions about these Terms, contact us at{" "}
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

export default TermsPage;
