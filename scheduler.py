import time
import logging
import schedule

from automation_worker import run_automation


# Run the automation every 30 minutes.
INTERVAL_MINUTES = 30

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            "automation.log",
            encoding="utf-8"
        )
    ]
)


def scheduled_automation():
    """Run one automation cycle without stopping the scheduler."""
    logging.info("Scheduled automation cycle started.")

    try:
        run_automation()
        logging.info("Scheduled automation cycle finished.")

    except Exception:
        logging.exception(
            "Automation cycle failed. "
            "The scheduler will continue running."
        )


def main():
    logging.info(
        "Scheduler started. Interval: %s minutes.",
        INTERVAL_MINUTES
    )

    # Run one cycle immediately when the scheduler starts.
    scheduled_automation()

    # Then repeat at the configured interval.
    schedule.every(INTERVAL_MINUTES).minutes.do(
        scheduled_automation
    )

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()