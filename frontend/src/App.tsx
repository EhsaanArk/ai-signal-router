import type { ReactNode } from "react";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";
import { ProtectedRoute } from "@/components/layout/protected-route";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { LoginPage } from "@/pages/login";
import { RegisterPage } from "@/pages/register";
import { ForgotPasswordPage } from "@/pages/forgot-password";
import { ResetPasswordPage } from "@/pages/reset-password";
import { VerifyEmailPage } from "@/pages/verify-email";
import { NotFound } from "@/components/shared/not-found";
import { useAuth } from "@/contexts/auth-context";
import { lazyRetry } from "@/lib/lazy-retry";

const TermsPage = lazyRetry(() => import("./pages/terms"));
const PrivacyPage = lazyRetry(() => import("./pages/privacy"));
const OAuthCallbackPage = lazyRetry(() => import("./pages/oauth-callback"));
const DashboardPage = lazyRetry(() => import("./pages/dashboard"));
const TelegramPage = lazyRetry(() => import("./pages/telegram"));
const RoutingRulesPage = lazyRetry(() => import("./pages/routing-rules"));
const RoutingRulesNewPage = lazyRetry(() => import("./pages/routing-rules-new"));
const RoutingRulesEditPage = lazyRetry(() => import("./pages/routing-rules-edit"));
const LogsPage = lazyRetry(() => import("./pages/logs"));
const SettingsPage = lazyRetry(() => import("./pages/settings"));
const SetupPage = lazyRetry(() => import("./pages/setup"));
const AdminHealthPage = lazyRetry(() => import("./pages/admin/health"));
const AdminUsersPage = lazyRetry(() => import("./pages/admin/users"));
const AdminUserDetailPage = lazyRetry(() => import("./pages/admin/user-detail"));
const AdminSignalsPage = lazyRetry(() => import("./pages/admin/signals"));
const AdminSystemRulesPage = lazyRetry(() => import("./pages/admin/system-rules"));
const AdminParserPage = lazyRetry(() => import("./pages/admin/parser"));
const AdminSettingsPage = lazyRetry(() => import("./pages/admin/settings"));

function AdminRoute({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (!user?.is_admin) return <Navigate to="/" replace />;
  return <>{children}</>;
}

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  { path: "/verify-email", element: <VerifyEmailPage /> },
  { path: "/terms", element: <TermsPage /> },
  { path: "/privacy", element: <PrivacyPage /> },
  { path: "/auth/callback", element: <OAuthCallbackPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      { path: "/setup", element: <SetupPage /> },
      {
        element: <DashboardLayout />,
        children: [
          { path: "/", element: <DashboardPage /> },
          { path: "/telegram", element: <TelegramPage /> },
          { path: "/routing-rules", element: <RoutingRulesPage /> },
          { path: "/routing-rules/new", element: <RoutingRulesNewPage /> },
          { path: "/routing-rules/:id/edit", element: <RoutingRulesEditPage /> },
          { path: "/logs", element: <LogsPage /> },
          { path: "/settings", element: <SettingsPage /> },
          { path: "/admin/health", element: <AdminRoute><AdminHealthPage /></AdminRoute> },
          { path: "/admin/users", element: <AdminRoute><AdminUsersPage /></AdminRoute> },
          { path: "/admin/users/:id", element: <AdminRoute><AdminUserDetailPage /></AdminRoute> },
          { path: "/admin/signals", element: <AdminRoute><AdminSignalsPage /></AdminRoute> },
          { path: "/admin/system-rules", element: <AdminRoute><AdminSystemRulesPage /></AdminRoute> },
          { path: "/admin/parser", element: <AdminRoute><AdminParserPage /></AdminRoute> },
          { path: "/admin/settings", element: <AdminRoute><AdminSettingsPage /></AdminRoute> },
        ],
      },
    ],
  },
  { path: "*", element: <NotFound /> },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
