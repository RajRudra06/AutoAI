import {
  ActivityEvent,
  MetricsOverview,
  QueueWorkerHealth,
  RegisterVehiclePayload,
  VehicleListResponse,
  VehicleState,
  VehicleSummaryPayload,
} from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000/api";
const AGENT_ID = process.env.NEXT_PUBLIC_AGENT_ID ?? "agent_001";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "secret_key_001";

const authHeaders = {
  "Content-Type": "application/json",
  "X-AGENT-ID": AGENT_ID,
  "X-API-KEY": API_KEY,
};

async function jsonOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status}: ${text}`);
  }
  return (await response.json()) as T;
}

export async function fetchActivityEvents(params: {
  vehicle_id?: string;
  source_name?: string;
  limit?: number;
  status?: string;
} = {}): Promise<ActivityEvent[]> {
  try {
    const search = new URLSearchParams();
    if (params.vehicle_id) search.set("vehicle_id", params.vehicle_id);
    if (params.source_name) search.set("source_name", params.source_name);
    if (params.status) search.set("status", params.status);
    search.set("limit", String(params.limit ?? 80));

    const response = await fetch(`${API_BASE}/activity/events?${search.toString()}`, {
      headers: authHeaders,
      cache: "no-store",
    });

    const data = await jsonOrThrow<{ events: ActivityEvent[] }>(response);
    return data.events ?? [];
  } catch (error) {
    console.warn("fetchActivityEvents failed", error);
    return [];
  }
}

export async function fetchMetrics(windowEvents = 200): Promise<MetricsOverview> {
  const response = await fetch(
    `${API_BASE}/activity/metrics/overview?window_events=${windowEvents}`,
    {
      headers: authHeaders,
      cache: "no-store",
    },
  );

  return jsonOrThrow<MetricsOverview>(response);
}

export async function fetchQueueWorkerHealth(): Promise<QueueWorkerHealth> {
  const response = await fetch(`${API_BASE}/activity/metrics/health`, {
    headers: authHeaders,
    cache: "no-store",
  });

  return jsonOrThrow<QueueWorkerHealth>(response);
}

export async function fetchVehicles(ownerId?: string): Promise<VehicleState[]> {
  const query = ownerId ? `?owner_id=${encodeURIComponent(ownerId)}` : "";
  try {
    const response = await fetch(`${API_BASE}/vehicles/state${query}`, {
      headers: authHeaders,
      cache: "no-store",
    });

    const data = await jsonOrThrow<VehicleListResponse>(response);
    return data.vehicles ?? [];
  } catch (error) {
    console.warn("fetchVehicles failed", error);
    return [];
  }
}

export async function registerVehicle(payload: RegisterVehiclePayload): Promise<VehicleState> {
  const response = await fetch(`${API_BASE}/vehicles/register`, {
    method: "POST",
    headers: authHeaders,
    body: JSON.stringify(payload),
  });

  const data = await jsonOrThrow<{ success: boolean; vehicle: VehicleState }>(response);
  return data.vehicle;
}

export async function deleteVehicle(vehicleId: string): Promise<boolean> {
  const response = await fetch(`${API_BASE}/vehicles/${vehicleId}`, {
    method: "DELETE",
    headers: authHeaders,
  });
  
  const data = await jsonOrThrow<{ success: boolean; deleted: boolean }>(response);
  return data.deleted;
}

export async function fetchVehicleActivity(vehicleId: string, limit = 25): Promise<ActivityEvent[]> {
  try {
    const response = await fetch(`${API_BASE}/activity/vehicle/${vehicleId}?limit=${limit}`, {
      headers: authHeaders,
      cache: "no-store",
    });

    const data = await jsonOrThrow<{ events: ActivityEvent[] }>(response);
    return data.events ?? [];
  } catch (error) {
    console.warn("fetchVehicleActivity failed", error);
    return [];
  }
}

export async function fetchVehicleSummary(vehicleId: string): Promise<VehicleSummaryPayload | null> {
  const response = await fetch(`${API_BASE}/activity/summary/${vehicleId}`, {
    headers: authHeaders,
    cache: "no-store",
  });

  if (response.status === 404) {
    return null;
  }

  const data = await jsonOrThrow<{ success: boolean; summary?: VehicleSummaryPayload }>(response);
  return data.summary ?? null;
}

export async function regenerateVehicleSummary(vehicleId: string): Promise<VehicleSummaryPayload | null> {
  const response = await fetch(`${API_BASE}/activity/summary/${vehicleId}`, {
    method: "POST",
    headers: authHeaders,
  });

  const data = await jsonOrThrow<{ success: boolean; summary?: VehicleSummaryPayload }>(response);
  return data.summary ?? null;
}

export async function triggerSimulationStart(vehicleId: string): Promise<boolean> {
  const response = await fetch(`${API_BASE}/simulation/start/${vehicleId}`, {
    method: "POST",
    headers: authHeaders,
  });
  const data = await jsonOrThrow<{ success: boolean }>(response);
  return data.success;
}

export async function triggerSystemBreach(vehicleId: string): Promise<boolean> {
  const response = await fetch(`${API_BASE}/simulation/force-risk/${vehicleId}`, {
    method: "POST",
    headers: authHeaders,
  });
  const data = await jsonOrThrow<{ success: boolean }>(response);
  return data.success;
}

export function getWsUrl(): string {
  const wsBase = (process.env.NEXT_PUBLIC_BACKEND_WS ?? "ws://127.0.0.1:8000/api").replace(/\/$/, "");
  return `${wsBase}/activity/ws`;
}

export function getWsParams(): URLSearchParams {
  const params = new URLSearchParams();
  params.set("agent_id", AGENT_ID);
  params.set("api_key", API_KEY);
  return params;
}
