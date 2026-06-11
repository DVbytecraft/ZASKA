import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./pages/AppLayout";
import { AuthPage } from "./pages/AuthPage";
import { ChatPage } from "./pages/ChatPage";
import { CreateTaskPage } from "./pages/CreateTaskPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DriverPortalPage } from "./pages/DriverPortalPage";
import { FoodPage } from "./pages/FoodPage";
import { MarketplacePage } from "./pages/MarketplacePage";
import { MerchantPortalPage } from "./pages/MerchantPortalPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { ProfilePage } from "./pages/ProfilePage";
import { RestaurantPortalPage } from "./pages/RestaurantPortalPage";
import { ShopPage } from "./pages/ShopPage";
import { SocialProtectionPage } from "./pages/SocialProtectionPage";
import { TaskApplicantsPage } from "./pages/TaskApplicantsPage";
import { TaskDetailPage } from "./pages/TaskDetailPage";
import { TaskListPage } from "./pages/TaskListPage";
import { VtcPage } from "./pages/VtcPage";
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
          <Route path="marketplace" element={<MarketplacePage />} />
          <Route path="food" element={<FoodPage />} />
          <Route path="food/partner" element={<RestaurantPortalPage />} />
          <Route path="shop" element={<ShopPage />} />
          <Route path="shop/partner" element={<MerchantPortalPage />} />
          <Route path="vtc" element={<VtcPage />} />
          <Route path="vtc/driver" element={<DriverPortalPage />} />
          <Route path="tasks/new" element={<CreateTaskPage />} />
          <Route path="tasks" element={<TaskListPage />} />
          <Route path="tasks/:taskId" element={<TaskDetailPage />} />
          <Route path="tasks/:taskId/applicants" element={<TaskApplicantsPage />} />
          <Route path="chat/:taskId" element={<ChatPage />} />
          <Route path="wallet" element={<WalletPage />} />
          <Route path="social-protection" element={<SocialProtectionPage />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="profile" element={<ProfilePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
