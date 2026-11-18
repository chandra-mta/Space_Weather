import os
import json
import logging
import time
from pathlib import Path
import pandas as pd
import subprocess
from datetime import timedelta


BASE_DIR = Path(__file__).resolve().parent

FLUENCE_PARQUET_FILE = BASE_DIR / "fluence_history.parquet"
STATE_FILE = BASE_DIR / "solar1-fluence-alert-state.json"
FLUENCE_ALERT_MESSAGE_FILE = BASE_DIR / "solar1-fluence-alert-message.txt"

# FLUENCE_LIMIT = 3.6e8 # for flight
FLUENCE_LIMIT = 1.1e6 # for testing, P3 at 1 for 2 hours
ALERT_COOLDOWN_HOURS = 24 # no follow-up alerts within this cooldown period
WINDOW_MINUTES = 120 # two-hour fluence

# Email configuration
ALERT_TO = "msobolewska@sao.si.edu"

logging.basicConfig(
    #level=logging.INFO,
    level=logging.WARNING,
    format="%(asctime)s UTC [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.Formatter.converter = time.gmtime


def load_latest_fluence():
    """
    Load the latest Solar-1 P3 fluence estimate and its data-quality
    statistics from the Parquet history file.
    """
    df = pd.read_parquet(FLUENCE_PARQUET_FILE)

    if df.empty:
        raise ValueError("Solar-1 fluence history is empty")

    latest = df.sort_index().iloc[-1]

    return {
        "end_time": df.index.max().isoformat(),
        "fluence": latest["fluence"],
        "valid_samples": latest["valid_samples"],
        "valid_percent": latest["valid_percent"],
        "longest_gap_minutes": latest["longest_gap_minutes"],
        "latest_valid_time": latest["latest_valid_time"]
    }


def load_alert_state():
    """
    """
    """
    Load alert status and timestamp of the last successful alert.
    """
    if not STATE_FILE.exists():
        return {
            "alerted": False,
            "last_alert_time": None
        }

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    return state


def save_alert_state(state):
    """
    Save a tmp file first, then replace the name to avoid
    partial json reads.
    """
    temp_file = STATE_FILE.with_name(STATE_FILE.name + ".tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(state, f)

    os.replace(temp_file, STATE_FILE)


def send_fluence_alert(result):
    """
    Send Solar-1 P3 fluence alert using mailx.
    """

    subject = "Solar-1 P3 Two-Hour Fluence Alert"

    message = (
        "Solar-1 STIS P3 2-hour fluence threshold exceeded.\n\n"
        f"Window ending (UTC): {result['end_time']}\n"
        f"Estimated fluence: {result['fluence']:.3e} particles/(cm2 sr MeV)\n"
        f"Threshold: {FLUENCE_LIMIT:.3e} particles/(cm2 sr MeV)\n"
        f"Valid measurements: {result['valid_samples']}/{WINDOW_MINUTES}\n"
        f"Data completeness: {result['valid_percent']:.1f}%\n"
        f"Longest gap: {result['longest_gap_minutes']} minutes\n"
        f"Latest valid measurement: {result['latest_valid_time']}\n"
    )

    # Save alert message for reference
    FLUENCE_ALERT_MESSAGE_FILE.write_text(message, encoding="utf-8")

    subprocess.run(
        ["/usr/bin/mailx", "-s", subject, ALERT_TO],
        input=message,
        text=True,
        check=True,
        timeout=30
    )

    logging.info("Solar-1 fluence alert submitted to %s", ALERT_TO)


def check_fluence_alert(result):
    """
    Send an alert on threshold crossing, suppress further alerts for
    24 hours, and require the fluence to drop below the threshold
    after the cooldown before rearming.
    """

    fluence = result["fluence"]

    if fluence is None:
        logging.warning("No valid Solar-1 P3 measurements in the two-hour window")
        return

    logging.info(
        "P3 two-hour fluence: %.3e; valid: %.1f%%; longest gap: %d min",
        fluence,
        result["valid_percent"],
        result["longest_gap_minutes"]
    )

    state = load_alert_state()
    alerted = state["alerted"]
    last_alert_time = state["last_alert_time"]

    now = pd.Timestamp.now(tz="UTC")

    # Determine whether the 24-hour suppression period has expired
    cooldown_expired = (
        last_alert_time is None
        or now - pd.Timestamp(last_alert_time)
           >= timedelta(hours=ALERT_COOLDOWN_HOURS)
    )

    exceeded = bool(fluence >= FLUENCE_LIMIT)

    if exceeded:

        # Send only when the system is armed and cooldown has expired
        if not alerted and cooldown_expired:
            send_fluence_alert(result)

            state = {
                "alerted": True,
                "last_alert_time": now.isoformat()
            }

            save_alert_state(state)

            logging.warning(
                "P3 fluence threshold exceeded: %.3e >= %.3e",
                fluence, FLUENCE_LIMIT
            )

    else:

        # Rearm only when fluence is below threshold
        # and at least 24 hours have elapsed
        if alerted and cooldown_expired:
            state["alerted"] = False
            save_alert_state(state)

            logging.info("Solar-1 fluence alert state reset")

            # Remove the saved alert message
            FLUENCE_ALERT_MESSAGE_FILE.unlink(missing_ok=True)


def main():
    """
    """
    result = load_latest_fluence()
    check_fluence_alert(result)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Solar-1 fluence alert processing failed")
        raise
