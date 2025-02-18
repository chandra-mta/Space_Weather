#!/proj/sot/ska3/flight/bin/python
import os
import sys
from datetime import datetime, timezone
import subprocess
import argparse
import traceback
import getpass
from email.mime.text import MIMEText
from subprocess import Popen, PIPE


DATA_DIR = "/data/mta4/Space_Weather/GOES/Data"
ARCHIVE_FILE = f"{DATA_DIR}/hrc_proxy.csv"
ADMIN = ["mtadude@cfa.harvard.edu"]
#
# --- Due to the latest data from SWPC being 15 minutes behind, this data will always have at minimum a 15 minute delay.
#
TIME_DIFF = 2700  #: 45 minutes in seconds


def send_mail(content, subject, admin):
    """Send warning message to the admins

    :param content: Content of the email.
    :type content: str
    :param subject: Subject line of the email.
    :type subject: str
    :param admin: List of email recipients.
    :type admin: list
    """
    content += f'This message was send to {" ".join(admin)}'
    msg = MIMEText(content)
    msg["Subject"] = subject
    msg["To"] = ",".join(admin)
    p = Popen(["/sbin/sendmail", "-t", "-oi"], stdin=PIPE)
    (out, error) = p.communicate(msg.as_bytes())


def check_cadence():
    """Reads the hrc_proxy.csv archive file to check if there is a delay in the calculation, likely due to missing data."""
    now = datetime.now(timezone.utc)
    out = subprocess.check_output(
        f"tail -n 1 {ARCHIVE_FILE}", shell=True, executable="/bin/csh"
    ).decode()
    last_time = datetime.strptime(out.split(",")[0], "%Y:%j:%H:%M")
    last_time = last_time.replace(tzinfo=timezone.utc)
    if os.path.isfile(f"{DATA_DIR}/check_archive.viol"):
        #
        # --- if we are in violation with a time discrepancy, do nothing until we are no longer in violation, then send email
        #
        if (now - last_time).total_seconds() < TIME_DIFF:
            content = f"Time discrepancy in {ARCHIVE_FILE} has ended.\n{'-' * 40}\nTail of file: {out}Current Time: {now.strftime('%Y:%j:%H:%M')}\n"
            send_mail(content, "HRC Proxy Archive Resumed", ADMIN)
            os.remove(f"{DATA_DIR}/check_archive.viol")
    #
    # --- If we have no record of a time violation, but then find one, write the viol file and send email
    #
    elif (now - last_time).total_seconds() > TIME_DIFF:
        content = f"Time discrepancy in {ARCHIVE_FILE}\n{'-' * 40}\nTail of file: {out}Current Time: {now.strftime('%Y:%j:%H:%M')}\n"
        content += "Discrepancy likely due to interrupted service from SWPC NOAA.\n"
        with open(f"{DATA_DIR}/check_archive.viol", "w") as f:
            f.write(content)
        send_mail(content, "Time Discrepancy in HRC Proxy Archive", ADMIN)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-m",
        "--mode",
        choices=["flight", "test"],
        required=True,
        help="Determine running mode.",
    )
    parser.add_argument(
        "-e",
        "--email",
        nargs="*",
        required=False,
        help="List of emails to receive notifications",
    )
    parser.add_argument(
        "-a", "--archive", help="Determine long-term record file path for HRC proxy"
    )
    args = parser.parse_args()

    if args.mode == "test":
        #
        # --- Redefine Admin for sending notification email in test mode
        #
        if args.email is not None:
            ADMIN = args.email
        else:
            ADMIN = [
                os.popen(f"getent aliases | grep {getpass.getuser()}")
                .read()
                .split(":")[1]
                .strip()
            ]

        DATA_DIR = f"{os.getcwd()}/test/_outTest"
        os.makedirs(DATA_DIR, exist_ok=True)
        if args.archive:
            ARCHIVE_FILE = args.archive
        else:
            ARCHIVE_FILE = f"{DATA_DIR}/hrc_proxy.csv"

        if not os.path.isfile(ARCHIVE_FILE):
            os.system(
                f"cp /data/mta4/Space_Weather/GOES/Data/hrc_proxy.csv {ARCHIVE_FILE}"
            )

        try:
            check_cadence()
        except:  # noqa: E722
            traceback.print_exc()

    elif args.mode == "flight":
        #
        # --- Create a lock file and exit strategy in case of race conditions
        #
        name = os.path.basename(__file__).split(".")[0]
        user = getpass.getuser()
        if os.path.isfile(f"/tmp/{user}/{name}.lock"):
            notification = f"Lock file exists as /tmp/{user}/{name}.lock. Process already running/errored out. Check calling scripts/cronjob/cronlog."
            send_mail(notification, f"Stalled Script: {name}", ADMIN)
            sys.exit(notification)
        else:
            os.system(f"mkdir -p /tmp/{user}; touch /tmp/{user}/{name}.lock")

        try:
            check_cadence()
        except:  # noqa: E722
            traceback.print_exc()
        #
        # --- Remove lock file once process is completed
        #
        os.system(f"rm /tmp/{user}/{name}.lock")
