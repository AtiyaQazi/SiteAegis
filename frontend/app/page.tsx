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
};

type AlertFilter =
  | "all"
  | "unread"
  | "findings"
  | "status"
  | "security";

export default function Home() {
  const [connected, setConnected] = useState(false);

  const [sites, setSites] = useState<Site[]>([]);
  const [updates, setUpdates] = useState<MonitoringUpdate[]>([]);
  const [lastUpdate, setLastUpdate] =
    useState<MonitoringUpdate | null>(null);

  const [loadingSites, setLoadingSites] =
    useState(true);

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

  const [alertActionId, setAlertActionId] =
    useState<string | null>(null);

  const [markingAllRead, setMarkingAllRead] =
    useState(false);

  const [alertActionError, setAlertActionError] =
    useState<string | null>(null);

  const [alertFilter, setAlertFilter] =
    useState<AlertFilter>("all");

  const wsRef = useRef<WebSocket | null>(null);

  const reconnectTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null,
    );

  /*
  ============================================================
  LOAD REGISTERED SITES
  ============================================================
  */

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
      const response = await fetch(
        `${API_URL}/api/sites`,
        {
          cache: "no-store",
        },
      );

      if (!response.ok) {
        throw new Error(
          `Sites request failed: ${response.status}`,
        );
      }

      const data = await response.json();

      if (!Array.isArray(data)) {
        throw new Error(
          "Invalid sites response received from backend.",
        );
      }

      setSites(data);
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
    let active = true;

    async function initialLoad() {
      if (!active) {
        return;
      }

      await loadSites();
    }

    initialLoad();

    return () => {
      active = false;
    };
  }, []);

  /*
  ============================================================
  LOAD ALERTS
  ============================================================
  */

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
      const alertsResponse = await fetch(
        `${API_URL}/api/alerts?limit=50`,
        {
          cache: "no-store",
        },
      );

      if (!alertsResponse.ok) {
        throw new Error(
          `Alerts request failed: ${alertsResponse.status}`,
        );
      }

      const alertsData =
        await alertsResponse.json();

      if (!Array.isArray(alertsData)) {
        throw new Error(
          "Invalid alerts response received from backend.",
        );
      }

      const countResponse = await fetch(
        `${API_URL}/api/alerts/count`,
        {
          cache: "no-store",
        },
      );

      if (!countResponse.ok) {
        throw new Error(
          `Alert count request failed: ${countResponse.status}`,
        );
      }

      const countData =
        await countResponse.json();

      setAlerts(alertsData);

      if (
        countData &&
        typeof countData.unread ===
          "number"
      ) {
        setUnreadAlertCount(
          countData.unread,
        );
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

  /*
  ============================================================
  MARK SINGLE ALERT AS READ
  ============================================================
  */

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
      const response = await fetch(
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
          Math.max(0, previous - 1),
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

  /*
  ============================================================
  MARK ALL ALERTS AS READ
  ============================================================
  */

  async function markAllAlertsAsRead() {
    if (markingAllRead) {
      return;
    }

    setMarkingAllRead(true);
    setAlertActionError(null);

    try {
      const response = await fetch(
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

  /*
  ============================================================
  WEBSOCKET LIVE MONITORING
  ============================================================
  */

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

        reconnectTimerRef.current = null;
      }
    }

    function clearInitialConnectionTimer() {
      if (initialConnectionTimer) {
        clearTimeout(
          initialConnectionTimer,
        );

        initialConnectionTimer = null;
      }
    }

    function mergeRealtimeAlerts(
      incomingAlerts: Alert[],
    ) {
      if (
        !Array.isArray(incomingAlerts) ||
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
                String(alert.alert_id),
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
        console.warn(
          "Invalid monitoring update:",
          data,
        );

        return;
      }

      console.log(
        "LIVE MONITORING UPDATE:",
        data,
      );

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
              String(data.site.site_id)
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
        Array.isArray(data.alerts) &&
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
              typeof countData.unread ===
                "number"
            ) {
              setUnreadAlertCount(
                countData.unread,
              );
            }
          })
          .catch((error) => {
            console.error(
              "Failed to refresh alert count:",
              error,
            );
          });
      } else if (
        data.summary &&
        data.summary.alerts_count > 0
      ) {
        loadAlerts();
      }
    }

    function scheduleReconnect() {
      if (!effectActive) {
        return;
      }

      if (reconnectTimerRef.current) {
        return;
      }

      console.log(
        "SiteAegis WebSocket reconnect scheduled...",
      );

      reconnectTimerRef.current =
        setTimeout(() => {
          reconnectTimerRef.current =
            null;

          if (!effectActive) {
            return;
          }

          connectWebSocket();
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
        console.log(
          "WebSocket already connected or connecting.",
        );

        return;
      }

      clearReconnectTimer();

      console.log(
        "Connecting to SiteAegis WebSocket...",
      );

      const ws = new WebSocket(
        WS_URL,
      );

      wsRef.current = ws;

      ws.onopen = () => {
        if (
          !effectActive ||
          wsRef.current !== ws
        ) {
          return;
        }

        console.log(
          "SiteAegis WebSocket Connected",
        );

        setConnected(true);

        try {
          ws.send(
            JSON.stringify({
              type: "client_connected",
              source:
                "siteaegis_dashboard",
            }),
          );
        } catch (error) {
          console.warn(
            "WebSocket handshake message failed:",
            error,
          );
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

          console.log(
            "LIVE SITEAEGIS EVENT:",
            data,
          );

          if (
            data?.type ===
            "connection"
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

          console.log(
            "SiteAegis event received:",
            data,
          );
        } catch (error) {
          console.error(
            "Invalid WebSocket message:",
            error,
            event.data,
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

        console.warn(
          "SiteAegis WebSocket connection error.",
        );
      };

      ws.onclose = (event) => {
        if (
          wsRef.current === ws
        ) {
          wsRef.current = null;
        }

        if (!effectActive) {
          return;
        }

        setConnected(false);

        console.log(
          `SiteAegis WebSocket Disconnected (code ${event.code})`,
        );

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
        if (
          ws.readyState ===
          WebSocket.OPEN
        ) {
          try {
            ws.close(
              1000,
              "Component cleanup",
            );
          } catch {
            // Ignore cleanup errors.
          }
        }
      }
    };
  }, []);

  /*
  ============================================================
  DERIVED DASHBOARD DATA
  ============================================================
  */

  const monitoredSites =
    sites.filter(
      (site) =>
        site.monitoring_enabled !==
        false,
    );

  const onlineSites =
    monitoredSites.filter(
      (site) =>
        site.last_status ===
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

  /*
  ============================================================
  ACTIVITY STREAM
  ============================================================
  */

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
            });
          }
        }

        return result.slice(0, 10);
      },
      [updates],
    );

  /*
  ============================================================
  FILTERED ALERTS
  ============================================================
  */

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
                type.includes("SECURITY")
              );
            },
          );

        case "all":
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
              type.includes("SECURITY")
            );
          },
        ).length,
      };
    }, [alerts]);

  /*
  ============================================================
  HELPERS
  ============================================================
  */

  function formatTime(
    timestamp: string,
  ) {
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
    timestamp: string,
  ) {
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

  /*
  ============================================================
  UI
  ============================================================
  */

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
            REAL-TIME WEB SECURITY
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
            websites, tracks
            security changes,
            evaluates risk, and
            delivers live
            intelligence through
            the monitoring stream.
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
            {sitesError
              ? "Backend connection unavailable"
              : "Registered monitoring targets"}
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
            Latest monitoring score
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
            {alertsError
              ? "Alert service unavailable"
              : "Security alerts requiring attention"}
          </small>
        </div>
      </section>

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
                The backend may be
                offline or temporarily
                unavailable.
              </p>

              <button
                type="button"
                onClick={() =>
                  loadSites(true)
                }
                disabled={
                  retryingSites
                }
                style={{
                  marginTop: "16px",
                  border:
                    "1px solid rgba(255,255,255,0.16)",
                  background:
                    "rgba(255,255,255,0.06)",
                  color: "#fff",
                  borderRadius:
                    "999px",
                  padding:
                    "9px 16px",
                  fontSize: "10px",
                  fontWeight: 700,
                  letterSpacing:
                    "0.08em",
                  cursor:
                    retryingSites
                      ? "default"
                      : "pointer",
                  opacity:
                    retryingSites
                      ? 0.55
                      : 1,
                }}
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
                SiteAegis will populate
                this panel when the
                monitoring stream sends
                its next scan.
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

              <h3>Activity</h3>
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
                      <span />
                    </div>

                    <div className="activity-body">
                      <strong>
                        {
                          activity.title
                        }
                      </strong>

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

      {/* =====================================================
          ALERT CENTER
          ===================================================== */}

      <section className="panel alerts-panel">
        <div className="panel-header">
          <div>
            <span className="eyebrow">
              SECURITY ALERTS
            </span>

            <h3>Alert Center</h3>

            <small
              style={{
                display: "block",
                marginTop: "6px",
                opacity: 0.55,
              }}
            >
              {alerts.length} total alerts ·{" "}
              {unreadAlerts} requiring attention
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
          <div
            style={{
              marginBottom: "16px",
              padding: "11px 14px",
              border:
                "1px solid rgba(255,255,255,0.10)",
              borderRadius: "10px",
              background:
                "rgba(255,255,255,0.035)",
              fontSize: "11px",
              lineHeight: 1.5,
              opacity: 0.8,
            }}
          >
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
              retrieve security alerts
              from the backend. Existing
              dashboard monitoring can
              continue independently.
            </p>

            <button
              type="button"
              onClick={() =>
                loadAlerts(true)
              }
              disabled={
                retryingAlerts
              }
              style={{
                marginTop: "16px",
                border:
                  "1px solid rgba(255,255,255,0.16)",
                background:
                  "rgba(255,255,255,0.06)",
                color: "#fff",
                borderRadius:
                  "999px",
                padding:
                  "9px 16px",
                fontSize: "10px",
                fontWeight: 700,
                letterSpacing:
                  "0.08em",
                cursor:
                  retryingAlerts
                    ? "default"
                    : "pointer",
                opacity:
                  retryingAlerts
                    ? 0.55
                    : 1,
              }}
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
                <div
                  style={{
                    display: "flex",
                    alignItems:
                      "center",
                    justifyContent:
                      "space-between",
                    gap: "12px",
                    flexWrap:
                      "wrap",
                    marginBottom:
                      "20px",
                    paddingBottom:
                      "16px",
                    borderBottom:
                      "1px solid rgba(255,255,255,0.07)",
                  }}
                >
                  <div
                    style={{
                      display:
                        "flex",
                      gap: "8px",
                      flexWrap:
                        "wrap",
                    }}
                  >
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
                            style={{
                              border:
                                active
                                  ? "1px solid rgba(255,255,255,0.28)"
                                  : "1px solid rgba(255,255,255,0.09)",
                              background:
                                active
                                  ? "rgba(255,255,255,0.10)"
                                  : "rgba(255,255,255,0.025)",
                              color:
                                active
                                  ? "#ffffff"
                                  : "rgba(255,255,255,0.55)",
                              borderRadius:
                                "999px",
                              padding:
                                "7px 12px",
                              fontSize:
                                "10px",
                              fontWeight:
                                700,
                              letterSpacing:
                                "0.08em",
                              cursor:
                                "pointer",
                              transition:
                                "all 0.2s ease",
                            }}
                          >
                            {alertFilterLabel(
                              filter,
                            )}{" "}
                            <span
                              style={{
                                opacity:
                                  0.55,
                              }}
                            >
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

                  <span
                    style={{
                      fontSize:
                        "10px",
                      letterSpacing:
                        "0.08em",
                      opacity:
                        0.45,
                      textTransform:
                        "uppercase",
                    }}
                  >
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
                  SiteAegis is
                  retrieving the
                  latest alerts.
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
                  No alerts have
                  been generated
                  by the monitoring
                  system yet.
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
                  There are no
                  alerts matching
                  the selected
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
                      style={{
                        position:
                          "relative",
                        opacity:
                          alert.is_read
                            ? 0.62
                            : 1,
                        transition:
                          "opacity 0.2s ease, transform 0.2s ease",
                      }}
                    >
                      {!alert.is_read && (
                        <div
                          style={{
                            position:
                              "absolute",
                            left: 0,
                            top: "14px",
                            bottom:
                              "14px",
                            width:
                              "2px",
                            borderRadius:
                              "4px",
                            background:
                              "currentColor",
                            opacity:
                              0.8,
                          }}
                        />
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
                            <span
                              style={{
                                marginLeft:
                                  "6px",
                                fontSize:
                                  "9px",
                                fontWeight:
                                  700,
                                letterSpacing:
                                  "0.08em",
                                padding:
                                  "3px 7px",
                                borderRadius:
                                  "999px",
                                background:
                                  "rgba(255,255,255,0.07)",
                                border:
                                  "1px solid rgba(255,255,255,0.10)",
                                opacity:
                                  0.7,
                              }}
                            >
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

      <footer className="footer">
        <span>
          SITEAEGIS / SECURITY MONITORING
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