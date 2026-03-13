import { createBrowserRouter, RouterProvider } from "react-router-dom";
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
import { NotFound } from "@/components/shared/not-found";

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  {
    element: <ProtectedRoute />,
    children: [
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
        ],
      },
    ],
  },
  { path: "*", element: <NotFound /> },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
