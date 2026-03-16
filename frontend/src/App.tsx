import { lazy, type ReactNode } from "react";
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

const DashboardPage = lazy(() => import("./pages/dashboard"));
const TelegramPage = lazy(() => import("./pages/telegram"));
const RoutingRulesPage = lazy(() => import("./pages/routing-rules"));
const RoutingRulesNewPage = lazy(() => import("./pages/routing-rules-new"));
const RoutingRulesEditPage = lazy(() => import("./pages/routing-rules-edit"));
const LogsPage = lazy(() => import("./pages/logs"));
const SettingsPage = lazy(() => import("./pages/settings"));
const SetupPage = lazy(() => import("./pages/setup"));
const AdminHealthPage = lazy(() => import("./pages/admin/health"));
const AdminUsersPage = lazy(() => import("./pages/admin/users"));
const AdminUserDetailPage = lazy(() => import("./pages/admin/user-detail"));
const AdminSignalsPage = lazy(() => import("./pages/admin/signals"));
const AdminSystemRulesPage = lazy(() => import("./pages/admin/system-rules"));

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
        ],
      },
    ],
  },
  { path: "*", element: <NotFound /> },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
