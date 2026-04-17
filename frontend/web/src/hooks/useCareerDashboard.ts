import { useEffect, useState } from "react";
import { api } from "../services/api";

export type CareerDashboard = {
  score: {
    overall: number;
    components: Record<string, number>;
    snapshot_date: string;
  };
  score_history: Array<{ date: string; score: number }>;
  stats: {
    problems_solved: number;
    deployed_projects: number;
    active_applications: number;
    contacts: number;
    cf_rating: number;
  };
  pipeline_preview: Record<string, Array<{ id: string; company: string; role: string; stage: string }>>;
  recent_opportunities: Array<{ id: string; title: string; kind: string; deadline: string | null }>;
  warnings: string[];
};

export function useCareerDashboard() {
  const [data, setData] = useState<CareerDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      const result = await api.career.dashboard();
      setData(result as CareerDashboard);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load career dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  return { data, loading, error, reload: load };
}
