#!/proj/sot/ska3/flight/bin/python
"""
**collect_goes_long.py**: Collect GOES data for the long term use

:Author: t. isobe (tisobe@cfa.harvard.edu)
:Last Updated: Feb 18, 2025

"""
import os
import sys
import time
from cxotime import CxoTime
import urllib.request
import json
import argparse

#
# --- Define directory pathing
#
GOES_DATA_DIR = "/data/mta4/Space_Weather/GOES/Data"
OUT_DATA_DIR = "/data/mta4/Space_Weather/GOES/Data"

PLINK = "https://services.swpc.noaa.gov/json/goes/primary/differential-protons-7-day.json"  #: json data locations proton and electron
PROTON_LIST = [
    "1020-1860 keV",
    "1900-2300 keV",
    "2310-3340 keV",
    "3400-6480 keV",
    "5840-11000 keV",
    "11640-23270 keV",
    "25900-38100 keV",
    "40300-73400 keV",
    "83700-98500 keV",
    "99900-118000 keV",
    "115000-143000 keV",
    "160000-242000 keV",
    "276000-404000 keV",
]  #: proton energy designations and output file names


def collect_goes_long():
    """Collect GOES data for the long term use

    :Web Link: https://services.swpc.noaa.gov/json/goes/primary/differential-protons-7-day.json
    :File Out: <data_dir>/goes_data_r.txt
                Time P1  P2A P2B P3  P4  P5  P6  P7  P8A P8B P8C P9  P10 HRC Proxy
    """
    #
    # --- find the last entry time
    #
    outfile = f"{GOES_DATA_DIR}/goes_data_r.txt"
    with open(outfile, "r") as f:
        data = [line.strip() for line in f.readlines()]
        data = [line for line in data if line != ""]
    cut = 0
    while cut == 0:
        atemp = data[-1].split()
        try:
            cut = CxoTime(atemp[0]).secs
            break
        except:  # noqa: E722
            data.pop(-1)
    #
    # --- extract proton data
    #
    p_data = extract_goes_data(PLINK, PROTON_LIST)
    #
    # --- time list
    #
    t_list = p_data[0][0]
    d_len = len(t_list)
    #
    # --- compute hrc proxy
    #
    hrc_val = compute_hrc(p_data)
    #
    # --- aline will save the text output of the table which is used by CRM
    #
    line = ""

    for k in range(0, d_len):
        stime = CxoTime(t_list[k]).secs
        if stime <= cut:
            #
            # ---If the time is less or equal to this cutoff point, then it's not new data.
            #
            continue
        line += f"{t_list[k]}\t\t"

        for m in range(0, 13):
            try:
                line += f"{p_data[m][1][k]:1.3e}\t"
            except:  # noqa: E722
                line += "0.0\t"

        line += f"{hrc_val[k]:5.0f}\t\n"
    #
    # ---  print out data file for ACIS Rad use
    #
    appendout = f"{OUT_DATA_DIR}/{os.path.basename(outfile)}"
    with open(appendout, "a") as fo:
        fo.write(line)


def extract_goes_data(dlink, energy_list):
    """Extract GOES satellite flux data

    :param dlink: JSON web address
    :type dlink: str
    :param energy_list: A list of energy designation
    :type energy_list: list
    :return: _description_
    :rtype: _type_
    """
    """
    
    input: dlink        --- json web address
            energy_list --- a list of energy designation
    output: <data_dir>/<out file>
    """
    try:
        with urllib.request.urlopen(dlink) as url:
            data = json.loads(url.read().decode())  #: Read json file from the web
    except:
        data = []
    #
    # --- go through all energy ranges
    #
    elen = len(energy_list)
    d_save = []
    for k in range(0, elen):
        t_list = []
        f_list = []
        energy = energy_list[k]
        last_time = time.strptime(data[0]["time_tag"], "%Y-%m-%dT%H:%M:%SZ")
        for ent in data:
            #
            # --- read time and flux of the given energy range
            #
            if ent["energy"] == energy:
                flux = float(ent["flux"]) * 1e3  # --- keV to MeV
                #
                # --- convert time into seconds from 1998.1.1
                #
                otime = ent["time_tag"]
                otime = time.strptime(otime, "%Y-%m-%dT%H:%M:%SZ")

                #
                # ---If the otime is more than five minutes after the last_time,
                # ---then that means the data set is missing an entry for this energy band and zero values should be append.
                #
                diff = time.mktime(otime) - time.mktime(last_time)
                if diff > 300:
                    for i in range(
                        300, int(diff), 300
                    ):  #: All times should be in divisions of 5 minutes/300 seconds.
                        missing_time = time.localtime(time.mktime(last_time) + i)
                        t_list.append(time.strftime("%Y:%j:%H:%M:%S", missing_time))
                        f_list.append(
                            -1e5
                        )  #: Mark missing data with the invalid data marker (-1e5)

                t_list.append(
                    time.strftime("%Y:%j:%H:%M:%S", otime)
                )  #: record time as string
                f_list.append(flux)
                last_time = otime

        d_save.append([t_list, f_list])

    return d_save


def compute_hrc(data):
    """Compute hrc proxy value.
    HRC_PROXY = 6000 x P4 + 270000 x P5 + 100000 x P6
        P4 ~ 11640-23270 keV + 25900-38100 keV
        P5 ~ 40300-73400 keV,
        P6 ~ 83700-98500 keV + 99900-118000 keV + 115000-143000 keV + 160000-242000 keV.
        and:
        c0: '1020-1860 keV',
        c1: '1900-2300 keV',
        c2: '2310-3340 keV',
        c3: '3400-6480 keV',
        c4: '5840-11000 keV',
        c5: '11640-23270 keV',
        c6: '25900-38100 keV',
        c7: '40300-73400 keV',
        c8: '83700-98500 keV',
        c9: '99900-118000 keV',
        c10: '115000-143000 keV',
        c11: '160000-242000 keV',
        c12: '276000-404000 keV'

    :param data: a list of lists of data: [[<time>, <data1>], [<time>, <data2>],...]
    :type data: list
    :return: hrc proxy list
    :rtype: list
    """
    c5 = data[5][1]
    c6 = data[6][1]
    c7 = data[7][1]

    hrc = []
    for k in range(0, len(c5)):
        try:
            val = (
                143.0 * c5[k] + 64738.0 * c6[k] + 162505.0 * c7[k] + 4127
            )  #: New proxy as of 2021:125:06:05:00
        except:  # noqa: E722
            val = 0.0

        hrc.append(val)

    return hrc


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
        "-p",
        "--path",
        required=False,
        help="Directory path to determine output location of data file.",
    )
    args = parser.parse_args()

    if args.mode == "test":
        OUT_DATA_DIR = f"{os.getcwd()}/test/_outTest"
        os.makedirs(OUT_DATA_DIR, exist_ok=True)
        if os.path.isfile(f"{OUT_DATA_DIR}/goes_data_r.txt"):
            GOES_DATA_DIR = OUT_DATA_DIR
        collect_goes_long()
    else:
        #
        # --- Create a lock file and exit strategy in case of race conditions
        #
        import getpass

        name = os.path.basename(__file__).split(".")[0]
        user = getpass.getuser()
        if os.path.isfile(f"/tmp/{user}/{name}.lock"):
            sys.exit(
                f"Lock file exists as /tmp/{user}/{name}.lock. Process already running/errored out. Check calling scripts/cronjob/cronlog."
            )
        else:
            os.system(f"mkdir -p /tmp/{user}; touch /tmp/{user}/{name}.lock")

        collect_goes_long()
        #
        # --- Remove lock file once process is completed
        #
        os.system(f"rm /tmp/{user}/{name}.lock")
