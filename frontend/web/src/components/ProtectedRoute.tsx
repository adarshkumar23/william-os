import { Navigate, Outlet, useLocation } from "react-router-dom";

import LoadingSpinner from "./LoadingSpinner";
import { useAuth } from "../contexts/AuthContext";

export default function ProtectedRoute() {
  const location = useLocation();
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingSpinner fullPage label="Restoring session" />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <Outlet />;
}
