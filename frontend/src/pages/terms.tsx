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
              {APP_NAME} is a cloud-based <strong>message routing</strong> service. It reads messages from
              Telegram channels that you choose to connect, attempts to extract structured data from
              those messages using artificial intelligence (best-effort, not guaranteed), and dispatches
              the structured data as webhook payloads to destination URLs that you configure.
            </p>
            <p className="text-muted-foreground leading-relaxed mt-2">
              The Service is a <strong>middleware tool</strong>. It does not control, verify, or take
              responsibility for the content of the messages it processes, the accuracy of the AI
              parsing, or the actions taken by any destination platform that receives the webhook.
              The user is solely responsible for choosing which channels to monitor, which destination
              URLs to configure, and what happens at those destinations.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">3. Not a Trading Platform, Broker, or Financial Institution</h2>
            <p className="text-muted-foreground leading-relaxed">
              {APP_NAME} is <strong>not</strong> a trading platform, broker, dealer, investment advisor,
              or financial institution. We are not registered with any financial regulatory authority
              in any jurisdiction. We do not:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li>Hold, manage, or have access to your trading accounts, funds, or broker credentials.</li>
              <li>Execute, place, modify, or cancel trades on your behalf. We only dispatch webhook messages.</li>
              <li>Provide financial advice, investment recommendations, or trading signals of any kind.</li>
              <li>Guarantee any trading outcomes, returns, or the accuracy of any parsed data.</li>
              <li>Verify, endorse, or take responsibility for any signal provider, channel, or message content.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">4. Content Disclaimer</h2>
            <p className="text-muted-foreground leading-relaxed">
              The Service processes messages from Telegram channels selected by you. We have
              <strong> no control</strong> over the content, accuracy, legality, or quality of these
              messages. Messages may contain inaccurate, misleading, or harmful information. The
              Service routes messages as-is after AI parsing — we do not verify, filter, or endorse
              any message content.
            </p>
            <p className="text-muted-foreground leading-relaxed mt-2">
              You are solely responsible for evaluating the source, quality, and reliability of any
              channel you connect. We strongly recommend reviewing parsed outputs before relying on
              them for any purpose, including but not limited to financial decisions.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">5. Risk Acknowledgement</h2>
            <p className="text-muted-foreground leading-relaxed">
              If you use this Service to route messages related to financial trading, you acknowledge
              and accept that:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li>Trading in financial markets involves substantial risk of loss and is not suitable for all individuals.</li>
              <li>You may lose some or all of your invested capital.</li>
              <li>You are solely responsible for any decisions and their outcomes, including any actions triggered by webhooks dispatched through this Service.</li>
              <li>AI-based parsing is best-effort and may produce incorrect, incomplete, or misinterpreted data.</li>
              <li>Service interruptions, software bugs, network delays, or technical failures may cause missed, delayed, duplicated, or incorrect webhook dispatches.</li>
              <li>The Service does not verify whether any message source is licensed, qualified, regulated, or trustworthy.</li>
              <li>Past performance of any signal provider does not guarantee future results.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">6. Disclaimer of Warranties</h2>
            <p className="text-muted-foreground leading-relaxed">
              The Service is provided <strong>"AS-IS"</strong> and <strong>"AS-AVAILABLE"</strong> without
              warranties of any kind, whether express, implied, or statutory, including but not limited
              to implied warranties of merchantability, fitness for a particular purpose, accuracy,
              and non-infringement.
            </p>
            <p className="text-muted-foreground leading-relaxed mt-2">
              We do not warrant that the Service will be uninterrupted, error-free, secure, or free
              of bugs or defects. The Service is currently in <strong>Beta</strong> and may contain
              errors, inaccuracies, or failures. You use the Service entirely at your own risk.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">7. Limitation of Liability</h2>
            <p className="text-muted-foreground leading-relaxed">
              To the maximum extent permitted by applicable law, {APP_NAME}, its operators, affiliates,
              officers, employees, and agents shall <strong>not be liable</strong> for any direct, indirect,
              incidental, special, consequential, or punitive damages, including but not limited to loss
              of profits, trading losses, data loss, or other intangible losses, resulting from:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li>Your use or inability to use the Service.</li>
              <li>Any data parsed, routed, missed, duplicated, or incorrectly interpreted by the Service.</li>
              <li>Any actions taken or not taken by any third-party platform receiving webhooks from this Service.</li>
              <li>Any content in messages processed by the Service.</li>
              <li>Unauthorized access to or alteration of your data or transmissions.</li>
              <li>Any interruption, downtime, or cessation of the Service for any reason.</li>
              <li>Software bugs, AI parsing errors, or technical failures of any kind.</li>
              <li>Actions or omissions of any third-party, including signal providers, trading platforms, or brokers.</li>
            </ul>
            <p className="text-muted-foreground leading-relaxed mt-2">
              In no event shall our total aggregate liability exceed the amount you have paid us for
              the Service in the twelve (12) months preceding the claim, or fifty US dollars (USD $50),
              whichever is greater.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">8. Indemnification</h2>
            <p className="text-muted-foreground leading-relaxed">
              You agree to indemnify, defend, and hold harmless {APP_NAME}, its operators, affiliates,
              officers, and employees from and against any claims, liabilities, damages, losses, costs,
              or expenses (including reasonable legal fees) arising out of or related to:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li>Your use of the Service.</li>
              <li>Any losses, damages, or disputes resulting from webhook messages dispatched through the Service.</li>
              <li>Your violation of these Terms or any applicable law or regulation.</li>
              <li>Your violation of any third party's rights.</li>
              <li>Any content in the Telegram channels you connect to the Service.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">9. Eligibility</h2>
            <p className="text-muted-foreground leading-relaxed">
              You must be at least 18 years of age to use this Service. By using the Service, you
              represent and warrant that you are at least 18 years old and have the legal capacity
              to enter into these Terms. You are responsible for ensuring that your use of the Service
              complies with the laws and regulations of your jurisdiction.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">10. User Responsibilities</h2>
            <p className="text-muted-foreground leading-relaxed">You agree to:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li>Provide accurate account information and keep it up to date.</li>
              <li>Maintain the security of your account credentials.</li>
              <li>Use the Service in compliance with all applicable laws and regulations.</li>
              <li>Review and verify any parsed data before relying on it for any purpose.</li>
              <li>Accept full responsibility for the configuration of your webhook destinations.</li>
              <li>Not use the Service for any illegal or unauthorized purpose.</li>
              <li>Not attempt to reverse-engineer, decompile, or exploit the Service.</li>
              <li>Not share your account credentials with third parties.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">11. Telegram Integration</h2>
            <p className="text-muted-foreground leading-relaxed">
              To use the Service, you must connect your personal Telegram account. By doing so,
              you acknowledge that:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1 text-muted-foreground">
              <li>You authorize {APP_NAME} to read messages in the Telegram channels you select for monitoring.</li>
              <li>Your Telegram session data is encrypted at rest using AES-256-GCM encryption.</li>
              <li>We will only read messages from channels you explicitly configure.</li>
              <li>You are responsible for complying with Telegram's Terms of Service.</li>
              <li>We are not affiliated with Telegram and are not responsible for Telegram's availability or policies.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">12. Subscription and Billing</h2>
            <p className="text-muted-foreground leading-relaxed">
              {APP_NAME} offers tiered subscription plans. The Service is currently in Beta and
              available at no cost. Pricing and billing terms will be communicated prior to any
              transition to paid plans. Your continued use of the Service after such notification
              constitutes acceptance of the applicable fees.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">13. Service Availability</h2>
            <p className="text-muted-foreground leading-relaxed">
              We do not guarantee uninterrupted, continuous, or error-free access to the Service.
              The Service may be unavailable due to maintenance, updates, technical failures,
              third-party service outages, or circumstances beyond our control. We are not liable
              for any losses or damages resulting from service downtime or unavailability.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">14. Termination</h2>
            <p className="text-muted-foreground leading-relaxed">
              We reserve the right to suspend or terminate your account at any time, with or
              without cause, with or without notice. You may delete your account at any time
              through the Settings page. Upon termination, your data will be deleted in
              accordance with our Privacy Policy.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">15. Dispute Resolution</h2>
            <p className="text-muted-foreground leading-relaxed">
              Any dispute arising from these Terms or your use of the Service shall first be
              attempted to be resolved through good-faith negotiation. If the dispute cannot
              be resolved within thirty (30) days, it shall be submitted to binding arbitration
              in accordance with the rules of the jurisdiction in which Sage Intelligence operates.
              You agree to waive any right to a jury trial or to participate in a class action
              lawsuit against {APP_NAME}.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">16. Changes to Terms</h2>
            <p className="text-muted-foreground leading-relaxed">
              We may update these Terms from time to time. We will notify you of material changes
              via email or through the Service. Your continued use after changes take effect
              constitutes acceptance of the updated Terms.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">17. Governing Law</h2>
            <p className="text-muted-foreground leading-relaxed">
              These Terms shall be governed by and construed in accordance with the laws of
              the British Virgin Islands, without regard to conflict of law principles.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3">18. Contact</h2>
            <p className="text-muted-foreground leading-relaxed">
              For questions about these Terms, contact us at{" "}
              <a href="mailto:support@sageintelligence.io" className="text-primary hover:underline">
                support@sageintelligence.io
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
