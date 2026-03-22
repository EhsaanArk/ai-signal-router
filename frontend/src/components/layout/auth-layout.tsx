import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { APP_NAME } from "@/lib/constants";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="dark flex flex-col min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardContent className="pt-6">
          <div className="mb-6 flex flex-col items-center gap-1.5 group cursor-pointer">
            <img src="/logo.svg" alt={APP_NAME} className="h-12 w-12 mb-1 transition-transform duration-200 group-hover:scale-110 group-hover:rotate-12" />
            <h1 className="text-center text-2xl font-semibold transition-colors duration-200 group-hover:text-primary">
              {APP_NAME}
            </h1>
            <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-500 border border-amber-500/20">Beta</span>
            <p className="text-xs text-muted-foreground text-center mt-1">
              AI-powered Telegram signal routing, automated
            </p>
          </div>
          {children}
        </CardContent>
      </Card>
      <div className="mt-4 flex items-center justify-center gap-3 text-[11px] text-muted-foreground">
        <Link to="/terms" className="hover:text-primary transition-colors">
          Terms of Service
        </Link>
        <span>&middot;</span>
        <Link to="/privacy" className="hover:text-primary transition-colors">
          Privacy Policy
        </Link>
      </div>
    </div>
  );
}
