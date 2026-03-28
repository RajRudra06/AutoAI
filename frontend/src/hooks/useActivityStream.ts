"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchActivityEvents, fetchMetrics, fetchQueueWorkerHealth, getWsParams, getWsUrl } from "@/lib/api";
import { ActivityEvent, MetricsOverview, QueueWorkerHealth } from "@/lib/types";

const emptyMetrics: MetricsOverview = {
  window_events: 0,
  recent_event_count: 0,
  events_last_hour: 0,
  events_per_minute: 0,
  stale_or_failed_events: 0,
  active_vehicle_count: 0,
  high_risk_vehicle_count: 0,
  fleet_stage_counts: {},
  status_counts: {},
  source_counts: {},
  transition_counts: {},
};

const emptyHealth: QueueWorkerHealth = {
  timestamp: "",
  queue_status: "unknown",
  queue_depths: {},
  total_queue_depth: 0,
  max_queue_depth: 0,
  latency_ms_trend: [],
  retry_signal_trend: [],
  avg_latency_ms: 0,
  retry_signal_percent: 0,
  worker_heartbeat: {
    online_worker_count: 0,
    status: "unknown",
    workers: {},
  },
};

export function useActivityStream(vehicleId?: string) {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [metrics, setMetrics] = useState<MetricsOverview>(emptyMetrics);
  const [queueHealth, setQueueHealth] = useState<QueueWorkerHealth>(emptyHealth);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let disposed = false;

    async function loadInitial() {
      try {
        const [eventRows, metricsRow, healthRow] = await Promise.all([
          fetchActivityEvents({ vehicle_id: vehicleId, limit: 80 }),
          fetchMetrics(300),
          fetchQueueWorkerHealth(),
        ]);

        if (disposed) return;
        setEvents(eventRows);
        setMetrics(metricsRow);
        setQueueHealth(healthRow);
      } catch (err) {
        if (disposed) return;
        setError(err instanceof Error ? err.message : "Failed to fetch activity data");
      }
    }

    async function poll() {
      try {
        const eventRows = await fetchActivityEvents({ vehicle_id: vehicleId, limit: 80 });
        if (!disposed) setEvents(eventRows);
      } catch {
        // Keep existing events on polling failure.
      }

      try {
        const nextMetrics = await fetchMetrics(300);
        if (!disposed) setMetrics(nextMetrics);
      } catch {
        // Keep existing metrics on polling failure.
      }

      try {
        const nextHealth = await fetchQueueWorkerHealth();
        if (!disposed) setQueueHealth(nextHealth);
      } catch {
        // Keep existing health snapshot on polling failure.
      }
    }

    loadInitial();

    try {
      const params = getWsParams();
      ws = new WebSocket(`${getWsUrl()}?${params.toString()}`);

      ws.onopen = () => {
        if (!disposed) setConnected(true);
      };

      ws.onmessage = (msg) => {
        if (disposed) return;

        try {
          const payload = JSON.parse(msg.data) as ActivityEvent;
          if (vehicleId && payload.vehicle_id !== vehicleId) {
            return;
          }

          setEvents((current) => [payload, ...current].slice(0, 120));
        } catch {
          // Ignore malformed frames.
        }
      };

      ws.onerror = () => {
        if (!disposed) setConnected(false);
      };

      ws.onclose = () => {
        if (!disposed) setConnected(false);
      };
    } catch {}

    const eventInterval = window.setInterval(poll, 4000);

    return () => {
      disposed = true;
      window.clearInterval(eventInterval);
      if (ws) ws.close();
    };
  }, [vehicleId]);

  const stageOrder = useMemo(
    () => ["IDLE", "DIAGNOSIS_PENDING", "DIAGNOSIS_COMPLETE", "SCHEDULING_COMPLETE", "ENGAGEMENT_COMPLETE"],
    [],
  );

  return {
    events,
    metrics,
    queueHealth,
    connected,
    error,
    stageOrder,
  };
}
