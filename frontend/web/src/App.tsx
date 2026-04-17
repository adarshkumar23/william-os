import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";
import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import { ErrorBoundary } from "./components/ErrorBoundary";
import DashboardPage from "./pages/DashboardPage";
import CareerDashboardPage from "./pages/career/CareerDashboardPage";
import CareerCoachPage from "./pages/career/CareerCoachPage";
import ProblemsPage from "./pages/career/ProblemsPage";
import ProjectsPage from "./pages/career/ProjectsPage";
import ApplicationsKanbanPage from "./pages/career/ApplicationsKanbanPage";
import NetworkPage from "./pages/career/NetworkPage";
import OpportunitiesPage from "./pages/career/OpportunitiesPage";
import DecisionsPage from "./pages/DecisionsPage";
import FitnessPage from "./pages/FitnessPage";
import HabitsPage from "./pages/Habits";
import JournalPage from "./pages/JournalPage";
import LoginPage from "./pages/LoginPage";
import MedicinePage from "./pages/MedicinePage";
import OnboardingPage from "./pages/OnboardingPage";
import RegisterPage from "./pages/RegisterPage";
import RulesPage from "./pages/RulesPage";
import SettingsPage from "./pages/SettingsPage";
import SleepPage from "./pages/SleepPage";
import StudyPage from "./pages/StudyPage";
import TradingPage from "./pages/TradingPage";
import ChatPage from "./pages/ChatPage";
import TimelinePage from "./pages/TimelinePage";
import AdminPage from "./pages/AdminPage";

function AnimatedRouteWrapper({ children }: { children: ReactNode }) {
  const location = useLocation();
  const shouldReduceMotion = useReducedMotion();

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={location.pathname}
        initial={shouldReduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={shouldReduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: -10 }}
        transition={{ duration: shouldReduceMotion ? 0 : 0.2 }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}

function ModuleBoundary({ moduleName, children }: { moduleName: string; children: ReactNode }) {
  return <ErrorBoundary moduleName={moduleName}>{children}</ErrorBoundary>;
}

export default function App() {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        window.dispatchEvent(new Event("william:command-palette-toggle"));
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route element={<ProtectedRoute />}>
          <Route path="/onboarding" element={<OnboardingPage />} />

          <Route element={<Layout />}>
            <Route
              path="/dashboard"
              element={
                <ModuleBoundary moduleName="dashboard">
                  <AnimatedRouteWrapper>
                    <DashboardPage />
                  </AnimatedRouteWrapper>
                </ModuleBoundary>
              }
            />
            <Route
              path="/habits"
              element={<ModuleBoundary moduleName="habits"><AnimatedRouteWrapper><HabitsPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/journal"
              element={<ModuleBoundary moduleName="journal"><AnimatedRouteWrapper><JournalPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/medicine"
              element={<ModuleBoundary moduleName="medicine"><AnimatedRouteWrapper><MedicinePage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/study"
              element={<ModuleBoundary moduleName="study"><AnimatedRouteWrapper><StudyPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/fitness"
              element={<ModuleBoundary moduleName="fitness"><AnimatedRouteWrapper><FitnessPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/trading"
              element={<ModuleBoundary moduleName="trading"><AnimatedRouteWrapper><TradingPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/sleep"
              element={<ModuleBoundary moduleName="sleep"><AnimatedRouteWrapper><SleepPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/decisions"
              element={<ModuleBoundary moduleName="decisions"><AnimatedRouteWrapper><DecisionsPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/chat"
              element={<ModuleBoundary moduleName="chat"><AnimatedRouteWrapper><ChatPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/timeline"
              element={<ModuleBoundary moduleName="timeline"><AnimatedRouteWrapper><TimelinePage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/rules"
              element={<ModuleBoundary moduleName="rules"><AnimatedRouteWrapper><RulesPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/settings"
              element={<ModuleBoundary moduleName="settings"><AnimatedRouteWrapper><SettingsPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/admin"
              element={<ModuleBoundary moduleName="admin"><AnimatedRouteWrapper><AdminPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/career"
              element={<ModuleBoundary moduleName="career-dashboard"><AnimatedRouteWrapper><CareerDashboardPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/career/coach"
              element={<ModuleBoundary moduleName="career-coach"><AnimatedRouteWrapper><CareerCoachPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/career/problems"
              element={<ModuleBoundary moduleName="career-problems"><AnimatedRouteWrapper><ProblemsPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/career/projects"
              element={<ModuleBoundary moduleName="career-projects"><AnimatedRouteWrapper><ProjectsPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/career/applications"
              element={<ModuleBoundary moduleName="career-applications"><AnimatedRouteWrapper><ApplicationsKanbanPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/career/network"
              element={<ModuleBoundary moduleName="career-network"><AnimatedRouteWrapper><NetworkPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
            <Route
              path="/career/opportunities"
              element={<ModuleBoundary moduleName="career-opportunities"><AnimatedRouteWrapper><OpportunitiesPage /></AnimatedRouteWrapper></ModuleBoundary>}
            />
          </Route>
        </Route>

        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}
