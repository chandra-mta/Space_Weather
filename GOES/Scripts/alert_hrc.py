#!/proj/sot/ska3/flight/bin/python
"""
**alert_hrc.py**: Send alerts to the HRC team in case the HRC proxy violates

:Author: W. Aaron (william.aaron@cfa.harvard.edu)
:Last Updated: Feb 20, 2025

"""
import os
import sys
import argparse
import getpass
import traceback
from datetime import datetime, timezone
import json
import csv
from astropy.io import ascii

#
# --- Define Directory Pathing
#
GOES_DIR = "/data/mta4/Space_Weather/GOES/Data"
GOES_DATA_FILE = f"{GOES_DIR}/Gp_pchan_5m.txt"
HRC_PROXY_DATA_FILE = f"{GOES_DIR}/hrc_proxy.csv"
VIOL_RECORD_FILE = f"{GOES_DIR}/hrc_proxy_viol.json"
NAMES = (
    "time",
    "p1",
    "p2a",
    "p2b",
    "p3",
    "p4",
    "p5",
    "p6",
    "p7",
    "p8a",
    "p8b",
    "p8c",
    "p9",
    "p10",
    "hrc_proxy",
    "hrc_proxy_legacy",
)
CSV_HEADER = ["time", "hrc_proxy", "hrc_proxy_legacy"]
HRC_THRESHOLD = {"Warning": 3.2e4}  #: Based on HRC Proxy differential values
PROXIES = ["hrc_proxy", "hrc_proxy_legacy"]
HRC_ADMIN = [
    "rkraft@cfa.harvard.edu",
    "6172756031@vtext.com",
    "dpatnaude@cfa.harvard.edu",
    "6173726105@vtext.com",
    "gtremblay@cfa.harvard.edu",
    "2075044862@vtext.com",
    "gerrit.schellenberg@cfa.harvard.edu",
    "6178750424@vtext.com",
    "mtadude@cfa.harvard.edu",
]  #: Alert Email Addresses
ADMIN = ["mtadude@cfa.harvard.edu"]


def alert_hrc():
    """Read the GOES differential proton data for the calculated hrc proxy value

    :File Out: <goes_dir>/hrc_proxy.csv

    """
    dat = ascii.read(
        GOES_DATA_FILE, data_start=5, delimiter="\t", guess=False, names=NAMES
    )
    time, hrc_proxy, hrc_proxy_legacy = dat[-1]["time", "hrc_proxy", "hrc_proxy_legacy"]
    recent_data = {
        "time": str(time),
        "hrc_proxy": int(hrc_proxy),
        "hrc_proxy_legacy": int(hrc_proxy_legacy),
    }  #: Cast astropy table data into json serializable types

    #
    # --- Check current status of HRC proxy violations.
    # --- If one has been found very recently, do not email about the violation again.
    #
    with open(VIOL_RECORD_FILE) as f:
        curr_viol = json.load(f)

    content = ""
    for kind in (
        HRC_THRESHOLD.keys()
    ):  #: Iterate over kinds of threshold and versions each proxy
        for proxy in PROXIES:
            if recent_data[proxy] > HRC_THRESHOLD[kind]:
                if viol_time_check(
                    curr_viol, kind, proxy
                ):  #: check if there was a similar kind of violation withing the last 24 hours
                    content += f"{kind}: {proxy}\n"
                    content += f"Limit: {HRC_THRESHOLD[kind]:.3e} counts/sec.\n"
                    content += f"Time: {time}\n"
                    content += f"{'-' * 20}\n"
                    for p in PROXIES:
                        content += f"{p}: {recent_data[p]:.5e}\n"
                    curr_viol[f"{kind}_{proxy}"] = recent_data

    if content != "" and len(HRC_ADMIN) > 0:
        send_mail(content, "HRC Proxy Violation", HRC_ADMIN)
    with open(VIOL_RECORD_FILE, "w") as f:
        json.dump(curr_viol, f, indent=4)

    add_to_archive(recent_data, HRC_PROXY_DATA_FILE)


def send_mail(content, subject, admin):
    """
    send out a notification email to admin
    """
    cmd = f'echo "{content}" | mailx -s "{subject}" {" ".join(admin)}'
    os.system(cmd)


def viol_time_check(curr_viol, kind, proxy):
    """
    Prevents spamming violation emails if the data is in violation,
    opting to send out a email if the specific violation was last warned more than 24 hours ago.
    """
    time_string = curr_viol[f"{kind}_{proxy}"]["time"]
    last = datetime.strptime(time_string, "%Y:%j:%H:%M")
    now = datetime.now(timezone.utc)
    last = last.replace(tzinfo=timezone.utc)
    return (now - last).days > 1


def add_to_archive(recent_data, outfile):
    with open(outfile, "a") as f:
        writer = csv.DictWriter(
            f, dialect="unix", fieldnames=CSV_HEADER, quoting=csv.QUOTE_NONE
        )
        writer.writerow(recent_data)


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
    parser.add_argument("-g", "--goes", help="Determine GOES data file path")
    parser.add_argument(
        "-a", "--archive_hrc", help="Determine long term record file path for HRC proxy"
    )
    parser.add_argument(
        "-j", "--json", help="Pass in record for current state of HRC proxy violations."
    )
    args = parser.parse_args()

    if args.mode == "test":
        #
        # --- Redefine Admin for sending notification email in test mode
        #
        if args.email is not None:
            HRC_ADMIN = args.email
            ADMIN = args.email
        else:
            HRC_ADMIN = [
                os.popen(f"getent aliases | grep {getpass.getuser()}")
                .read()
                .split(":")[1]
                .strip()
            ]
            ADMIN = HRC_ADMIN

        #
        # --- Redefine pathing for GOES and HRC PROXY data files
        #
        OUT_DIR = f"{os.getcwd()}/test/_outTest"
        os.makedirs(OUT_DIR, exist_ok=True)
        if args.goes:
            GOES_DATA_FILE = args.goes
        else:
            GOES_DATA_FILE = f"{OUT_DIR}/Gp_pchan_5m.txt"

        if args.json:
            VIOL_RECORD_FILE = args.json
        else:
            temp_dict = {
                "time": "2020:077:17:10",
                "hrc_proxy": 0,
                "hrc_proxy_legacy": 0,
            }
            import copy

            check_viol = {
                "Warning_hrc_proxy": copy.copy(temp_dict),
                "Warning_hrc_proxy_legacy": copy.copy(temp_dict),
            }

            VIOL_RECORD_FILE = f"{OUT_DIR}/hrc_proxy_viol.json"
            with open(VIOL_RECORD_FILE, "w") as f:
                json.dump(check_viol, f, indent=4)

        if args.archive_hrc:
            HRC_PROXY_DATA_FILE = args.archive_hrc
        else:
            HRC_PROXY_DATA_FILE = f"{OUT_DIR}/hrc_proxy.csv"
            with open(HRC_PROXY_DATA_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, dialect="unix", fieldnames=CSV_HEADER, quoting=csv.QUOTE_NONE
                )
                writer.writeheader()

        try:
            alert_hrc()
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
            alert_hrc()
        except:  # noqa: E722
            traceback.print_exc()
        #
        # --- Remove lock file once process is completed
        #
        os.system(f"rm /tmp/{user}/{name}.lock")
