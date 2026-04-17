import { Zap } from "lucide-react";

export default function CareerCoachPage() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <div className="rounded-full bg-indigo-500/15 p-6">
        <Zap className="h-10 w-10 text-indigo-400" />
      </div>
      <h2 className="text-xl font-semibold text-text-primary">William as Career Coach</h2>
      <p className="max-w-sm text-text-secondary">
        Daily briefings, interview drills, and AI-powered career guidance are coming in Sprint 3.
      </p>
      <span className="rounded-full border border-indigo-400/30 bg-indigo-500/10 px-4 py-1.5 text-sm text-indigo-300">
        Sprint 3 — Coming Soon
      </span>
    </div>
  );
}
