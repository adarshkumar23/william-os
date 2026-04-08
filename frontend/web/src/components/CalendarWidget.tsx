import { format } from "date-fns";
import { CalendarDays } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../services/api";
import { CalendarEvent, CalendarTodayResponse } from "../types/api";
import { AppCard, Badge } from "./ui";

export default function CalendarWidget() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const rows = await api.calendar.today();
        if (active) {
          setEvents((rows as CalendarTodayResponse)?.events ?? []);
        }
      } catch {
        if (active) {
          setEvents([]);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, []);

  return (
    <AppCard>
      <div className="flex items-center gap-2">
        <CalendarDays className="h-4 w-4 text-accent" />
        <p className="section-label">Calendar Today</p>
      </div>
      <div className="mt-3 space-y-2">
        {loading ? (
          <p className="body-copy">Loading events...</p>
        ) : events.length === 0 ? (
          <p className="body-copy">No calendar events today.</p>
        ) : (
          events.slice(0, 6).map((event) => (
            <div
              key={`${event.source}-${event.id}`}
              className="rounded-lg border border-border bg-surface-raised p-3"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-text-primary">{event.title}</p>
                <Badge
                  label={event.source}
                  variant={event.source === "google" ? "accent" : "default"}
                  className="capitalize"
                />
              </div>
              <p className="meta-copy mt-1">
                {format(new Date(event.start), "p")} - {format(new Date(event.end), "p")}
                {event.location ? ` • ${event.location}` : ""}
              </p>
            </div>
          ))
        )}
      </div>
    </AppCard>
  );
}
