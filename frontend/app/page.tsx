"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const API_URL = "http://127.0.0.1:8000";
const WS_URL = "ws://127.0.0.1:8000/ws";

type Site = {
  site_id: string;
  name: string;
  url: string;
  hostname: string;
  monitoring_enabled?: boolean;
  last_scan_id?: string | null;
  last_status?: string | null;
  last_risk_score?: number | null;
  last_risk_level?: string | null;
};

type Scan = {
  scan_id: string;
  status: string;
  status_code: number | null;
  response_time_ms: number | null;
  ip_address: string | null;
  risk_score: number | null;
  risk_level: string | null;
  findings_count: number;
};

type MonitoringEvent = {
  event_id?: string;
  event_type?: string;
  severity?: string;
  title?: string;
  description?: string;
};

type Alert = {
  alert_id: string;
  site_id: string;
  event_id: string | null;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
};

type MonitoringUpdate = {
  type: string;
  timestamp: string;
  site: Site;
  scan: Scan;
  events: MonitoringEvent[];
  alerts: Alert[];
  summary: {
    events_count: number;
    alerts_count: number;
  };
};

type Activity = {
  id: string;
  title: string;
  description: string;
  severity: string;
  site: string;
  timestamp: string;
  source?: string;
};

type AlertFilter =
  | "all"
  | "unread"
  | "findings"
  | "status"
  | "security";

type Camera = {
  id: number | string;
  name: string;
  location?: string | null;
  description?: string | null;
  source_type?: string | null;
  source_url?: string | null;
  is_active?: boolean;
  status?: string | null;
};

type SafetyEvent = {
  id: number | string;
  event_type?: string | null;
  title?: string | null;
  description?: string | null;
  severity?: string | null;
  risk_score?: number | null;
  confidence?: number | null;
  camera_id?: number | string | null;
  zone_id?: number | string | null;
  is_active?: boolean;
  created_at?: string | null;
  metadata?: Record<string, unknown> | null;
};

type Incident = {
  id: number | string;
  incident_type?: string | null;
  title?: string | null;
  description?: string | null;
  severity?: string | null;
  risk_score?: number | null;
  status?: string | null;
  event_id?: number | string | null;
  camera_id?: number | string | null;
  zone_id?: number | string | null;
  created_at?: string | null;
};

type Zone = {
  id: number | string;
  name: string;
  location?: string | null;
  description?: string | null;
  risk_level?: string | null;
  is_active?: boolean;
  polygon?: unknown;
};

type HealthState = {
  status: string;
  app?: string;
  version?: string;
  services?: {
    redis?: string;
    [key: string]: unknown;
  };
};

type SafetyCategory = {
  key: string;
  label: string;
  shortLabel: string;
  count: number;
  severity: string;
};

type LiveCameraState = {
  cameraId: number | string;
  status?: string;
  thread_alive?: boolean;
  frames_read?: number;
  frames_processed?: number;
  events_created?: number;
  last_error?: string | null;
  camera?: Camera;
  live_analysis?: {
    camera_id?: number | string;
    status?: string;
    thread_alive?: boolean;
    frames_read?: number;
    frames_processed?: number;
    events_created?: number;
    last_error?: string | null;
    message?: string;
    source?: string | null;
  };
};

type SafetyLiveMessage = {
  type?: string;
  timestamp?: string;
  camera_id?: number | string;
  camera_name?: string;
  event?: SafetyEvent;
  analysis?: Record<string, unknown>;
  status?: string;
  message?: string;
};

function extractArray<T>(data: unknown): T[] {
  if (Array.isArray(data)) {
    return data as T[];
  }

  if (data && typeof data === "object") {
    const object = data as Record<string, unknown>;

    const candidates = [
      object.items,
      object.results,
      object.data,
      object.events,
      object.incidents,
      object.cameras,
      object.zones,
    ];

    for (const candidate of candidates) {
      if (Array.isArray(candidate)) {
        return candidate as T[];
      }
    }
  }

  return [];
}

function normalizeLiveCameraState(
  data: unknown,
  cameraId: number | string,
): LiveCameraState {
  const value =
    data && typeof data === "object"
      ? (data as Record<string, unknown>)
      : {};

  const nested =
    value.live_analysis &&
    typeof value.live_analysis === "object"
      ? (value.live_analysis as Record<string, unknown>)
      : {};

  const camera =
    value.camera &&
    typeof value.camera === "object"
      ? (value.camera as Camera)
      : undefined;

  const normalizeCameraId = (
    candidate: unknown,
  ): number | string | undefined => {
    if (
      typeof candidate === "number" ||
      typeof candidate === "string"
    ) {
      return candidate;
    }

    return undefined;
  };

  const normalizedCameraId =
    normalizeCameraId(nested.camera_id) ??
    normalizeCameraId(value.cameraId) ??
    normalizeCameraId(value.camera_id) ??
    normalizeCameraId(camera?.id) ??
    cameraId;

  return {
    cameraId: normalizedCameraId,
    status:
      typeof nested.status === "string"
        ? nested.status
        : typeof value.status === "string"
          ? value.status
          : typeof camera?.status === "string"
            ? camera.status
            : "stopped",
    thread_alive:
      typeof nested.thread_alive === "boolean"
        ? nested.thread_alive
        : typeof value.thread_alive === "boolean"
          ? value.thread_alive
          : false,
    frames_read:
      typeof nested.frames_read === "number"
        ? nested.frames_read
        : typeof value.frames_read === "number"
          ? value.frames_read
          : 0,
    frames_processed:
      typeof nested.frames_processed === "number"
        ? nested.frames_processed
        : typeof value.frames_processed === "number"
          ? value.frames_processed
          : 0,
    events_created:
      typeof nested.events_created === "number"
        ? nested.events_created
        : typeof value.events_created === "number"
          ? value.events_created
          : 0,
    last_error:
      typeof nested.last_error === "string"
        ? nested.last_error
        : typeof value.last_error === "string"
          ? value.last_error
          : null,
    camera,
    live_analysis:
      value.live_analysis &&
      typeof value.live_analysis === "object"
        ? (value.live_analysis as LiveCameraState["live_analysis"])
        : undefined,
  };
}

function normalizeSafetyEvent(
  item: unknown,
  index: number,
): SafetyEvent {
  const value =
    item && typeof item === "object"
      ? (item as Record<string, unknown>)
      : {};

  return {
    id: (value.id ??
      value.event_id ??
      `safety-${index}`) as number | string,
    event_type: (value.event_type ??
      value.type ??
      null) as string | null,
    title: (value.title ??
      value.name ??
      null) as string | null,
    description: (value.description ??
      value.message ??
      null) as string | null,
    severity: (value.severity ??
      value.risk_level ??
      null) as string | null,
    risk_score:
      typeof value.risk_score === "number"
        ? value.risk_score
        : null,
    confidence:
      typeof value.confidence === "number"
        ? value.confidence
        : null,
    camera_id: (value.camera_id ??
      null) as number | string | null,
    zone_id: (value.zone_id ??
      null) as number | string | null,
    is_active:
      typeof value.is_active === "boolean"
        ? value.is_active
        : true,
    created_at: (value.created_at ??
      value.timestamp ??
      null) as string | null,
    metadata:
      value.metadata &&
      typeof value.metadata === "object"
        ? (value.metadata as Record<string, unknown>)
        : null,
  };
}

function normalizeIncident(
  item: unknown,
  index: number,
): Incident {
  const value =
    item && typeof item === "object"
      ? (item as Record<string, unknown>)
      : {};

  return {
    id: (value.id ??
      value.incident_id ??
      `incident-${index}`) as number | string,
    incident_type: (value.incident_type ??
      value.type ??
      null) as string | null,
    title: (value.title ??
      value.name ??
      null) as string | null,
    description: (value.description ??
      value.message ??
      null) as string | null,
    severity: (value.severity ??
      value.risk_level ??
      null) as string | null,
    risk_score:
      typeof value.risk_score === "number"
        ? value.risk_score
        : null,
    status: (value.status ??
      null) as string | null,
    event_id: (value.event_id ??
      null) as number | string | null,
    camera_id: (value.camera_id ??
      null) as number | string | null,
    zone_id: (value.zone_id ??
      null) as number | string | null,
    created_at: (value.created_at ??
      value.timestamp ??
      null) as string | null,
  };
}

export default function Home() {
  const [connected, setConnected] = useState(false);

  const [sites, setSites] = useState<Site[]>([]);
  const [updates, setUpdates] = useState<MonitoringUpdate[]>([]);
  const [lastUpdate, setLastUpdate] =
    useState<MonitoringUpdate | null>(null);

  const [loadingSites, setLoadingSites] = useState(true);
  const [sitesError, setSitesError] =
    useState<string | null>(null);
  const [retryingSites, setRetryingSites] =
    useState(false);

  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [alertsLoading, setAlertsLoading] =
    useState(true);
  const [alertsError, setAlertsError] =
    useState<string | null>(null);
  const [retryingAlerts, setRetryingAlerts] =
    useState(false);

  const [unreadAlertCount, setUnreadAlertCount] =
    useState(0);

  const [totalAlertCount, setTotalAlertCount] =
    useState(0);

  const [alertActionId, setAlertActionId] =
    useState<string | null>(null);

  const [markingAllRead, setMarkingAllRead] =
    useState(false);

  const [alertActionError, setAlertActionError] =
    useState<string | null>(null);

  const [alertFilter, setAlertFilter] =
    useState<AlertFilter>("all");

  const [cameras, setCameras] =
    useState<Camera[]>([]);

  const [zones, setZones] =
    useState<Zone[]>([]);

  const [safetyEvents, setSafetyEvents] =
    useState<SafetyEvent[]>([]);

  const [incidents, setIncidents] =
    useState<Incident[]>([]);

  const [health, setHealth] =
    useState<HealthState | null>(null);

  const [safetyLoading, setSafetyLoading] =
    useState(true);

  const [safetyRefreshing, setSafetyRefreshing] =
    useState(false);

  const [safetyError, setSafetyError] =
    useState<string | null>(null);

  const [liveCameraStates, setLiveCameraStates] =
    useState<Record<string, LiveCameraState>>({});

  const [cameraActionId, setCameraActionId] =
    useState<string | null>(null);

  const [safetyActivity, setSafetyActivity] =
    useState<Activity[]>([]);

  const wsRef =
    useRef<WebSocket | null>(null);

  const reconnectTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null,
    );

  async function fetchJson(
    path: string,
  ): Promise<unknown> {
    const response = await fetch(
      `${API_URL}${path}`,
      {
        cache: "no-store",
      },
    );

    if (!response.ok) {
      throw new Error(
        `${path} returned ${response.status}`,
      );
    }

    return response.json();
  }

  async function fetchOptional(
    paths: string[],
  ): Promise<unknown | null> {
    for (const path of paths) {
      try {
        return await fetchJson(path);
      } catch {
        continue;
      }
    }

    return null;
  }

  async function loadSites(
    isRetry = false,
  ) {
    if (isRetry) {
      setRetryingSites(true);
    } else {
      setLoadingSites(true);
    }

    setSitesError(null);

    try {
      const data =
        await fetchJson("/api/sites");

      const siteList =
        extractArray<Site>(data);

      setSites(siteList);
    } catch (error) {
      console.error(
        "Failed to load sites:",
        error,
      );

      setSitesError(
        "Unable to load registered sites. Make sure the SiteAegis backend is running.",
      );
    } finally {
      setLoadingSites(false);
      setRetryingSites(false);
    }
  }

  useEffect(() => {
    loadSites();
  }, []);

  async function loadAlerts(
    isRetry = false,
  ) {
    if (isRetry) {
      setRetryingAlerts(true);
    } else {
      setAlertsLoading(true);
    }

    setAlertsError(null);

    try {
      const alertsData =
        await fetchJson(
          "/api/alerts?limit=50",
        );

      const alertsList =
        extractArray<Alert>(
          alertsData,
        );

      const countData =
        await fetchJson(
          "/api/alerts/count",
        );

      setAlerts(alertsList);

      if (
        countData &&
        typeof countData === "object"
      ) {
        const countObject =
          countData as Record<string, unknown>;

        if (
          typeof countObject.total ===
          "number"
        ) {
          setTotalAlertCount(
            countObject.total,
          );
        }

        if (
          typeof countObject.unread ===
          "number"
        ) {
          setUnreadAlertCount(
            countObject.unread,
          );
        }
      }
    } catch (error) {
      console.error(
        "Failed to load alerts:",
        error,
      );

      setAlertsError(
        "Unable to load security alerts. Make sure the SiteAegis backend is running.",
      );
    } finally {
      setAlertsLoading(false);
      setRetryingAlerts(false);
    }
  }

  useEffect(() => {
    loadAlerts();
  }, []);

  async function loadSafetyDashboard(
    showLoading = false,
  ) {
    if (showLoading) {
      setSafetyLoading(true);
    } else {
      setSafetyRefreshing(true);
    }

    setSafetyError(null);

    try {
      const [
        camerasData,
        zonesData,
        safetyData,
        incidentsData,
        healthData,
      ] = await Promise.all([
        fetchOptional([
          "/api/cameras",
        ]),
        fetchOptional([
          "/api/zones",
        ]),
        fetchOptional([
          "/api/safety/events?limit=100",
          "/api/safety/events",
          "/api/safety?limit=100",
        ]),
        fetchOptional([
          "/api/incidents?limit=100",
          "/api/incidents",
        ]),
        fetchOptional([
          "/api/health",
        ]),
      ]);

      if (camerasData !== null) {
        setCameras(
          extractArray<Camera>(
            camerasData,
          ),
        );
      }

      if (zonesData !== null) {
        setZones(
          extractArray<Zone>(
            zonesData,
          ),
        );
      }

      if (safetyData !== null) {
        const rawEvents =
          extractArray<unknown>(
            safetyData,
          );

        const normalizedEvents =
          rawEvents.map(
            normalizeSafetyEvent,
          );

        normalizedEvents.sort(
          (a, b) => {
            const aTime =
              a.created_at
                ? new Date(
                    a.created_at,
                  ).getTime()
                : 0;

            const bTime =
              b.created_at
                ? new Date(
                    b.created_at,
                  ).getTime()
                : 0;

            return bTime - aTime;
          },
        );

        setSafetyEvents(
          normalizedEvents.slice(
            0,
            100,
          ),
        );
      }

      if (incidentsData !== null) {
        const rawIncidents =
          extractArray<unknown>(
            incidentsData,
          );

        const normalizedIncidents =
          rawIncidents.map(
            normalizeIncident,
          );

        normalizedIncidents.sort(
          (a, b) => {
            const aTime =
              a.created_at
                ? new Date(
                    a.created_at,
                  ).getTime()
                : 0;

            const bTime =
              b.created_at
                ? new Date(
                    b.created_at,
                  ).getTime()
                : 0;

            return bTime - aTime;
          },
        );

        setIncidents(
          normalizedIncidents.slice(
            0,
            100,
          ),
        );
      }

      if (healthData !== null) {
        setHealth(
          healthData as HealthState,
        );
      }

      if (
        camerasData === null &&
        zonesData === null &&
        safetyData === null &&
        incidentsData === null
      ) {
        throw new Error(
          "Safety API endpoints are unavailable.",
        );
      }
    } catch (error) {
      console.error(
        "Failed to load safety dashboard:",
        error,
      );

      setSafetyError(
        "Some safety intelligence data is unavailable. Web security monitoring remains active.",
      );
    } finally {
      setSafetyLoading(false);
      setSafetyRefreshing(false);
    }
  }

  useEffect(() => {
    loadSafetyDashboard(true);

    const interval =
      setInterval(() => {
        loadSafetyDashboard(false);
      }, 5000);

    return () =>
      clearInterval(interval);
  }, []);

  async function loadCameraStatus(
    cameraId: number | string,
  ) {
    try {
      const data =
        await fetchJson(
          `/api/cameras/${cameraId}/live/status`,
        );

      setLiveCameraStates(
        (previous) => ({
          ...previous,
          [String(cameraId)]:
            normalizeLiveCameraState(
              data,
              cameraId,
            ),
        }),
      );
    } catch (error) {
      console.warn(
        `Camera ${cameraId} status unavailable:`,
        error,
      );
    }
  }

  useEffect(() => {
    if (cameras.length === 0) {
      return;
    }

    cameras.forEach((camera) => {
      loadCameraStatus(camera.id);
    });
  }, [cameras]);

  useEffect(() => {
    const interval =
      setInterval(() => {
        cameras.forEach((camera) => {
          loadCameraStatus(camera.id);
        });
      }, 5000);

    return () =>
      clearInterval(interval);
  }, [cameras]);

  async function startLiveCamera(
    cameraId: number | string,
  ) {
    setCameraActionId(
      String(cameraId),
    );

    try {
      const response =
        await fetch(
          `${API_URL}/api/cameras/${cameraId}/live/start?frame_interval=1&loop_video=true`,
          {
            method: "POST",
          },
        );

      if (!response.ok) {
        throw new Error(
          `Camera start failed: ${response.status}`,
        );
      }

      const data =
        await response.json();

      setLiveCameraStates(
        (previous) => ({
          ...previous,
          [String(cameraId)]:
            normalizeLiveCameraState(
              data,
              cameraId,
            ),
        }),
      );

      setSafetyActivity(
        (previous) => [
          {
            id: `camera-start-${Date.now()}`,
            title:
              "Live camera analysis started",
            description:
              `Camera ${cameraId} is now being analyzed in the background.`,
            severity: "low",
            site:
              `Camera #${cameraId}`,
            timestamp:
              new Date().toISOString(),
            source: "camera",
          },
          ...previous,
        ].slice(0, 15),
      );
    } catch (error) {
      console.error(
        "Failed to start camera:",
        error,
      );

      setSafetyError(
        "Unable to start the selected live camera.",
      );
    } finally {
      setCameraActionId(null);

      setTimeout(() => {
        loadCameraStatus(
          cameraId,
        );
      }, 1000);
    }
  }

  async function stopLiveCamera(
    cameraId: number | string,
  ) {
    setCameraActionId(
      String(cameraId),
    );

    try {
      const response =
        await fetch(
          `${API_URL}/api/cameras/${cameraId}/live/stop`,
          {
            method: "POST",
          },
        );

      if (!response.ok) {
        throw new Error(
          `Camera stop failed: ${response.status}`,
        );
      }

      const data =
        await response.json();

      setLiveCameraStates(
        (previous) => ({
          ...previous,
          [String(cameraId)]:
            normalizeLiveCameraState(
              data,
              cameraId,
            ),
        }),
      );
    } catch (error) {
      console.error(
        "Failed to stop camera:",
        error,
      );

      setSafetyError(
        "Unable to stop the selected live camera.",
      );
    } finally {
      setCameraActionId(null);

      setTimeout(() => {
        loadCameraStatus(
          cameraId,
        );
      }, 500);
    }
  }

  async function markAlertAsRead(
    alertId: string,
  ) {
    if (!alertId) {
      return;
    }

    const selectedAlert =
      alerts.find(
        (alert) =>
          String(alert.alert_id) ===
          String(alertId),
      );

    if (
      !selectedAlert ||
      selectedAlert.is_read
    ) {
      return;
    }

    setAlertActionId(alertId);
    setAlertActionError(null);

    try {
      const response =
        await fetch(
          `${API_URL}/api/alerts/${alertId}/read`,
          {
            method: "PATCH",
          },
        );

      if (!response.ok) {
        throw new Error(
          `Mark alert failed: ${response.status}`,
        );
      }

      setAlerts((previous) =>
        previous.map((alert) =>
          String(alert.alert_id) ===
          String(alertId)
            ? {
                ...alert,
                is_read: true,
              }
            : alert,
        ),
      );

      setUnreadAlertCount(
        (previous) =>
          Math.max(
            0,
            previous - 1,
          ),
      );

      const countResponse =
        await fetch(
          `${API_URL}/api/alerts/count`,
          {
            cache: "no-store",
          },
        );

      if (countResponse.ok) {
        const countData =
          await countResponse.json();

        if (
          countData &&
          typeof countData.total ===
            "number"
        ) {
          setTotalAlertCount(
            countData.total,
          );
        }

        if (
          countData &&
          typeof countData.unread ===
            "number"
        ) {
          setUnreadAlertCount(
            countData.unread,
          );
        }
      }
    } catch (error) {
      console.error(
        "Failed to mark alert as read:",
        error,
      );

      setAlertActionError(
        "Could not mark this alert as read. Please try again.",
      );
    } finally {
      setAlertActionId(null);
    }
  }

  async function markAllAlertsAsRead() {
    if (markingAllRead) {
      return;
    }

    setMarkingAllRead(true);
    setAlertActionError(null);

    try {
      const response =
        await fetch(
          `${API_URL}/api/alerts/read-all`,
          {
            method: "PATCH",
          },
        );

      if (!response.ok) {
        throw new Error(
          `Mark all alerts failed: ${response.status}`,
        );
      }

      setAlerts((previous) =>
        previous.map((alert) => ({
          ...alert,
          is_read: true,
        })),
      );

      setUnreadAlertCount(0);

      const countResponse =
        await fetch(
          `${API_URL}/api/alerts/count`,
          {
            cache: "no-store",
          },
        );

      if (countResponse.ok) {
        const countData =
          await countResponse.json();

        if (
          countData &&
          typeof countData.total ===
            "number"
        ) {
          setTotalAlertCount(
            countData.total,
          );
        }

        if (
          countData &&
          typeof countData.unread ===
            "number"
        ) {
          setUnreadAlertCount(
            countData.unread,
          );
        }
      }
    } catch (error) {
      console.error(
        "Failed to mark all alerts as read:",
        error,
      );

      setAlertActionError(
        "Could not mark all alerts as read. Please try again.",
      );
    } finally {
      setMarkingAllRead(false);
    }
  }

  useEffect(() => {
    let effectActive = true;

    let initialConnectionTimer:
      | ReturnType<typeof setTimeout>
      | null = null;

    function clearReconnectTimer() {
      if (reconnectTimerRef.current) {
        clearTimeout(
          reconnectTimerRef.current,
        );

        reconnectTimerRef.current =
          null;
      }
    }

    function clearInitialConnectionTimer() {
      if (initialConnectionTimer) {
        clearTimeout(
          initialConnectionTimer,
        );

        initialConnectionTimer =
          null;
      }
    }

    function mergeRealtimeAlerts(
      incomingAlerts: Alert[],
    ) {
      if (
        !Array.isArray(
          incomingAlerts,
        ) ||
        incomingAlerts.length === 0
      ) {
        return;
      }

      setAlerts((previous) => {
        const incomingIds = new Set(
          incomingAlerts.map(
            (alert) =>
              String(alert.alert_id),
          ),
        );

        const existingWithoutDuplicates =
          previous.filter(
            (alert) =>
              !incomingIds.has(
                String(
                  alert.alert_id,
                ),
              ),
          );

        return [
          ...incomingAlerts,
          ...existingWithoutDuplicates,
        ].slice(0, 50);
      });
    }

    function handleMonitoringUpdate(
      data: MonitoringUpdate,
    ) {
      if (
        !data ||
        !data.site ||
        !data.scan
      ) {
        return;
      }

      setLastUpdate(data);

      setUpdates((previous) => {
        const next = [
          data,
          ...previous.filter(
            (item) =>
              String(
                item.scan?.scan_id,
              ) !==
              String(
                data.scan?.scan_id,
              ),
          ),
        ];

        return next.slice(0, 10);
      });

      setSites((previous) => {
        const updated =
          previous.map(
            (site) =>
              String(site.site_id) ===
              String(
                data.site.site_id,
              )
                ? {
                    ...site,
                    ...data.site,
                    last_scan_id:
                      data.scan.scan_id,
                    last_status:
                      data.scan.status,
                    last_risk_score:
                      data.scan.risk_score,
                    last_risk_level:
                      data.scan.risk_level,
                  }
                : site,
          );

        const exists =
          previous.some(
            (site) =>
              String(site.site_id) ===
              String(
                data.site.site_id,
              ),
          );

        if (!exists) {
          updated.push({
            ...data.site,
            last_scan_id:
              data.scan.scan_id,
            last_status:
              data.scan.status,
            last_risk_score:
              data.scan.risk_score,
            last_risk_level:
              data.scan.risk_level,
          });
        }

        return updated;
      });

      if (
        Array.isArray(
          data.alerts,
        ) &&
        data.alerts.length > 0
      ) {
        mergeRealtimeAlerts(
          data.alerts,
        );

        fetch(
          `${API_URL}/api/alerts/count`,
          {
            cache: "no-store",
          },
        )
          .then((response) =>
            response.ok
              ? response.json()
              : null,
          )
          .then((countData) => {
            if (
              countData &&
              typeof countData.total ===
                "number"
            ) {
              setTotalAlertCount(
                countData.total,
              );
            }

            if (
              countData &&
              typeof countData.unread ===
                "number"
            ) {
              setUnreadAlertCount(
                countData.unread,
              );
            }
          })
          .catch(console.error);
      } else if (
        data.summary &&
        data.summary.alerts_count > 0
      ) {
        loadAlerts();
      }
    }

    function handleSafetyMessage(
      data: SafetyLiveMessage,
    ) {
      const type =
        String(
          data?.type ?? "",
        ).toLowerCase();

      if (
        type ===
          "camera_safety_event" &&
        data.event
      ) {
        const event =
          normalizeSafetyEvent(
            data.event,
            Date.now(),
          );

        setSafetyEvents(
          (previous) => [
            event,
            ...previous.filter(
              (item) =>
                String(
                  item.id,
                ) !==
                String(event.id),
            ),
          ].slice(0, 100),
        );

        setSafetyActivity(
          (previous) => [
            {
              id: `safety-${event.id}-${Date.now()}`,
              title:
                event.title ??
                "Safety event detected",
              description:
                event.description ??
                "A construction-site safety event was detected.",
              severity:
                event.severity ??
                "medium",
              site:
                data.camera_name ??
                `Camera #${data.camera_id ?? "—"}`,
              timestamp:
                event.created_at ??
                data.timestamp ??
                new Date().toISOString(),
              source: "safety",
            },
            ...previous,
          ].slice(0, 15),
        );

        return;
      }

      if (
        type ===
          "camera_analysis_status" ||
        type ===
          "camera_analysis_error"
      ) {
        setSafetyActivity(
          (previous) => [
            {
              id: `camera-${Date.now()}`,
              title:
                data.message ??
                "Camera analysis update",
              description:
                `Camera #${data.camera_id ?? "—"} analysis status changed.`,
              severity:
                type ===
                "camera_analysis_error"
                  ? "high"
                  : "low",
              site:
                data.camera_name ??
                `Camera #${data.camera_id ?? "—"}`,
              timestamp:
                data.timestamp ??
                new Date().toISOString(),
              source: "camera",
            },
            ...previous,
          ].slice(0, 15),
        );
      }
    }

    function scheduleReconnect() {
      if (!effectActive) {
        return;
      }

      if (
        reconnectTimerRef.current
      ) {
        return;
      }

      reconnectTimerRef.current =
        setTimeout(() => {
          reconnectTimerRef.current =
            null;

          if (effectActive) {
            connectWebSocket();
          }
        }, 3000);
    }

    function connectWebSocket() {
      if (!effectActive) {
        return;
      }

      if (
        wsRef.current &&
        (
          wsRef.current.readyState ===
            WebSocket.OPEN ||
          wsRef.current.readyState ===
            WebSocket.CONNECTING
        )
      ) {
        return;
      }

      clearReconnectTimer();

      const ws =
        new WebSocket(WS_URL);

      wsRef.current = ws;

      ws.onopen = () => {
        if (
          !effectActive ||
          wsRef.current !== ws
        ) {
          return;
        }

        setConnected(true);

        try {
          ws.send(
            JSON.stringify({
              type: "client_connected",
              source:
                "siteaegis_dashboard",
            }),
          );
        } catch {
          // Ignore handshake errors.
        }
      };

      ws.onmessage = (event) => {
        if (
          !effectActive ||
          wsRef.current !== ws
        ) {
          return;
        }

        try {
          const data =
            JSON.parse(
              event.data,
            );

          if (
            data?.type ===
              "connection" ||
            data?.type ===
              "ack"
          ) {
            return;
          }

          if (
            data?.type ===
              "monitoring_update" ||
            data?.type ===
              "site_update"
          ) {
            handleMonitoringUpdate(
              data as MonitoringUpdate,
            );

            return;
          }

          if (
            String(
              data?.type ?? "",
            ).startsWith(
              "camera_",
            )
          ) {
            handleSafetyMessage(
              data as SafetyLiveMessage,
            );

            return;
          }
        } catch (error) {
          console.error(
            "Invalid WebSocket message:",
            error,
          );
        }
      };

      ws.onerror = () => {
        if (
          !effectActive ||
          wsRef.current !== ws
        ) {
          return;
        }
      };

      ws.onclose = () => {
        if (
          wsRef.current === ws
        ) {
          wsRef.current = null;
        }

        if (!effectActive) {
          return;
        }

        setConnected(false);
        scheduleReconnect();
      };
    }

    initialConnectionTimer =
      setTimeout(() => {
        initialConnectionTimer =
          null;

        if (effectActive) {
          connectWebSocket();
        }
      }, 100);

    return () => {
      effectActive = false;

      clearInitialConnectionTimer();
      clearReconnectTimer();

      const ws =
        wsRef.current;

      wsRef.current = null;

      setConnected(false);

      if (ws) {
        try {
          if (
            ws.readyState ===
              WebSocket.OPEN ||
            ws.readyState ===
              WebSocket.CONNECTING
          ) {
            ws.close(
              1000,
              "Component cleanup",
            );
          }
        } catch {
          // Ignore cleanup errors.
        }
      }
    };
  }, []);

  const monitoredSites =
    sites.filter(
      (site) =>
        site.monitoring_enabled !==
        false,
    );

  const onlineSites =
    monitoredSites.filter(
      (site) =>
        String(
          site.last_status ??
            "",
        ).toLowerCase() ===
        "online",
    ).length;

  const latestRisk =
    lastUpdate?.scan.risk_score ??
    monitoredSites.find(
      (site) =>
        site.last_risk_score !==
          null &&
        site.last_risk_score !==
          undefined,
    )?.last_risk_score ??
    null;

  const latestResponse =
    lastUpdate?.scan
      .response_time_ms ??
    null;

  const unreadAlerts =
    unreadAlertCount;

  const openIncidents =
    incidents.filter(
      (incident) => {
        const status =
          String(
            incident.status ??
              "open",
          ).toLowerCase();

        return (
          status === "open" ||
          status === "active" ||
          status === "investigating"
        );
      },
    );

  const activeSafetyEvents =
    safetyEvents.filter(
      (event) =>
        event.is_active !== false,
    );

  const criticalSafetyEvents =
    activeSafetyEvents.filter(
      (event) =>
        String(
          event.severity ??
            "",
        ).toLowerCase() ===
          "critical" ||
        Number(
          event.risk_score ?? 0,
        ) >= 90,
    ).length;

  const detectionCategories =
    useMemo<
      SafetyCategory[]
    >(() => {
      const definitions = [
        {
          key: "ppe",
          label: "PPE",
          shortLabel: "PPE",
          matches: [
            "ppe",
            "helmet",
            "hardhat",
            "safety_vest",
            "no_hardhat",
            "no-safety vest",
            "safety vest",
          ],
        },
        {
          key: "restricted_zone",
          label:
            "Restricted Zone",
          shortLabel: "ZONE",
          matches: [
            "restricted_zone",
            "zone_entry",
            "restricted",
          ],
        },
        {
          key: "proximity",
          label:
            "Worker–Machine",
          shortLabel:
            "PROXIMITY",
          matches: [
            "worker_machine_proximity",
            "proximity",
          ],
        },
        {
          key: "crowding",
          label: "Crowding",
          shortLabel:
            "CROWDING",
          matches: [
            "crowding",
            "crowd",
          ],
        },
        {
          key: "fall",
          label: "Falls",
          shortLabel: "FALL",
          matches: [
            "fall",
            "worker_fall",
          ],
        },
        {
          key: "unsafe_movement",
          label:
            "Unsafe Movement",
          shortLabel:
            "MOVEMENT",
          matches: [
            "unsafe_movement",
            "unsafe movement",
          ],
        },
      ];

      return definitions.map(
        (definition) => {
          const matchingEvents =
            safetyEvents.filter(
              (event) => {
                const type =
                  String(
                    event.event_type ??
                      "",
                  ).toLowerCase();

                const title =
                  String(
                    event.title ??
                      "",
                  ).toLowerCase();

                return definition.matches.some(
                  (match) =>
                    type.includes(
                      match,
                    ) ||
                    title.includes(
                      match,
                    ),
                );
              },
            );

          const hasCritical =
            matchingEvents.some(
              (event) =>
                String(
                  event.severity ??
                    "",
                ).toLowerCase() ===
                  "critical" ||
                Number(
                  event.risk_score ??
                    0,
                ) >= 90,
            );

          const hasHigh =
            matchingEvents.some(
              (event) =>
                String(
                  event.severity ??
                    "",
                ).toLowerCase() ===
                  "high" ||
                Number(
                  event.risk_score ??
                    0,
                ) >= 70,
            );

          return {
            key: definition.key,
            label: definition.label,
            shortLabel:
              definition.shortLabel,
            count:
              matchingEvents.length,
            severity:
              hasCritical
                ? "critical"
                : hasHigh
                  ? "high"
                  : matchingEvents.length >
                      0
                    ? "medium"
                    : "low",
          };
        },
      );
    }, [safetyEvents]);

  const latestSafetyEvents =
    useMemo(
      () =>
        safetyEvents
          .slice()
          .sort(
            (a, b) => {
              const aTime =
                a.created_at
                  ? new Date(
                      a.created_at,
                    ).getTime()
                  : 0;

              const bTime =
                b.created_at
                  ? new Date(
                      b.created_at,
                    ).getTime()
                  : 0;

              return (
                bTime - aTime
              );
            },
          )
          .slice(0, 8),
      [safetyEvents],
    );

  const activities =
    useMemo<Activity[]>(
      () => {
        const result: Activity[] =
          [];

        for (const update of updates) {
          if (
            update.events &&
            update.events.length > 0
          ) {
            for (
              const event of
                update.events
            ) {
              result.push({
                id:
                  event.event_id ??
                  `${update.scan.scan_id}-${result.length}`,
                title:
                  event.title ??
                  "Monitoring change detected",
                description:
                  event.description ??
                  "A change was detected during monitoring.",
                severity:
                  event.severity ??
                  "info",
                site:
                  update.site.name,
                timestamp:
                  update.timestamp,
                source: "web",
              });
            }
          } else {
            result.push({
              id:
                update.scan.scan_id,
              title:
                "Monitoring scan completed",
              description:
                `${update.site.hostname} scanned successfully.`,
              severity:
                "info",
              site:
                update.site.name,
              timestamp:
                update.timestamp,
              source: "web",
            });
          }
        }

        return [
          ...safetyActivity,
          ...result,
        ]
          .sort(
            (a, b) =>
              new Date(
                b.timestamp,
              ).getTime() -
              new Date(
                a.timestamp,
              ).getTime(),
          )
          .slice(0, 15);
      },
      [
        updates,
        safetyActivity,
      ],
    );

  const filteredAlerts =
    useMemo(() => {
      switch (alertFilter) {
        case "unread":
          return alerts.filter(
            (alert) =>
              !alert.is_read,
          );

        case "findings":
          return alerts.filter(
            (alert) =>
              alert.alert_type
                .toUpperCase()
                .includes("FINDING"),
          );

        case "status":
          return alerts.filter(
            (alert) =>
              alert.alert_type
                .toUpperCase()
                .includes("STATUS"),
          );

        case "security":
          return alerts.filter(
            (alert) => {
              const type =
                alert.alert_type.toUpperCase();

              return (
                type.includes("RISK") ||
                type.includes("SSL") ||
                type.includes(
                  "SECURITY",
                )
              );
            },
          );

        default:
          return alerts;
      }
    }, [alerts, alertFilter]);

  const alertFilterCounts =
    useMemo(() => {
      return {
        all: alerts.length,

        unread: alerts.filter(
          (alert) =>
            !alert.is_read,
        ).length,

        findings: alerts.filter(
          (alert) =>
            alert.alert_type
              .toUpperCase()
              .includes("FINDING"),
        ).length,

        status: alerts.filter(
          (alert) =>
            alert.alert_type
              .toUpperCase()
              .includes("STATUS"),
        ).length,

        security: alerts.filter(
          (alert) => {
            const type =
              alert.alert_type.toUpperCase();

            return (
              type.includes("RISK") ||
              type.includes("SSL") ||
              type.includes(
                "SECURITY",
              )
            );
          },
        ).length,
      };
    }, [alerts]);

  function formatTime(
    timestamp?: string | null,
  ) {
    if (!timestamp) {
      return "--";
    }

    try {
      return new Date(
        timestamp,
      ).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return "--";
    }
  }

  function formatDateTime(
    timestamp?: string | null,
  ) {
    if (!timestamp) {
      return "--";
    }

    try {
      return new Date(
        timestamp,
      ).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "--";
    }
  }

  function riskClass(
    level?: string | null,
  ) {
    if (!level) {
      return "";
    }

    return level.toLowerCase();
  }

  function severityClass(
    severity?: string | null,
  ) {
    if (!severity) {
      return "low";
    }

    const normalized =
      severity.toLowerCase();

    if (
      [
        "critical",
        "high",
        "medium",
        "low",
      ].includes(normalized)
    ) {
      return normalized;
    }

    return "low";
  }

  function alertSeverityClass(
    severity?: string | null,
  ) {
    if (!severity) {
      return "info";
    }

    return severity.toLowerCase();
  }

  function alertFilterLabel(
    filter: AlertFilter,
  ) {
    switch (filter) {
      case "all":
        return "ALL";
      case "unread":
        return "UNREAD";
      case "findings":
        return "FINDINGS";
      case "status":
        return "STATUS";
      case "security":
        return "SECURITY";
      default:
        return "ALL";
    }
  }

  function humanizeEventType(
    eventType?: string | null,
  ) {
    if (!eventType) {
      return "Safety event";
    }

    return eventType
      .replaceAll("_", " ")
      .replace(/\b\w/g, (char) =>
        char.toUpperCase(),
      );
  }

  function cameraIsRunning(
    camera: Camera,
  ) {
    const state =
      liveCameraStates[
        String(camera.id)
      ];

    if (!state) {
      return (
        String(
          camera.status ??
            "",
        ).toLowerCase() ===
          "running" ||
        String(
          camera.status ??
            "",
        ).toLowerCase() ===
          "online"
      );
    }

    const status =
      String(
        state.status ??
          "",
      ).toLowerCase();

    return (
      state.thread_alive === true ||
      status === "running" ||
      status === "starting"
    );
  }

  return (
    <main className="dashboard">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            SA
          </div>

          <div>
            <h1>SiteAegis</h1>

            <p>
              Security Intelligence Platform
            </p>
          </div>
        </div>

        <div className="connection">
          <span
            className={`connection-dot ${
              connected
                ? "connected"
                : "disconnected"
            }`}
          />

          <span>
            {connected
              ? "LIVE MONITORING"
              : "DISCONNECTED"}
          </span>
        </div>
      </header>

      <section className="hero">
        <div>
          <span className="eyebrow">
            REAL-TIME WEB + SITE SAFETY
          </span>

          <h2>
            Observe.
            <br />
            <span>Detect.</span>
            <br />
            Respond.
          </h2>

          <p>
            SiteAegis continuously
            monitors registered
            websites and construction
            environments, evaluates
            security and safety risk,
            detects hazardous activity,
            and delivers live
            intelligence through a
            unified monitoring stream.
          </p>
        </div>

        <div className="live-card">
          <div className="pulse-ring">
            <span />
          </div>

          <div>
            <strong>
              {connected
                ? "SYSTEM ONLINE"
                : "SYSTEM OFFLINE"}
            </strong>

            <small>
              {connected
                ? "WebSocket stream active"
                : "Live stream unavailable — reconnecting"}
            </small>
          </div>
        </div>
      </section>

      <section className="stats-grid">
        <div className="stat-card">
          <span className="stat-label">
            MONITORED SITES
          </span>

          <strong>
            {loadingSites
              ? "—"
              : sitesError
                ? "!"
                : monitoredSites.length}
          </strong>

          <small>
            Registered monitoring targets
          </small>
        </div>

        <div className="stat-card">
          <span className="stat-label">
            ONLINE
          </span>

          <strong className="online">
            {loadingSites
              ? "—"
              : sitesError
                ? "—"
                : onlineSites}
          </strong>

          <small>
            Currently reported online
          </small>
        </div>

        <div className="stat-card">
          <span className="stat-label">
            CURRENT RISK
          </span>

          <strong
            className={riskClass(
              lastUpdate?.scan
                .risk_level,
            )}
          >
            {latestRisk !== null
              ? latestRisk
              : "—"}
          </strong>

          <small>
            Latest web security score
          </small>
        </div>

        <div className="stat-card">
          <span className="stat-label">
            UNREAD ALERTS
          </span>

          <strong>
            {alertsLoading
              ? "—"
              : alertsError
                ? "!"
                : unreadAlerts}
          </strong>

          <small>
            Security alerts requiring attention
          </small>
        </div>
      </section>

      <section className="safety-stats-grid">
        <div className="safety-stat-card">
          <div className="safety-stat-top">
            <span className="stat-label">
              CAMERAS
            </span>

            <span className="safety-mini-icon">
              CAM
            </span>
          </div>

          <strong>
            {safetyLoading
              ? "—"
              : cameras.length}
          </strong>

          <small>
            Registered site cameras
          </small>
        </div>

        <div className="safety-stat-card">
          <div className="safety-stat-top">
            <span className="stat-label">
              ACTIVE EVENTS
            </span>

            <span className="safety-mini-icon">
              EVT
            </span>
          </div>

          <strong
            className={
              criticalSafetyEvents >
              0
                ? "critical"
                : ""
            }
          >
            {safetyLoading
              ? "—"
              : activeSafetyEvents.length}
          </strong>

          <small>
            Detected safety conditions
          </small>
        </div>

        <div className="safety-stat-card">
          <div className="safety-stat-top">
            <span className="stat-label">
              OPEN INCIDENTS
            </span>

            <span className="safety-mini-icon">
              INC
            </span>
          </div>

          <strong
            className={
              openIncidents.length >
              0
                ? "high"
                : "low"
            }
          >
            {safetyLoading
              ? "—"
              : openIncidents.length}
          </strong>

          <small>
            Incidents requiring response
          </small>
        </div>

        <div className="safety-stat-card">
          <div className="safety-stat-top">
            <span className="stat-label">
              RESTRICTED ZONES
            </span>

            <span className="safety-mini-icon">
              ZONE
            </span>
          </div>

          <strong>
            {safetyLoading
              ? "—"
              : zones.length}
          </strong>

          <small>
            Configured safety boundaries
          </small>
        </div>
      </section>

      {safetyError && (
        <div className="dashboard-notice">
          <span className="notice-dot" />

          <span>
            {safetyError}
          </span>

          <button
            type="button"
            onClick={() =>
              loadSafetyDashboard(
                false,
              )
            }
            disabled={
              safetyRefreshing
            }
          >
            {safetyRefreshing
              ? "REFRESHING..."
              : "REFRESH SAFETY"}
          </button>
        </div>
      )}

      <section className="content-grid">
        <div className="panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">
                TARGET
              </span>

              <h3>
                Latest monitored site
              </h3>
            </div>

            <div className="status-badge">
              <span
                className={
                  lastUpdate?.scan
                    .status ===
                  "online"
                    ? "online"
                    : ""
                }
              />

              {lastUpdate?.scan
                .status ??
                (sitesError
                  ? "OFFLINE"
                  : "WAITING")}
            </div>
          </div>

          {sitesError ? (
            <div className="empty-state">
              <div className="empty-icon">
                !
              </div>

              <h4>
                Monitoring data unavailable
              </h4>

              <p>
                SiteAegis could not
                retrieve the registered
                monitoring targets.
              </p>

              <button
                type="button"
                className="secondary-button"
                onClick={() =>
                  loadSites(true)
                }
                disabled={
                  retryingSites
                }
              >
                {retryingSites
                  ? "RETRYING..."
                  : "RETRY"}
              </button>
            </div>
          ) : loadingSites ? (
            <div className="empty-state">
              <div className="empty-icon">
                ◌
              </div>

              <h4>
                Loading monitoring targets
              </h4>

              <p>
                SiteAegis is retrieving
                registered websites.
              </p>
            </div>
          ) : lastUpdate ? (
            <div className="site-content">
              <div className="site-identity">
                <div className="site-icon">
                  {lastUpdate.site.name
                    .slice(0, 2)
                    .toUpperCase()}
                </div>

                <div>
                  <h4>
                    {
                      lastUpdate.site
                        .name
                    }
                  </h4>

                  <a
                    href={
                      lastUpdate.site
                        .url
                    }
                    target="_blank"
                    rel="noreferrer"
                  >
                    {
                      lastUpdate.site
                        .url
                    }
                  </a>
                </div>
              </div>

              <div className="metrics">
                <div>
                  <span>RISK</span>

                  <strong
                    className={riskClass(
                      lastUpdate
                        .scan
                        .risk_level,
                    )}
                  >
                    {lastUpdate.scan
                      .risk_score ??
                      "—"}
                  </strong>
                </div>

                <div>
                  <span>
                    RESPONSE
                  </span>

                  <strong>
                    {latestResponse !==
                    null
                      ? `${latestResponse} ms`
                      : "—"}
                  </strong>
                </div>

                <div>
                  <span>
                    STATUS CODE
                  </span>

                  <strong>
                    {lastUpdate.scan
                      .status_code ??
                      "—"}
                  </strong>
                </div>

                <div>
                  <span>
                    IP ADDRESS
                  </span>

                  <strong>
                    {lastUpdate.scan
                      .ip_address ??
                      "—"}
                  </strong>
                </div>
              </div>

              <div className="scan-meta">
                <span>
                  SCAN #
                  {
                    lastUpdate.scan
                      .scan_id
                  }
                </span>

                <span>
                  {formatTime(
                    lastUpdate.timestamp,
                  )}
                </span>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">
                ◌
              </div>

              <h4>
                Waiting for live telemetry
              </h4>

              <p>
                Registered sites are
                available, but no live
                monitoring update has
                arrived yet.
              </p>
            </div>
          )}
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <span className="eyebrow">
                LIVE STREAM
              </span>

              <h3>
                Unified activity
              </h3>
            </div>

            <span className="event-count">
              {activities.length} EVENTS
            </span>
          </div>

          {!connected &&
          activities.length === 0 ? (
            <div className="empty-activity">
              <div className="stream-line" />

              <p>
                Live monitoring stream
                is currently disconnected.
                SiteAegis will reconnect
                automatically.
              </p>
            </div>
          ) : activities.length > 0 ? (
            <div className="activity-list">
              {activities.map(
                (activity) => (
                  <div
                    className="activity-item"
                    key={activity.id}
                  >
                    <div className="activity-indicator">
                      <span
                        className={
                          activity.source ===
                          "safety"
                            ? "safety"
                            : activity.source ===
                                "camera"
                              ? "camera"
                              : ""
                        }
                      />
                    </div>

                    <div className="activity-body">
                      <div className="activity-title-line">
                        <strong>
                          {
                            activity.title
                          }
                        </strong>

                        {activity.source && (
                          <span className="activity-source">
                            {activity.source}
                          </span>
                        )}
                      </div>

                      <p>
                        {
                          activity.description
                        }
                      </p>

                      <time>
                        {
                          activity.site
                        }{" "}
                        ·{" "}
                        {formatTime(
                          activity.timestamp,
                        )}
                      </time>
                    </div>
                  </div>
                ),
              )}
            </div>
          ) : (
            <div className="empty-activity">
              <div className="stream-line" />

              <p>
                Connected successfully.
                Waiting for the first
                monitoring event.
              </p>
            </div>
          )}
        </div>
      </section>

      <section className="panel safety-panel">
        <div className="panel-header">
          <div>
            <span className="eyebrow">
              CONSTRUCTION SAFETY
            </span>

            <h3>
              Safety intelligence
            </h3>
          </div>

          <div className="panel-header-actions">
            <span className="event-count">
              {safetyRefreshing
                ? "SYNCING"
                : "LIVE"}
            </span>

            <button
              type="button"
              className="small-action-button"
              onClick={() =>
                loadSafetyDashboard(
                  false,
                )
              }
              disabled={
                safetyRefreshing
              }
            >
              {safetyRefreshing
                ? "..."
                : "REFRESH"}
            </button>
          </div>
        </div>

        <div className="safety-category-grid">
          {detectionCategories.map(
            (category) => (
              <div
                className={`detection-card ${severityClass(
                  category.severity,
                )}`}
                key={category.key}
              >
                <div className="detection-card-top">
                  <span>
                    {
                      category.shortLabel
                    }
                  </span>

                  <span
                    className={`severity-dot ${severityClass(
                      category.severity,
                    )}`}
                  />
                </div>

                <strong>
                  {category.count}
                </strong>

                <small>
                  {category.label}
                </small>
              </div>
            ),
          )}
        </div>

        <div className="safety-columns">
          <div className="safety-events-column">
            <div className="subpanel-heading">
              <div>
                <span className="eyebrow">
                  DETECTIONS
                </span>

                <h4>
                  Recent safety events
                </h4>
              </div>

              <span className="event-count">
                {
                  latestSafetyEvents.length
                }{" "}
                RECENT
              </span>
            </div>

            {latestSafetyEvents.length ===
            0 ? (
              <div className="compact-empty">
                <span>
                  ◌
                </span>

                <p>
                  No safety events
                  have been recorded
                  yet.
                </p>
              </div>
            ) : (
              <div className="safety-event-list">
                {latestSafetyEvents.map(
                  (event) => (
                    <div
                      className="safety-event-item"
                      key={String(
                        event.id,
                      )}
                    >
                      <div
                        className={`event-severity ${severityClass(
                          event.severity,
                        )}`}
                      >
                        {String(
                          event.severity ??
                            "LOW",
                        )
                          .slice(
                            0,
                            1,
                          )
                          .toUpperCase()}
                      </div>

                      <div className="safety-event-body">
                        <div className="safety-event-title">
                          <strong>
                            {event.title ??
                              humanizeEventType(
                                event.event_type,
                              )}
                          </strong>

                          {event.risk_score !==
                            null &&
                            event.risk_score !==
                              undefined && (
                              <span>
                                RISK{" "}
                                {
                                  event.risk_score
                                }
                              </span>
                            )}
                        </div>

                        <p>
                          {event.description ??
                            humanizeEventType(
                              event.event_type,
                            )}
                        </p>

                        <time>
                          {event.camera_id !==
                            null &&
                            event.camera_id !==
                              undefined &&
                            `CAMERA #${event.camera_id} · `}
                          {event.zone_id !==
                            null &&
                            event.zone_id !==
                              undefined &&
                            `ZONE #${event.zone_id} · `}
                          {formatDateTime(
                            event.created_at,
                          )}
                        </time>
                      </div>
                    </div>
                  ),
                )}
              </div>
            )}
          </div>

          <div className="incident-column">
            <div className="subpanel-heading">
              <div>
                <span className="eyebrow">
                  RESPONSE
                </span>

                <h4>
                  Open incidents
                </h4>
              </div>

              <span
                className={
                  openIncidents.length >
                  0
                    ? "incident-count critical"
                    : "incident-count low"
                }
              >
                {
                  openIncidents.length
                }
              </span>
            </div>

            {openIncidents.length ===
            0 ? (
              <div className="compact-empty">
                <span>
                  ✓
                </span>

                <p>
                  No open safety
                  incidents.
                </p>
              </div>
            ) : (
              <div className="incident-list">
                {openIncidents
                  .slice(0, 6)
                  .map(
                    (incident) => (
                      <div
                        className="incident-item"
                        key={String(
                          incident.id,
                        )}
                      >
                        <div
                          className={`event-severity ${severityClass(
                            incident.severity,
                          )}`}
                        >
                          !
                        </div>

                        <div className="incident-body">
                          <div className="safety-event-title">
                            <strong>
                              {incident.title ??
                                humanizeEventType(
                                  incident.incident_type,
                                )}
                            </strong>

                            <span>
                              {
                                incident.status ??
                                "OPEN"
                              }
                            </span>
                          </div>

                          <p>
                            {incident.description ??
                              "Safety incident requires review."}
                          </p>

                          <time>
                            {incident.risk_score !==
                              null &&
                              incident.risk_score !==
                                undefined &&
                              `RISK ${incident.risk_score} · `}
                            {formatDateTime(
                              incident.created_at,
                            )}
                          </time>
                        </div>
                      </div>
                    ),
                  )}
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="panel cameras-panel">
        <div className="panel-header">
          <div>
            <span className="eyebrow">
              VIDEO INTELLIGENCE
            </span>

            <h3>
              Site cameras
            </h3>
          </div>

          <span className="event-count">
            {cameras.length} CAMERAS
          </span>
        </div>

        {cameras.length === 0 ? (
          <div className="compact-empty camera-empty">
            <span>
              CAM
            </span>

            <p>
              No cameras are currently
              registered with SiteAegis.
            </p>
          </div>
        ) : (
          <div className="camera-grid">
            {cameras.map(
              (camera) => {
                const state =
                  liveCameraStates[
                    String(
                      camera.id,
                    )
                  ];

                const running =
                  cameraIsRunning(
                    camera,
                  );

                const frameCount =
                  state?.frames_processed ??
                  state?.live_analysis
                    ?.frames_processed ??
                  0;

                const eventCount =
                  state?.events_created ??
                  state?.live_analysis
                    ?.events_created ??
                  0;

                const cameraStatus =
                  state?.status ??
                  state?.live_analysis
                    ?.status ??
                  camera.status ??
                  "offline";

                return (
                  <div
                    className={`camera-card ${
                      running
                        ? "running"
                        : ""
                    }`}
                    key={String(
                      camera.id,
                    )}
                  >
                    <div className="camera-visual">
                      <div className="camera-grid-lines" />

                      <div className="camera-status-pill">
                        <span
                          className={
                            running
                              ? "online"
                              : "offline"
                          }
                        />

                        {running
                          ? "ANALYZING"
                          : "STANDBY"}
                      </div>

                      <div className="camera-center">
                        <span>
                          CAM
                        </span>

                        <strong>
                          #
                          {
                            camera.id
                          }
                        </strong>
                      </div>
                    </div>

                    <div className="camera-content">
                      <div className="camera-title-row">
                        <div>
                          <h4>
                            {
                              camera.name
                            }
                          </h4>

                          <p>
                            {camera.location ??
                              "Construction site"}
                          </p>
                        </div>

                        <span className="camera-type">
                          {String(
                            camera.source_type ??
                              "SOURCE",
                          ).toUpperCase()}
                        </span>
                      </div>

                      <div className="camera-metrics">
                        <div>
                          <span>
                            FRAMES
                          </span>

                          <strong>
                            {
                              frameCount
                            }
                          </strong>
                        </div>

                        <div>
                          <span>
                            EVENTS
                          </span>

                          <strong>
                            {
                              eventCount
                            }
                          </strong>
                        </div>

                        <div>
                          <span>
                            STATUS
                          </span>

                          <strong>
                            {cameraStatus}
                          </strong>
                        </div>
                      </div>

                      {state?.last_error && (
                        <div className="camera-error">
                          {state.last_error}
                        </div>
                      )}

                      <div className="camera-actions">
                        {!running ? (
                          <button
                            type="button"
                            className="camera-start-button"
                            onClick={() =>
                              startLiveCamera(
                                camera.id,
                              )
                            }
                            disabled={
                              cameraActionId ===
                              String(
                                camera.id,
                              )
                            }
                          >
                            {cameraActionId ===
                            String(
                              camera.id,
                            )
                              ? "STARTING..."
                              : "START LIVE ANALYSIS"}
                          </button>
                        ) : (
                          <button
                            type="button"
                            className="camera-stop-button"
                            onClick={() =>
                              stopLiveCamera(
                                camera.id,
                              )
                            }
                            disabled={
                              cameraActionId ===
                              String(
                                camera.id,
                              )
                            }
                          >
                            {cameraActionId ===
                            String(
                              camera.id,
                            )
                              ? "STOPPING..."
                              : "STOP ANALYSIS"}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              },
            )}
          </div>
        )}
      </section>

      <section className="panel alerts-panel">
        <div className="panel-header">
          <div>
            <span className="eyebrow">
              SECURITY ALERTS
            </span>

            <h3>
              Alert Center
            </h3>

            <small className="panel-subtitle">
              {totalAlertCount || alerts.length} total alerts ·{" "}
              {unreadAlerts} requiring
              attention
            </small>
          </div>

          <div className="alerts-actions">
            <span className="event-count">
              {alertsLoading
                ? "— UNREAD"
                : `${unreadAlerts} UNREAD`}
            </span>

            {unreadAlerts > 0 && (
              <button
                type="button"
                onClick={
                  markAllAlertsAsRead
                }
                disabled={
                  markingAllRead
                }
                className="mark-all-button"
              >
                {markingAllRead
                  ? "MARKING..."
                  : "MARK ALL READ"}
              </button>
            )}
          </div>
        </div>

        {alertActionError && (
          <div className="alert-action-error">
            {alertActionError}
          </div>
        )}

        {alertsError ? (
          <div className="empty-state">
            <div className="empty-icon">
              !
            </div>

            <h4>
              Alert service unavailable
            </h4>

            <p>
              SiteAegis could not
              retrieve security alerts.
            </p>

            <button
              type="button"
              className="secondary-button"
              onClick={() =>
                loadAlerts(true)
              }
              disabled={
                retryingAlerts
              }
            >
              {retryingAlerts
                ? "RETRYING..."
                : "RETRY ALERTS"}
            </button>
          </div>
        ) : (
          <>
            {!alertsLoading &&
              alerts.length > 0 && (
                <div className="alert-toolbar">
                  <div className="alert-filters">
                    {(
                      [
                        "all",
                        "unread",
                        "findings",
                        "status",
                        "security",
                      ] as AlertFilter[]
                    ).map(
                      (
                        filter,
                      ) => {
                        const active =
                          alertFilter ===
                          filter;

                        return (
                          <button
                            key={
                              filter
                            }
                            type="button"
                            onClick={() =>
                              setAlertFilter(
                                filter,
                              )
                            }
                            className={
                              active
                                ? "active"
                                : ""
                            }
                          >
                            {alertFilterLabel(
                              filter,
                            )}{" "}
                            <span>
                              {
                                alertFilterCounts[
                                  filter
                                ]
                              }
                            </span>
                          </button>
                        );
                      },
                    )}
                  </div>

                  <span className="showing-count">
                    Showing{" "}
                    {
                      filteredAlerts.length
                    }{" "}
                    alerts
                  </span>
                </div>
              )}

            {alertsLoading ? (
              <div className="empty-state">
                <div className="empty-icon">
                  ◌
                </div>

                <h4>
                  Loading security alerts
                </h4>

                <p>
                  SiteAegis is retrieving
                  the latest alerts.
                </p>
              </div>
            ) : alerts.length ===
              0 ? (
              <div className="empty-state">
                <div className="empty-icon">
                  ✓
                </div>

                <h4>
                  No security alerts
                </h4>

                <p>
                  No alerts have been
                  generated by the
                  monitoring system yet.
                </p>
              </div>
            ) : filteredAlerts.length ===
              0 ? (
              <div className="empty-state">
                <div className="empty-icon">
                  ✓
                </div>

                <h4>
                  No{" "}
                  {alertFilterLabel(
                    alertFilter,
                  ).toLowerCase()}{" "}
                  alerts
                </h4>

                <p>
                  There are no alerts
                  matching the selected
                  filter.
                </p>
              </div>
            ) : (
              <div className="alerts-list">
                {filteredAlerts.map(
                  (
                    alert,
                    index,
                  ) => (
                    <div
                      className={`alert-item ${
                        alert.is_read
                          ? "read"
                          : "unread"
                      }`}
                      key={
                        alert.alert_id
                      }
                    >
                      {!alert.is_read && (
                        <div className="alert-unread-line" />
                      )}

                      <div
                        className={`alert-severity ${alertSeverityClass(
                          alert.severity,
                        )}`}
                      >
                        {alert.severity
                          .slice(
                            0,
                            1,
                          )
                          .toUpperCase()}
                      </div>

                      <div className="alert-body">
                        <div className="alert-title-row">
                          <strong>
                            {
                              alert.title
                            }
                          </strong>

                          {!alert.is_read && (
                            <span className="unread-dot" />
                          )}

                          {index ===
                            0 && (
                            <span className="latest-badge">
                              LATEST
                            </span>
                          )}
                        </div>

                        <p>
                          {
                            alert.message
                          }
                        </p>

                        <div className="alert-meta">
                          <span>
                            {
                              alert.alert_type
                            }
                          </span>

                          <span>
                            SITE #
                            {
                              alert.site_id
                            }
                          </span>

                          <span>
                            {formatDateTime(
                              alert.created_at,
                            )}
                          </span>
                        </div>
                      </div>

                      {!alert.is_read && (
                        <button
                          type="button"
                          className="alert-read-button"
                          onClick={() =>
                            markAlertAsRead(
                              alert.alert_id,
                            )
                          }
                          disabled={
                            alertActionId ===
                            alert.alert_id
                          }
                        >
                          {alertActionId ===
                          alert.alert_id
                            ? "..."
                            : "MARK READ"}
                        </button>
                      )}
                    </div>
                  ),
                )}
              </div>
            )}
          </>
        )}
      </section>

      <section className="services-strip">
        <div className="service-item">
          <span
            className={`service-dot ${
              connected
                ? "online"
                : "offline"
            }`}
          />

          <div>
            <strong>
              WEBSOCKET
            </strong>

            <small>
              {connected
                ? "Live event stream active"
                : "Reconnecting"}
            </small>
          </div>
        </div>

        <div className="service-item">
          <span
            className={`service-dot ${
              health?.status ===
              "healthy"
                ? "online"
                : "offline"
            }`}
          />

          <div>
            <strong>
              API
            </strong>

            <small>
              {health?.status ??
                "Checking"}
            </small>
          </div>
        </div>

        <div className="service-item">
          <span
            className={`service-dot ${
              health?.services
                ?.redis ===
              "connected"
                ? "online"
                : "offline"
            }`}
          />

          <div>
            <strong>
              REDIS
            </strong>

            <small>
              {health?.services
                ?.redis ??
                "Checking"}
            </small>
          </div>
        </div>

        <div className="service-item">
          <span className="service-dot online" />

          <div>
            <strong>
              POSTGRESQL
            </strong>

            <small>
              Primary database
            </small>
          </div>
        </div>
      </section>

      <footer className="footer">
        <span>
          SITEAEGIS / SECURITY + SAFETY INTELLIGENCE
        </span>

        <span>
          {connected
            ? "WEBSOCKET · ACTIVE"
            : "WEBSOCKET · OFFLINE"}
        </span>
      </footer>
    </main>
  );
}