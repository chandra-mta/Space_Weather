#!/proj/sot/ska3/flight/bin/python

"""
**add_region_info.py**: Add region info to the crm data

:Author: W. Aaron (william.aaron@cfa.harvard.edu)
:Last Updated: Mar 06, 2025

"""

import os
import sys
import argparse
import re
import math
from cxotime import CxoTime
from datetime import datetime, timezone

#
#--- Define Directory Pathing
#
KP_DATA_DIR = "/data/mta4/Space_Weather/KP/Data"
TLE_DATA_DIR = "/data/mta4/Space_Weather/TLE/Data"
XMM_DATA_DIR = "/data/mta4/Space_Weather/XMM/Data"

#
# --- append paths to private folders to a python directory
#
sys.path.append("/data/mta4/Script/Python3.12")
sys.path.append('/data/mta4/Space_Weather/EPHEM/Scripts/')
#
# --- import several functions
#
from geopack import geopack
import convert_coord as ecc

#
#--- Earth radius
#
earth    =  6378.0

#--------------------------------------------------------------------------
#-- add_region_info: add region information to crm database               -
#--------------------------------------------------------------------------

def add_region_info():
    """
    add region information to crm database
    input:  none, but read from:
            <kp_data_dir>/k_index_data
            <tle_data_dir>Data/xmm.gsme_in_Re
            <tle_data_dir>Data/cxo.gsme_in_Re
    output: <xmm_data_dir>/Data/crmreg_xmm.dat
            <xmm_data_dir>/Data/crmreg_cxo.dat
    """
#
#--- read kp data
#
    ifile = f"{KP_DATA_DIR}/k_index_data"
    with open(f"{KP_DATA_DIR}/k_index_data") as f:
        data = [line.strip() for line in f.readlines()]
    ktime = []
    kps   = []
    for ent in data:
        atemp = re.split(r'\s+', ent)
        ktime.append(float(atemp[0]))
        kps.append(float(atemp[1]))
#
#--- xmm data update
#
#--- read GSM data
#
    [xtime, utime, xgsm, ygsm, zgsm, xgse, ygse, zgse, alt] = read_gsm('xmm')
#
#--- find kp value for the each data
#
    nkps = match_kp(ktime, xtime, kps)
#
#--- write the result
#
    write_region_data(xtime, utime,  nkps, xgsm, ygsm, zgsm, alt, 'xmm')
#
#--- cxo data update
#
    [xtime, utime, xgsm, ygsm, zgsm, xgse, ygse, zgse, alt] = read_gsm('cxo')
    nkps = match_kp(ktime, xtime, kps)
    write_region_data(xtime, utime,  nkps, xgsm, ygsm, zgsm, alt, 'cxo')

#--------------------------------------------------------------------------
#-- read_gsm: read GSM data                                              --
#--------------------------------------------------------------------------

def read_gsm(satellite):
    """
    read GSM data
    input:  satellite   --- either xmm or cxo
            <tle_data_dir>/Data/<satellite>.gsme_in_Re
    output: a list of list of data:
                atime   --- time in seconds from 1998.1.1
                utime   --- time in seconds from 1970.1.1
                xgsm/ygsm/zgsm  --- GSM coords
                xgse/ygse/zgse  --- GSE coords
                alt             --- orbital altitude
    """
#
#--- read the radiation data
#
    ifile = f"{TLE_DATA_DIR}/{satellite}.gsme_in_Re"
    with open(ifile) as f:
        data = [line.strip() for line in f.readlines()]

    atime = []
    utime = []
    xgsm  = []
    ygsm  = []
    zgsm  = []
    xgse  = []
    ygse  = []
    zgse  = []
    alt   = []
    for ent in data:
        atemp = re.split(r'\s+', ent)
#
#--- make it back to kkm
#
        xgsm.append(float(atemp[1]) *1.e3)
        ygsm.append(float(atemp[2]) *1.e3)
        zgsm.append(float(atemp[3]) *1.e3)

        xgse.append(float(atemp[4]) *1.e3)
        ygse.append(float(atemp[5]) *1.e3)
        zgse.append(float(atemp[6]) *1.e3)

        year = int(float(atemp[7]))
        mon  = int(float(atemp[8]))
        day  = int(float(atemp[9]))
        hh   = int(float(atemp[10]))
        mm   = int(float(atemp[11]))
        ss   = int(float(atemp[12]))
#
#--- compute Chandra Time
#
        ctime = CxoTime(f"{year}-{mon}-{day}T{hh}:{mm}:{ss}").secs
        atime.append(ctime)
#
#---- compute UTS
#
        uts = ut_in_secs(year, mon, day, hh, mm, ss)
        utime.append(uts)
        psi = geopack.recalc(uts) #: Despite not being used, a bug in geopack.geigeo does not initialize the cgst variable correctly without running this first :(
#
#--- compute altitude
#
        xgeo, ygeo, zgeo = geopack.geogsm(float(atemp[1]), float(atemp[2]), float(atemp[3]), -1)
        x, y , z = geopack.geigeo(xgeo, ygeo, zgeo, -1)
        r = math.sqrt(x*x + y*y + z*z) * 1.e3
        alt.append(r)

    return [atime, utime, xgsm, ygsm, zgsm, xgse, ygse, zgse, alt]


#--------------------------------------------------------------------------
#-- write_region_data: write out the data                                --
#--------------------------------------------------------------------------

def write_region_data(xtime, utime,  nkps, xgsm, ygsm, zgsm, alt,  sat):
    """
    write out the data
    input:  atime   --- time in seconds from 1998.1.1
            utime   --- time in seconds from 1970.1.1
            xgsm/ygsm/zgsm  --- GSM coords
            ygse/ygse/zgse  --- GSE coords
            alt             --- orbital altitude
            sat             --- either xmm or cxo
    output: <xmm__data_dir>/crmreg_<sat>.dat
    """
    line = ''
    for k in range(0, len(xtime)):
        psi = geopack.recalc(utime[k]) #: Despite not being used, a bug in geopack.geigeo does not initialize the cgst variable correctly without running this first :(
        xtail, ytail, ztail, lid = ecc.locreg(nkps[k], xgsm[k], ygsm[k], zgsm[k])
        line = line + '%9d'   % xtime[k] + '\t' 
        line = line + '%3.3f' % alt[k]   + '\t'
        line = line + '%3.3f' % xgsm[k]  + '\t'
        line = line + '%3.3f' % ygsm[k]  + '\t'
        line = line + '%3.3f' % zgsm[k]  + '\t'
        line = line + '%4d'   % lid      + '\n'

    ofile = f"{XMM_DATA_DIR}/crmreg_{sat}.dat"
    with open(ofile, 'w') as fo:
        fo.write(line)

#--------------------------------------------------------------------------
#-- match_kp: find kp value for the given time (list)                    --
#--------------------------------------------------------------------------

def match_kp(ktime, xtime, kps):
    """
    find kp value for the given time (list)
    input:  ktime   --- a list of time of corresponding kp value list
            xtime   --- a list of time 
            kps     --- a list of kp values
    output: nkps    --- a list of kp values matched to xtime list
    """
    klen  = len(ktime)
    nkps  = []
    start = 0
    for etime in xtime:
        for m in range(start, klen):
            if m + 1 >= klen:
                nkps.append(kps[-1])
                break

            if ktime[m] < etime:
                continue
            elif etime >= ktime[m] and etime < ktime[m+1]:
                nkps.append(kps[m])
                start = m - 5
                if start < 0:
                    start = 0
                break

    return nkps

def ut_in_secs(year, mon, day, hh, mm, ss):
    """convert calendar date into universal time in sec (seconds from 1970.1.1)

    :param year: year
    :type year: str, int,float
    :param mon: month
    :type mon: str, int,float
    :param day: day
    :type day: str, int,float
    :param hh: hours
    :type hh: str, int,float
    :param mm: minutes
    :type mm: str, int,float
    :param ss: seconds
    :type ss: str, int,float
    :return: UT in seconds from 1970.1.1
    :rtype: float
    """
    year = int(float(year))
    mon = int(float(mon))
    day = int(float(day))
    hh = int(float(hh))
    mm = int(float(mm))
    ss = int(float(ss))

    uts = datetime(year,mon,day,hh,mm,ss, tzinfo=timezone.utc).timestamp()

    return uts

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mode", choices = ['flight','test'], required = True, help = "Determine running mode.")
    parser.add_argument("-p", "--path", required = False, help = "Directory path to determine output location of plot.")
    args = parser.parse_args()
#
#--- Determine if running in test mode and change pathing if so
#
    if args.mode == "test":
        if args.path:
            XMM_DATA_DIR = args.path
        else:
            XMM_DATA_DIR = f"{os.getcwd()}/test/_outTest"
        os.makedirs(XMM_DATA_DIR, exist_ok = True)
        add_region_info()
    elif args.mode == "flight":
#
#--- Create a lock file and exit strategy in case of race conditions
#
        import getpass
        name = os.path.basename(__file__).split(".")[0]
        user = getpass.getuser()
        if os.path.isfile(f"/tmp/{user}/{name}.lock"):
            sys.exit(f"Lock file exists as /tmp/{user}/{name}.lock. Process already running/errored out. Check calling scripts/cronjob/cronlog.")
        else:
            os.system(f"mkdir -p /tmp/{user}; touch /tmp/{user}/{name}.lock")

        add_region_info()
#
#--- Remove lock file once process is completed
#
        os.system(f"rm /tmp/{user}/{name}.lock")


