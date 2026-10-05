import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "@/store/auth";
import { AppShell } from "@/components/AppShell";
import { LoginPage } from "@/pages/Login";
import { useApplyTheme } from "@/hooks/useDemo";

// Every page except login is its own chunk; the home page (d3 charts) loads right after sign-in.
const TwinStagePage = lazy(() => import("@/pages/TwinStage").then((m) => ({ default: m.TwinStagePage })));
const MealPage = lazy(() => import("@/pages/Meal"));
const WhatIfPage = lazy(() => import("@/pages/WhatIf"));
const VoicePage = lazy(() => import("@/pages/Voice"));
const TrustPage = lazy(() => import("@/pages/Trust"));
const DoctorPanelPage = lazy(() => import("@/pages/DoctorPanel"));
const DoctorBriefPage = lazy(() => import("@/pages/DoctorBrief"));
const ProfilePage = lazy(() => import("@/pages/Profile"));
const NotFoundPage = lazy(() => import("@/pages/NotFound"));

function RequireAuth({ children }: { children: ReactNode }) {
  const token = useAuth((s) => s.token);
  const loc = useLocation();
  if (!token) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <AppShell>{children}</AppShell>;
}

function PageFallback() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6" aria-busy="true">
      <div className="skeleton h-8 w-56" />
      <div className="skeleton mt-6 h-64" />
    </div>
  );
}

export function App() {
  useApplyTheme();
  const page = (el: ReactNode) => (
    <RequireAuth>
      <Suspense fallback={<PageFallback />}>{el}</Suspense>
    </RequireAuth>
  );
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={page(<TwinStagePage />)} />
      <Route path="/meal" element={page(<MealPage />)} />
      <Route path="/whatif" element={page(<WhatIfPage />)} />
      <Route path="/talk" element={page(<VoicePage />)} />
      <Route path="/trust" element={page(<TrustPage />)} />
      <Route path="/doctor" element={page(<DoctorPanelPage />)} />
      <Route path="/doctor/:pid" element={page(<DoctorBriefPage />)} />
      <Route path="/me" element={page(<ProfilePage />)} />
      <Route path="*" element={page(<NotFoundPage />)} />
    </Routes>
  );
}
