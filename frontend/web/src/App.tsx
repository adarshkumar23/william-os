import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./contexts/AuthContext";
import Navbar from "./components/Navbar";
import ProtectedRoute from "./components/ProtectedRoute";
import DashboardPage from "./pages/DashboardPage";
import FitnessPage from "./pages/FitnessPage";
import HabitsPage from "./pages/HabitsPage";
import JournalPage from "./pages/JournalPage";
import LoginPage from "./pages/LoginPage";
import MedicinePage from "./pages/MedicinePage";
import RegisterPage from "./pages/RegisterPage";
import SettingsPage from "./pages/SettingsPage";
import StudyPage from "./pages/StudyPage";

function ProtectedLayout() {
  return (
    <div className="min-h-full">
      <Navbar />
      <main className="mx-auto max-w-7xl px-4 pb-10 pt-6 md:px-6 md:pt-8">
        <Outlet />
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          <Route
            element={
              <ProtectedRoute>
                <ProtectedLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<DashboardPage />} />
            <Route path="/habits" element={<HabitsPage />} />
            <Route path="/journal" element={<JournalPage />} />
            <Route path="/medicine" element={<MedicinePage />} />
            <Route path="/study" element={<StudyPage />} />
            <Route path="/fitness" element={<FitnessPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
