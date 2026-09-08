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

export default function Home() {
  const [connected, setConnected] = useState(false);

  const [sites, setSites] = useState<Site[]>([]);

  const [updates, setUpdates] = useState<
    MonitoringUpdate[]
  >([]);

  const [lastUpdate, setLastUpdate] =
    useState<MonitoringUpdate | null>(null);

  const [loadingSites, setLoadingSites] =
    useState(true);

  const [alerts, setAlerts] = useState<Alert[]>([]);

  const [alertsLoading, setAlertsLoading] =
    useState(true);

  const [unreadAlertCount, setUnreadAlertCount] =
    useState(0);

  const [alertActionId, setAlertActionId] =
    useState<string | null>(null);

  const [markingAllRead, setMarkingAllRead] =
    useState(false);

  const wsRef =
    useRef<WebSocket | null>(null);

  const reconnectTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null,
    );

  /*
  ============================================================
  LOAD REGISTERED SITES
  ============================================================
  */

  useEffect(() => {
    let active = true;

    async function loadSites() {
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

        const data =
          await response.json();

        if (
          active &&
          Array.isArray(data)
        ) {
          setSites(data);
        }
      } catch (error) {
        console.error(
          "Failed to load sites:",
          error,
        );
      } finally {
        if (active) {
          setLoadingSites(false);
        }
      }
    }

    loadSites();

    return () => {
      active = false;
    };
  }, []);

  /*
  ============================================================
  LOAD ALERTS + REAL UNREAD COUNT
  ============================================================
  */

  async function loadAlerts() {
    try {
      const [
        alertsResponse,
        countResponse,
      ] = await Promise.all([
        fetch(
          `${API_URL}/api/alerts?limit=50`,
          {
            cache: "no-store",
          },
        ),

        fetch(
          `${API_URL}/api/alerts/count`,
          {
            cache: "no-store",
          },
        ),
      ]);

      if (!alertsResponse.ok) {
        throw new Error(
          `Alerts request failed: ${alertsResponse.status}`,
        );
      }

      if (!countResponse.ok) {
        throw new Error(
          `Alert count request failed: ${countResponse.status}`,
        );
      }

      const alertsData =
        await alertsResponse.json();

      const countData =
        await countResponse.json();

      if (
        Array.isArray(alertsData)
      ) {
        setAlerts(alertsData);
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
    } catch (error) {
      console.error(
        "Failed to load alerts:",
        error,
      );
    } finally {
      setAlertsLoading(false);
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

    setAlertActionId(alertId);

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
    } catch (error) {
      console.error(
        "Failed to mark alert as read:",
        error,
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
    setMarkingAllRead(true);

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
    } catch (error) {
      console.error(
        "Failed to mark all alerts as read:",
        error,
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

    /*
    ------------------------------------------------------------
    CLEAR RECONNECT TIMER
    ------------------------------------------------------------
    */

    function clearReconnectTimer() {
      if (reconnectTimerRef.current) {
        clearTimeout(
          reconnectTimerRef.current,
        );

        reconnectTimerRef.current =
          null;
      }
    }

    /*
    ------------------------------------------------------------
    CLEAR INITIAL CONNECTION TIMER
    ------------------------------------------------------------
    */

    function clearInitialConnectionTimer() {
      if (initialConnectionTimer) {
        clearTimeout(
          initialConnectionTimer,
        );

        initialConnectionTimer = null;
      }
    }

    /*
    ------------------------------------------------------------
    MERGE REAL-TIME ALERTS
    ------------------------------------------------------------
    */

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
        const incomingIds =
          new Set(
            incomingAlerts.map(
              (alert) =>
                String(
                  alert.alert_id,
                ),
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

      /*
      ----------------------------------------------------------
      UPDATE REAL UNREAD COUNT
      ----------------------------------------------------------
      */

      setUnreadAlertCount(
        (previous) => {
          const newUnreadCount =
            incomingAlerts.filter(
              (alert) =>
                !alert.is_read,
            ).length;

          const incomingIds =
            new Set(
              incomingAlerts.map(
                (alert) =>
                  String(
                    alert.alert_id,
                  ),
              ),
            );

          const replacedUnreadCount =
            alerts.filter(
              (alert) =>
                incomingIds.has(
                  String(
                    alert.alert_id,
                  ),
                ) &&
                !alert.is_read,
            ).length;

          return Math.max(
            0,
            previous -
              replacedUnreadCount +
              newUnreadCount,
          );
        },
      );
    }

    /*
    ------------------------------------------------------------
    HANDLE MONITORING UPDATE
    ------------------------------------------------------------
    */

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

      /*
      ----------------------------------------------------------
      SAVE LATEST UPDATE
      ----------------------------------------------------------
      */

      setLastUpdate(data);

      /*
      ----------------------------------------------------------
      UPDATE ACTIVITY HISTORY
      ----------------------------------------------------------
      */

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

      /*
      ----------------------------------------------------------
      UPDATE MATCHING SITE
      ----------------------------------------------------------
      */

      setSites((previous) => {
        const updated =
          previous.map(
            (site) =>
              String(
                site.site_id,
              ) ===
              String(
                data.site.site_id,
              )
                ? {
                    ...site,
                    ...data.site,

                    last_scan_id:
                      data.scan
                        .scan_id,

                    last_status:
                      data.scan
                        .status,

                    last_risk_score:
                      data.scan
                        .risk_score,

                    last_risk_level:
                      data.scan
                        .risk_level,
                  }
                : site,
          );

        const exists =
          previous.some(
            (site) =>
              String(
                site.site_id,
              ) ===
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

      /*
      ----------------------------------------------------------
      REAL-TIME ALERTS
      ----------------------------------------------------------
      */

      if (
        Array.isArray(
          data.alerts,
        ) &&
        data.alerts.length > 0
      ) {
        mergeRealtimeAlerts(
          data.alerts,
        );

        /*
        Also refresh the authoritative
        backend count.
        */

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

    /*
    ============================================================
    SCHEDULE RECONNECT
    ============================================================
    */

    function scheduleReconnect() {
      if (!effectActive) {
        return;
      }

      if (
        reconnectTimerRef.current
      ) {
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

    /*
    ============================================================
    CONNECT WEBSOCKET
    ============================================================
    */

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

      const ws =
        new WebSocket(
          WS_URL,
        );

      wsRef.current = ws;

      /*
      ==========================================================
      ON OPEN
      ==========================================================
      */

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

      /*
      ==========================================================
      ON MESSAGE
      ==========================================================
      */

      ws.onmessage = (
        event,
      ) => {
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

          /*
          --------------------------------------------------------
          CONNECTION EVENT
          --------------------------------------------------------
          */

          if (
            data?.type ===
            "connection"
          ) {
            return;
          }

          /*
          --------------------------------------------------------
          MONITORING UPDATE
          --------------------------------------------------------
          */

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

          /*
          --------------------------------------------------------
          ACK / OTHER EVENT
          --------------------------------------------------------
          */

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

      /*
      ==========================================================
      ON ERROR
      ==========================================================
      */

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

      /*
      ==========================================================
      ON CLOSE
      ==========================================================
      */

      ws.onclose = (
        event,
      ) => {
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

    /*
    ============================================================
    INITIAL CONNECTION
    ============================================================
    */

    initialConnectionTimer =
      setTimeout(() => {
        initialConnectionTimer =
          null;

        if (effectActive) {
          connectWebSocket();
        }
      }, 100);

    /*
    ============================================================
    CLEANUP
    ============================================================
    */

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
            /*
            Ignore cleanup errors.
            */
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
    lastUpdate?.scan
      .risk_score ??
    monitoredSites.find(
      (site) =>
        site.last_risk_score !==
          null &&
        site.last_risk_score !==
          undefined,
    )?.last_risk_score ??
    null;

  const latestFindings =
    lastUpdate?.scan
      .findings_count ??
    0;

  const latestResponse =
    lastUpdate?.scan
      .response_time_ms ??
    null;

  /*
  ============================================================
  ALERT COUNTS
  ============================================================
  */

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
            update.events.length >
              0
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

        return result.slice(
          0,
          10,
        );
      },
      [updates],
    );

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
      ).toLocaleTimeString(
        [],
        {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        },
      );
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
      ).toLocaleString(
        [],
        {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        },
      );
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
            <h1>
              SiteAegis
            </h1>

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
            <span>
              Detect.
            </span>
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
                : "Waiting for backend"}
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
            {onlineSites}
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
              : unreadAlerts}
          </strong>

          <small>
            Security alerts requiring attention
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
                "WAITING"}
            </div>
          </div>

          {lastUpdate ? (
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
                  <span>
                    RISK
                  </span>

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
                The dashboard will
                populate when
                SiteAegis receives
                its first monitoring
                update through the
                WebSocket stream.
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
                Activity
              </h3>
            </div>

            <span className="event-count">
              {activities.length} EVENTS
            </span>
          </div>

          {activities.length > 0 ? (
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
                No monitoring events
                received yet.
              </p>
            </div>
          )}
        </div>
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
          </div>

          <div className="alerts-actions">
            <span className="event-count">
              {unreadAlerts} UNREAD
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
        ) : alerts.length === 0 ? (
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
        ) : (
          <div className="alerts-list">
            {alerts.map(
              (alert) => (
                <div
                  className={`alert-item ${
                    alert.is_read
                      ? "read"
                      : "unread"
                  }`}
                  key={alert.alert_id}
                >
                  <div
                    className={`alert-severity ${alertSeverityClass(
                      alert.severity,
                    )}`}
                  >
                    {alert.severity
                      .slice(0, 1)
                      .toUpperCase()}
                  </div>

                  <div className="alert-body">
                    <div className="alert-title-row">
                      <strong>
                        {alert.title}
                      </strong>

                      {!alert.is_read && (
                        <span className="unread-dot" />
                      )}
                    </div>

                    <p>
                      {alert.message}
                    </p>

                    <div className="alert-meta">
                      <span>
                        {alert.alert_type}
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