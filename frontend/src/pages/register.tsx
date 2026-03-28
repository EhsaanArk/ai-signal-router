import { Link } from "react-router-dom";
import { AuthLayout } from "@/components/layout/auth-layout";
import { usePageTitle } from "@/hooks/use-page-title";

export function RegisterPage() {
  usePageTitle("Registration Closed");

  return (
    <AuthLayout>
      <div className="space-y-4 text-center">
        <h2 className="text-lg font-semibold">Registration is Currently Closed</h2>
        <p className="text-sm text-muted-foreground">
          Thanks for your interest in Sage Radar AI! We are working towards the
          big launch — stay tuned!
        </p>
        <p className="text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link to="/login" className="text-primary hover:underline">
            Sign In
          </Link>
        </p>
      </div>
    </AuthLayout>
  );
}

export default RegisterPage;
