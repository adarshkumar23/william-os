import { Navigate, Outlet, useLocation } from "react-router-dom";

import { SkeletonLoader } from "./ui";
import { useAuth } from "../contexts/AuthContext";

export default function ProtectedRoute() {
  const location = useLocation();
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center px-6">
        <div className="w-full max-w-xl space-y-3">
          <SkeletonLoader variant="card" />
          <SkeletonLoader variant="text" lines={2} />
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
