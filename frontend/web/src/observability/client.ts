// @ts-ignore - resolved after npm install in workspace
import * as Sentry from "@sentry/react";

type MetricTags = Record<string, string | number | boolean>;

const pageApiErrorCounts = new Map<string, number>();
let refreshFailures = 0;

export function initFrontendObservability() {
  const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;
  if (!dsn) {
    return;
  }

  Sentry.init({
    dsn,
    integrations: [Sentry.browserTracingIntegration(), Sentry.replayIntegration()],
    tracesSampleRate: Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? 0.2),
    replaysSessionSampleRate: Number(import.meta.env.VITE_SENTRY_REPLAY_SAMPLE_RATE ?? 0.05),
    replaysOnErrorSampleRate: Number(import.meta.env.VITE_SENTRY_REPLAY_ON_ERROR_SAMPLE_RATE ?? 1.0),
    environment: import.meta.env.MODE,
    release: import.meta.env.VITE_APP_VERSION || "web-dev",
  });

  captureNavigationTimings();
  observeLcp();
  observeCls();
}

export function captureUIError(error: Error, context: MetricTags = {}) {
  Sentry.captureException(error, {
    tags: {
      module: String(context.module ?? "unknown"),
    },
    extra: context,
  });
}

export function recordApiError(page: string, endpoint: string, statusCode: number) {
  const key = page || "unknown";
  const nextCount = (pageApiErrorCounts.get(key) ?? 0) + 1;
  pageApiErrorCounts.set(key, nextCount);

  if (nextCount % 5 !== 0) {
    return;
  }

  Sentry.captureMessage("frontend_api_error_rate", {
    level: "warning",
    tags: {
      page: key,
      endpoint,
    },
    extra: {
      api_errors_for_page: nextCount,
      status_code: statusCode,
    },
  });
}

export function recordRefreshTokenFailure(page: string) {
  refreshFailures += 1;
  Sentry.captureMessage("refresh_token_failed", {
    level: "warning",
    tags: { page },
    extra: { refresh_failures: refreshFailures },
  });
}

function captureNavigationTimings() {
  const navEntries = performance.getEntriesByType("navigation") as PerformanceNavigationTiming[];
  if (!navEntries.length) {
    return;
  }

  const nav = navEntries[0];
  if (nav.responseStart > 0) {
    Sentry.captureMessage("web_vital_ttfb", {
      level: "info",
      extra: { ttfb_ms: Math.round(nav.responseStart) },
    });
  }
}

function observeLcp() {
  if (!("PerformanceObserver" in window)) {
    return;
  }

  let latestLcp = 0;
  const observer = new PerformanceObserver((entryList) => {
    const entries = entryList.getEntries();
    const last = entries[entries.length - 1];
    if (last) {
      latestLcp = last.startTime;
    }
  });

  try {
    observer.observe({ type: "largest-contentful-paint", buffered: true });
  } catch {
    return;
  }

  const flush = () => {
    if (latestLcp > 0) {
      Sentry.captureMessage("web_vital_lcp", {
        level: "info",
        extra: { lcp_ms: Math.round(latestLcp) },
      });
    }
    observer.disconnect();
  };

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      flush();
    }
  });
}

function observeCls() {
  if (!("PerformanceObserver" in window)) {
    return;
  }

  let clsValue = 0;
  const observer = new PerformanceObserver((entryList) => {
    for (const entry of entryList.getEntries() as Array<PerformanceEntry & { value?: number; hadRecentInput?: boolean }>) {
      if (!entry.hadRecentInput && typeof entry.value === "number") {
        clsValue += entry.value;
      }
    }
  });

  try {
    observer.observe({ type: "layout-shift", buffered: true });
  } catch {
    return;
  }

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      Sentry.captureMessage("web_vital_cls", {
        level: "info",
        extra: { cls: Number(clsValue.toFixed(4)) },
      });
      observer.disconnect();
    }
  });
}
