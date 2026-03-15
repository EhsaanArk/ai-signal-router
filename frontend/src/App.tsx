import { type ReactNode } from "react";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";
import { ProtectedRoute } from "@/components/layout/protected-route";
import { DashboardLayout } from "@/components/layout/dashboard-layout";
import { LoginPage } from "@/pages/login";
import { RegisterPage } from "@/pages/register";
import { ForgotPasswordPage } from "@/pages/forgot-password";
import { ResetPasswordPage } from "@/pages/reset-password";
import { DashboardPage } from "@/pages/dashboard";
import { TelegramPage } from "@/pages/telegram";
import { RoutingRulesPage } from "@/pages/routing-rules";
import { RoutingRulesNewPage } from "@/pages/routing-rules-new";
import { RoutingRulesEditPage } from "@/pages/routing-rules-edit";
import { LogsPage } from "@/pages/logs";
import { SettingsPage } from "@/pages/settings";
import { SetupPage } from "@/pages/setup";
import { AdminHealthPage } from "@/pages/admin/health";
import { AdminUsersPage } from "@/pages/admin/users";
import { AdminUserDetailPage } from "@/pages/admin/user-detail";
import { AdminSignalsPage } from "@/pages/admin/signals";
import { AdminSystemRulesPage } from "@/pages/admin/system-rules";
import { NotFound } from "@/components/shared/not-found";
import { useAuth } from "@/contexts/auth-context";

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
