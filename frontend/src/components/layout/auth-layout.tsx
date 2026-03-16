import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { APP_NAME } from "@/lib/constants";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="dark flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardContent className="pt-6">
          <div className="mb-6 flex flex-col items-center gap-1.5">
            <h1 className="text-center text-2xl font-semibold">
              {APP_NAME}
            </h1>
            <span className="text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-500 border border-amber-500/20">Beta</span>
            <p className="text-xs text-muted-foreground text-center mt-1">
              Automate your Telegram trading signals to SageMaster
            </p>
          </div>
          {children}
        </CardContent>
      </Card>
    </div>
  );
}
