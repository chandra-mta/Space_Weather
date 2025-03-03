#!/proj/sot/ska3/flight/bin/python

"""
**alert_ace.py**: Run ACE alerts.

:Author: W. Aaron (william.aaron@cfa.harvard.edu)
:Last Updated: Mar 03, 2025

"""

import os
from email.mime.text import MIMEText
from subprocess import Popen, PIPE
from astropy.io import ascii
from astropy.table import Column, unique
import argparse
from cxotime import CxoTime
from datetime import datetime, timedelta
import numpy as np
import getpass
import json
import signal

#
# --- Define Directory Pathing and Globals
#
ACE_URL = "https://cxc.cfa.harvard.edu/mta/RADIATION_new/ACE/ace.html"
ACE_DATA_DIR = "/data/mta4/Space_Weather/ACE/Data"
CRM_DATA_DIR = "/data/mta4/Space_Weather/CRM3/Data"
COMM_DATA_DIR = "/data/mta4/Space_Weather/Comm_data/Data"
SNAPSHOT_DIR = "/data/mta4/www/Snapshot"
_ADMIN = "mtadude@cfa.harvard.edu"
_INPUT_ACE_COLUMNS = [
    "year",
    "month",
    "day",
    "hhmm",
    "mjd",
    "daysecs",
    "electron_status",
    "electron38-53",
    "electron175-315",
    "proton_status",
    "proton47-68",
    "proton115-195",
    "proton310-580",
    "proton795-1193",
    "proton1060-1900",
    "aniso",
]  #: For reading in ACE data file.
_P3_CHANNEL = "proton115-195"  #: Channel selection for P3 alert.
ACE_P3_LIMIT = 3.6e8  #: Fluence of 3.6e8 particles/cm2-ster-MeV within 2 hours.
_DEFAULT_VIOLATION = {
    "ace_p3": {"cxotime": 0, "val": 0}
}  #: If cannot find file of previous violations, then assume issue involving them not being sent and rebuild file. Built for multiple alert types
_TESTMAIL = False


def alert_ace():
    """
    Intake the last two hours worth of ACE data and calculate P3 fluence. If over the limit, send alert.
    """
    #
    # --- Source Data File
    #
    data_file = f"{ACE_DATA_DIR}/ace_12h_archive"
    ace_table = unique(ascii.read(data_file, names=_INPUT_ACE_COLUMNS))
    cxotime_col = Column(
        _convert_time_format(
            ace_table["year"], ace_table["month"], ace_table["day"], ace_table["hhmm"]
        ),
        name="cxotime",
    )
    ace_table.add_column(cxotime_col)
    two_hours_ago = ace_table["cxotime"][-1] - timedelta(hours=2)
    sel = np.logical_and(
        ace_table["cxotime"].data >= two_hours_ago, ace_table[_P3_CHANNEL] > 0
    )
    data_select = ace_table[sel]
    if len(data_select) > 0:
        p130f = (
            np.mean(data_select[_P3_CHANNEL].data) * 7200
        )  #: Calculates the fluence with available data.
    else:
        p130f = -1e5 #: No valid data to send alert.

    #
    # ---Determine if Alerting
    #
    if p130f > ACE_P3_LIMIT:
        #
        # --- Pull current violation information to avoid repeated alerts
        #
        if os.path.isfile(f"{ACE_DATA_DIR}/ace_alert.json"):
            with open(f"{ACE_DATA_DIR}/ace_alert.json") as f:
                curr_viol = json.load(f)
            if "ace_p3" not in curr_viol.keys():
                curr_viol["ace_p3"] = _DEFAULT_VIOLATION["ace_p3"]
        else:
            curr_viol = _DEFAULT_VIOLATION
        if (
            data_select[-1]["cxotime"].datetime
            - CxoTime(curr_viol["ace_p3"]["cxotime"]).datetime
        ).days > 1:
            #
            # --- Last alert was more than one day ago. Therefore this is a new alerting instance
            #
            curr_viol["ace_p3"] = {
                "cxotime": int(data_select[-1]["cxotime"].secs),
                "val": p130f,
            }

            text_body = (
                "A Radiation violation of P3 (130KeV) has been observed by ACE\n"
            )
            text_body += f"Observed = {p130f:.4e}\n"
            text_body += (
                "(limit = fluence of 3.6e8 particles/cm2-ster-MeV within 2 hours)\n"
            )
            text_body += f"see {ACE_URL}\n"
            if os.path.isfile(f"{SNAPSHOT_DIR}/.scs107alert"):
                recipients = "sot_yellow_alert@cfa.harvard.edu"
            else:
                recipients = "sot_ace_alert@cfa.harvard.edu"
                text_body += "The ACIS on-call person should review the data and call a telecon if necessary.\n"
            #
            # --- Include additional CRM and Comm data
            #
            #with open(f"{CRM_DATA_DIR}/CRMsummary.dat") as f:
            #    text_body += f"CRM:\n{f.read()}\n"
            #with open(f"{COMM_DATA_DIR}/dsn_summary.dat") as f:
            #    text_body += f"DSN:\n{f.read()}\n"
            text_body += f"This message sent to {recipients.split('@')[0]}"
            send_mail("ACE_p3", recipients, text_body)
            with open(f"{ACE_DATA_DIR}/ace_alert.json", "w") as f:
                json.dump(curr_viol, f, indent=4)


def send_mail(subject, recipients, text_body, cc=""):
    """Send MIMEText Email

    :param subject: Subject of email
    :type subject: str
    :param recipients: Intended recipients
    :type recipients: list or str
    :param text_body:Email contents
    :type text_body: str
    :param cc:Carbon Copy recipients, defaults to ''
    :type cc: str or list, optional
    """
    #
    # --- Construct message in MIMEText
    #
    msg = MIMEText(text_body)
    msg["Subject"] = subject
    if type(recipients).__name__ == "list":
        recipients = ",".join(recipients)
    if type(cc).__name__ == "list":
        cc = ",".join(cc)
    msg["To"] = recipients
    msg["CC"] = cc
    #
    # --- Send Email
    #
    if not _TESTMAIL:
        p = Popen(["/sbin/sendmail", "-t", "-oi"], stdin=PIPE)
        (out, error) = p.communicate(msg.as_bytes())
    else:
        print(msg)


@np.vectorize
def _convert_time_format(year, month, day, hhmm):
    """Converts separated ``numpy.ndarray`` containing date information into an array of ``CxoTime`` objects.

    :param year: Four digit year
    :type year: int
    :param month: Month
    :type month: int
    :param day: Day
    :type day: int
    :param hhmm: Integer Combining Hours and Minutes
    :type hhmm: int
    :return: ``numpy.ndarray`` of ``CxoTime`` objects.
    :rtype: ``numpy.ndarray(dtype = 'object')``

    """
    hh = hhmm // 100  #: hours in hundreds and thousands place
    mm = hhmm % 100  #: minutes in tens and ones place
    time = datetime.strptime(
        f"{year:04}:{month:02}:{day:02}:{hh:02}:{mm:02}", "%Y:%m:%d:%H:%M"
    )
    return CxoTime(time, format="datetime")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-m",
        "--mode",
        choices=["flight", "test"],
        required=True,
        help="Determine running mode.",
    )
    parser.add_argument("-p", "--path", help="Determine path to ACE Data.")
    args = parser.parse_args()

    if args.mode == "test":
        _TESTMAIL = True
        if args.path:
            ACE_DATA_DIR = args.path
        else:
            ACE_DATA_DIR = f"{os.getcwd()}/test/_outTest"
        os.makedirs(ACE_DATA_DIR, exist_ok=True)
        if not os.path.isfile(f"{ACE_DATA_DIR}/ace_12h_archive"):
            os.system(
                f"cp /data/mta4/Space_Weather/ACE/Data/ace_12h_archive {ACE_DATA_DIR}"
            )
        alert_ace()

    elif args.mode == "flight":
        #
        # --- Create a lock file and exit strategy in case of race conditions
        #
        name = os.path.basename(__file__).split(".")[0]
        user = getpass.getuser()
        if os.path.isfile(f"/tmp/{user}/{name}.lock"):
            notification = f"Lock file exists as /tmp/{user}/{name}.lock. Process already running/errored out. Check calling scripts/cronjob/cronlog."
            send_mail(notification, f"Stalled Script: {name}", _ADMIN)
            with open(f"/tmp/{user}/{name}.lock") as f:
                pid = int(f.readlines()[-1].strip())
            os.remove(f"/tmp/{user}/{name}.lock")
            os.kill(pid, signal.SIGTERM)
            os.system(
                f"mkdir -p /tmp/{user}; echo '{os.getpid()}' > /tmp/{user}/{name}.lock"
            )
        else:
            os.system(
                f"mkdir -p /tmp/{user}; echo '{os.getpid()}' > /tmp/{user}/{name}.lock"
            )
        alert_ace()
        #
        # --- Remove lock file once process is completed
        #
        os.system(f"rm /tmp/{user}/{name}.lock")
