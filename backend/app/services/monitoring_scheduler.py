from datetime import datetime, timezone

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.monitoring_service import monitor_sites


scheduler = AsyncIOScheduler()


def monitoring_job():
    """Execute the SiteAegis monitoring cycle."""

    print(
        "\n============================================================"
    )
    print("[SCHEDULER] Monitoring cycle started.")
    print(
        "============================================================"
    )

    try:

        result = monitor_sites()

        print(
            f"[SCHEDULER] Monitoring cycle finished: "
            f"{result}"
        )

        return result

    except Exception as exc:

        print(
            f"[SCHEDULER ERROR] {exc}"
        )

        raise


def scheduler_listener(event):
    """Log scheduler execution status."""

    if event.exception:

        print(
            "[SCHEDULER] Monitoring job failed."
        )

    else:

        print(
            "[SCHEDULER] Monitoring job executed successfully."
        )


scheduler.add_listener(
    scheduler_listener,
    EVENT_JOB_EXECUTED | EVENT_JOB_ERROR,
)


def start_monitoring_scheduler():
    """Start SiteAegis monitoring scheduler."""

    if scheduler.running:
        print(
            "[SCHEDULER] Scheduler is already running."
        )
        return

    scheduler.add_job(
        monitoring_job,
        trigger="interval",
        minutes=1,
        id="siteaegis_monitoring",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(timezone.utc),
    )

    scheduler.start()

    print(
        "[STARTUP] SiteAegis monitoring scheduler started."
    )


def stop_monitoring_scheduler():
    """Stop SiteAegis monitoring scheduler."""

    if not scheduler.running:
        return

    scheduler.shutdown(
        wait=False
    )

    print(
        "[SHUTDOWN] SiteAegis monitoring scheduler stopped."
    )