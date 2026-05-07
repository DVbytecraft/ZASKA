import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./pages/AppLayout";
import { AuthPage } from "./pages/AuthPage";
import { ChatPage } from "./pages/ChatPage";
import { CreateTaskPage } from "./pages/CreateTaskPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ProfilePage } from "./pages/ProfilePage";
import { TaskDetailPage } from "./pages/TaskDetailPage";
import { TaskListPage } from "./pages/TaskListPage";
import { WalletPage } from "./pages/WalletPage";
import { useAuthStore } from "./store";
import "./styles.css";

function Protected({ children }: { children: React.ReactNode }) {
  const userId = useAuthStore((s) => s.userId);
  if (!userId) return <Navigate to="/auth" replace />;
  return <>{children}</>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/auth" element={<AuthPage />} />
        <Route
          path="/"
          element={
            <Protected>
              <AppLayout />
            </Protected>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="tasks/new" element={<CreateTaskPage />} />
          <Route path="tasks" element={<TaskListPage />} />
          <Route path="tasks/:taskId" element={<TaskDetailPage />} />
          <Route path="chat/:taskId" element={<ChatPage />} />
          <Route path="wallet" element={<WalletPage />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
