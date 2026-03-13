import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { APP_NAME } from "@/lib/constants";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-md">
        <CardContent className="pt-6">
          <h1 className="mb-6 text-center text-2xl font-semibold">
            {APP_NAME}
          </h1>
          {children}
        </CardContent>
      </Card>
    </div>
  );
}
