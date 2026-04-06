import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import { ErrorBoundary } from "./components/ErrorBoundary";
import DashboardPage from "./pages/DashboardPage";
import DecisionsPage from "./pages/DecisionsPage";
import FitnessPage from "./pages/FitnessPage";
import HabitsPage from "./pages/Habits";
import JournalPage from "./pages/JournalPage";
import LoginPage from "./pages/LoginPage";
import MedicinePage from "./pages/MedicinePage";
import RegisterPage from "./pages/RegisterPage";
import SettingsPage from "./pages/SettingsPage";
import SleepPage from "./pages/SleepPage";
import StudyPage from "./pages/StudyPage";
import TradingPage from "./pages/TradingPage";

function AnimatedRouteWrapper({ children }: { children: ReactNode }) {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        transition={{ duration: 0.2 }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route
              path="/dashboard"
              element={
                <AnimatedRouteWrapper>
                  <DashboardPage />
                </AnimatedRouteWrapper>
              }
            />
            <Route path="/habits" element={<AnimatedRouteWrapper><HabitsPage /></AnimatedRouteWrapper>} />
            <Route path="/journal" element={<AnimatedRouteWrapper><JournalPage /></AnimatedRouteWrapper>} />
            <Route path="/medicine" element={<AnimatedRouteWrapper><MedicinePage /></AnimatedRouteWrapper>} />
            <Route path="/study" element={<AnimatedRouteWrapper><StudyPage /></AnimatedRouteWrapper>} />
            <Route path="/fitness" element={<AnimatedRouteWrapper><FitnessPage /></AnimatedRouteWrapper>} />
            <Route path="/trading" element={<AnimatedRouteWrapper><TradingPage /></AnimatedRouteWrapper>} />
            <Route path="/sleep" element={<AnimatedRouteWrapper><SleepPage /></AnimatedRouteWrapper>} />
            <Route path="/decisions" element={<AnimatedRouteWrapper><DecisionsPage /></AnimatedRouteWrapper>} />
            <Route path="/settings" element={<AnimatedRouteWrapper><SettingsPage /></AnimatedRouteWrapper>} />
          </Route>
        </Route>

        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}
