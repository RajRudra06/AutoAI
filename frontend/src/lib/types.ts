export type ActivityEvent = {
  _id?: string;
  event_id: string;
  timestamp: string;
  vehicle_id: string;
  source_type: string;
  source_name: string;
  stage_from?: string | null;
  stage_to?: string | null;
  action: string;
  status: string;
  celery_task_id?: string | null;
  job_id?: string | null;
  risk_level?: string | null;
  summary: string;
  details?: Record<string, unknown>;
  latency_ms?: number | null;
};

export type MetricsOverview = {
  window_events: number;
  recent_event_count: number;
  events_last_hour: number;
  events_per_minute: number;
  stale_or_failed_events: number;
  active_vehicle_count: number;
  high_risk_vehicle_count: number;
  fleet_stage_counts: Record<string, number>;
  status_counts: Record<string, number>;
  source_counts: Record<string, number>;
  transition_counts: Record<string, number>;
};

export type QueueWorkerHealth = {
  timestamp: string;
  queue_status: string;
  queue_depths: Record<string, number>;
  total_queue_depth: number;
  max_queue_depth: number;
  latency_ms_trend: number[];
  retry_signal_trend: number[];
  avg_latency_ms: number;
  retry_signal_percent: number;
  worker_heartbeat: {
    online_worker_count: number;
    status: string;
    workers: Record<
      string,
      {
        online: boolean;
        pid?: number;
        pool?: number;
        total_tasks?: number;
      }
    >;
  };
};

export type VehicleSummaryPayload = {
  technical_summary: string;
  business_summary: string;
  judge_summary: string;
};

export type VehicleState = {
  vehicle_id: string;
  latest_features?: Record<string, number | string | boolean | null>;
  workflow_state?: {
    current_stage?: string;
    flags?: {
      diagnosis_required?: boolean;
      scheduling_required?: boolean;
      engagement_required?: boolean;
    };
  };
  risk_state?: {
    high_risk_active?: boolean;
    unresolved_issues?: string[];
  };
  pipeline_associated?: {
    pipeline_status?: string;
  };
  last_updated?: string;
};

export type VehicleListResponse = {
  vehicles: VehicleState[];
};
