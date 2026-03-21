import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";

const PROD_URL = "https://app.radar.sagemaster.com";

/**
 * Full-page redirect notice shown to non-admin users on the staging environment.
 * Staging is detected by hostname containing "staging" or "stg".
 */
export function StagingRedirect() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <div className="mx-auto max-w-md space-y-6 text-center">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold tracking-tight">
            Sage Radar AI has moved!
          </h1>
          <p className="text-muted-foreground">
            The staging environment is now reserved for development and testing
            only. Your account has been migrated to production.
          </p>
        </div>

        <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground space-y-2">
          <p className="font-medium text-foreground">To get started:</p>
          <ol className="list-decimal list-inside text-left space-y-1">
            <li>Visit the production app (link below)</li>
            <li>Sign in with your existing email and password</li>
            <li>Re-connect your Telegram account (~2 minutes)</li>
          </ol>
          <p className="text-xs pt-1">
            Your routing rules and configuration have been preserved.
          </p>
        </div>

        <Button asChild size="lg" className="w-full">
          <a href={PROD_URL} target="_blank" rel="noopener noreferrer">
            Go to Production
            <ExternalLink className="ml-2 h-4 w-4" />
          </a>
        </Button>

        <p className="text-xs text-muted-foreground">
          {PROD_URL}
        </p>
      </div>
    </div>
  );
}

/**
 * Returns true if the current hostname indicates a staging environment.
 */
export function isStagingEnvironment(): boolean {
  const hostname = window.location.hostname;
  return hostname.includes("staging") || hostname.includes("stg.");
}
