import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import type { ReactNode } from "react";

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return <div className="grid min-h-screen place-items-center text-sm text-muted-foreground">Загрузка…</div>;
  }
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
}
