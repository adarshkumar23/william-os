import clsx from "clsx";
import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";

export default function OSModeSwitcher() {
  const location = useLocation();
  const navigate = useNavigate();
  const mode = location.pathname.startsWith("/career") ? "career" : "william";

  useEffect(() => {
    if (mode === "career") {
      localStorage.setItem("wos.lastCareerRoute", location.pathname);
    } else {
      localStorage.setItem("wos.lastWilliamRoute", location.pathname);
    }
  }, [location.pathname, mode]);

  const goToWilliam = () => {
    navigate(localStorage.getItem("wos.lastWilliamRoute") ?? "/dashboard");
  };

  const goToCareer = () => {
    navigate(localStorage.getItem("wos.lastCareerRoute") ?? "/career");
  };

  return (
    <div className="mb-4 flex gap-1 rounded-xl border border-border bg-surface p-1">
      <button
        onClick={goToWilliam}
        className={clsx(
          "flex-1 rounded-lg px-2 py-1.5 text-xs font-semibold transition",
          mode === "william"
            ? "bg-accent/15 text-accent border border-accent/30"
            : "text-text-secondary hover:bg-surface-raised",
        )}
      >
        William OS
      </button>
      <button
        onClick={goToCareer}
        className={clsx(
          "flex-1 rounded-lg px-2 py-1.5 text-xs font-semibold transition",
          mode === "career"
            ? "bg-indigo-500/20 text-indigo-300 border border-indigo-400/40"
            : "text-text-secondary hover:bg-surface-raised",
        )}
      >
        Career OS
      </button>
    </div>
  );
}
