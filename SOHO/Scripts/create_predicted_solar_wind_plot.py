#!/proj/sot/ska3/flight/bin/python

#################################################################################
#                                                                               #
#   create_predicted_solar_wind_plot.py: create predicted solar wind            #
#                                        speed and density plot                 #
#                                                                               #
#           author: t. isobe (tisobe@cfa.harvard.edu)                           #
#                                                                               #
#           last update: Mar 16, 2021                                           #
#                                                                               #
#################################################################################

import os
import requests
import zipfile
import re
import time
import urllib.request
import json
import numpy as np
from Chandra.Time import DateTime
from astropy.table import Table
import astropy.units as u

import matplotlib as mpl
if __name__ == '__main__':
    mpl.use('Agg')
from pylab import *
import matplotlib.pyplot as plt
import matplotlib.font_manager as font_manager

# Reading directory list
path = '/data/mta4/Space_Weather/house_keeping/dir_list'

with open(path, 'r') as f:
    data = [line.strip() for line in f.readlines()]

for ent in data:
    atemp = re.split(':', ent)
    var  = atemp[1].strip()
    line = atemp[0].strip()
    exec("%s = %s" %(var, line))

# For writing out files in test directory
if (os.getenv('TEST') == 'TEST'):
    os.system('mkdir -p TestOut')
    test_out = os.getcwd() + '/TestOut'

# Temp writing file name
import random
rtail  = int(time.time() * random.random())
zspace = '/tmp/zspace' + str(rtail)

# Current time
THIS_YEAR = DateTime().year
YEAR_START_SECS = DateTime(f'{THIS_YEAR}:001:00:00:00').secs

# Data sources
SWEPAM = 'https://services.swpc.noaa.gov/json/ace/swepam/ace_swepam_1h.json'
MTOF = f"https://l1.umd.edu/data/{THIS_YEAR}_CELIAS_Proton_Monitor_5min.zip"

#-------------------------------------------------------------------------
#-- create_predicted_solar_wind_plot: create predicted soloar wind speed and density plot
#-------------------------------------------------------------------------

def create_predicted_solar_wind_plot():
    """
    create predicted soloar wind speed and density plot
    input:  none but read from:
            ftp://ftp.swpc.noaa.gov/pub/lists/ace2
            http://umtof.umd.edu/pm/crn/archive/
            <ephem_dir>/Data/PE.EPH.gsme_spherical
    ouptut: <orbit_dir>/Plots/solwind.png
    """
#
#-- ace swepam data
#
    [stime_list, sdensity, sspeed] = download_swepam()
#
#--- soho mtof data
#
    [mtime_list, mdensity, mspped] = download_mtof()
#
#--- orbital information
#
    #[gtime_list, alt_list, lon_list, lat_lst] = read_gsme_data()
    gsme_data = read_gsme_data()
#
#--- create prediction
#
    [dtime, aspd0, mspd0, aspdu0, mspdu0, aden0, mden0, adenu0, mdenu0,\
            aspd1, mspd1, aspdu1, mspdu1, aden1, mden1, adenu1, mdenu1,\
            adens, aspds, mdens, mspds]\
        = create_prediction(sdensity, sspeed, mdensity, mspped)
#
#--- plot the data
#
    create_plot(gsme_data['time'], gsme_data['alt'], gsme_data['lon'], gsme_data['lat'], dtime, \
                aspd0, mspd0, aspdu0, mspdu0, aden0, mden0, adenu0, mdenu0,\
                aspd1, mspd1, aspdu1, mspdu1, aden1, mden1, adenu1, mdenu1,\
                adens, aspds, mdens, mspds)

#-------------------------------------------------------------------------
#-- download_swepam: download ace swepam data from ftp site            ---
#-------------------------------------------------------------------------

def download_swepam():
    """
    input: none but read from:
            https://services.swpc.noaa.gov/json/ace/swepam/ace_swepam_1h.json
    output: density --- dictionary of particle density; key chandra time in hr unit
            speed   --- dictionary of solar wind speed; key chandra time in hr unit
    """
#
#--- read soloar wind data from json site
#
    with urllib.request.urlopen(SWEPAM) as url:
        data = json.loads(url.read().decode())

    time_list = []
    density   = {}
    speed     = {}

    for ent in data:
#
#--- drop bad data
#
        if ent['dsflag'] not in [0, 1]:
            continue
#
#--- time format is <yyyy><ddd><hh>
#
        ltime = time.strftime('%Y:%j:%H:00:00', time.strptime(ent['time_tag'], '%Y-%m-%dT%H:%M:%S'))
        ltime = int(DateTime(ltime).secs / 3600.)

        try:
            dval = float(ent['dens'])
            sval = float(ent['speed'])
        except:
            continue

        time_list.append(ltime)
        density[ltime] = dval
        speed[ltime]   = sval

    time_list = list(set(time_list))
    time_list = sorted(time_list)

    return [time_list,  density, speed]


def download_mtof():
    """    
    download soho mtof data from html site
    input: none but read from:
            http://umtof.umd.edu/pm/crn/archive/
    output: time_list   --- a list of time in chandra time in hr unit
            density     --- dictionary of particle density; key chandra time in hr unit
            speed       --- dictionary of solar wind speed; key chandra time in hr unit
    """

    r = requests.get(MTOF, allow_redirects=True)
    open('mtof.zip', 'wb').write(r.content)

    with zipfile.ZipFile('mtof.zip', 'r') as f:
        f.extractall('mtof')
    os.remove("mtof.zip")

    with open("mtof/2023_CELIAS_Proton_Monitor_5min.txt", 'r') as f:
        lines = f.readlines()

    # keep only list items that start with a digit
    ok = [line[0].isdigit() for line in lines]
    data = np.array(lines)[ok]

    t = Table(names=('yy', 'mon', 'dd', 'doy', 'speed', 'np', 'vth', 'ns', 'vhe',
                     'gse_x', 'gse_y', 'gse_z', 'range', 'hglat', 'hglong', 'crne'),
              dtype=(float, str, float, str, float, float, float, float, float,
                     float, float, float, float, float, float, float))

    for d in data[-31680:]: # 110 days of data with 5 min bins
        d.strip()
        row_items = d.split()
        t.add_row(row_items)

    time = [f"{str(int(2000 + x['yy']))}:{x['doy']}" for x in t]
    time = [DateTime(tt).secs / 3600 for tt in time] # in hours

    # Only one entry for each int(time)
    t['time_int'] = [int(x) for x in time]
    t['time_int'].unit = u.hr
    t_by_time_int = t.group_by('time_int')

    # Remove mon and doy columns, type str, before aggregation
    t_by_time_int.remove_columns(['mon', 'doy'])
    t_median = t_by_time_int.groups.aggregate(np.median)

    # Format required by TI's code: a dictionary with a key being Chandra.Time in hours
    density = {}
    for dd, tt in zip(t_median['np'], t_median['time_int']):
        density[tt] = dd

    speed = {}
    for ss, tt in zip(t_median['speed'], t_median['time_int']):
        speed[tt] = ss

    return list(t_median['time_int']), density, speed


def read_gsme_data():
    """
    Read gsme data from <ephem_dir>/Data/PE.EPH.gsme_spherical
    :returns data: a numpy ndarray with fields 'time' (time in fractional day of year),
                  'alt' (altitude), 'lon' (longitude), 'lat' (latitude)
    """

    ifile = ephem_dir + 'Data/PE.EPH.gsme_spherical'
    data = np.loadtxt(ifile)

    tab = Table(data, names=('time', 'alt', 'lat', 'lon',
                             'tmp4', 'tmp5', 'tmp6', 'tmp7',
                             'tmp8', 'tmp9', 'tmp10', 'tmp11', 'tmp12'))

    tab['time'] = convert_to_doy(tab['time'])
    tab['lat'] = -1.0 * tab['lat'] + 90.0

    # Usually ephem data is a few days short of 30 day period; extend the data
    # to fill the orbital data
    data = extend_orbit_period(tab['time', 'alt', 'lat', 'lon'])

    return data


def extend_orbit_period(tinp):
    """
    Extend orbital period to fill up 30 day period
    :param tinp: an astropy table with columns 'time', 'alt', 'lon', lat'.
    :returns data: a numpy ndarray with fields 'time', 'alt', 'lon', lat',
                   and with values extended in time
    """

    # Find indecies of last two nadirs
    [p1, p2] = find_orbit_nadir_times(tinp['alt'])

    # Drop the data after the last nadir point
    data = tinp[:p2].as_array()

    # Find the data values between two periods and extend the data
    data_between_nadirs = tinp[p1:p2].as_array()

    for k in range(0, 8):
        data = np.append(data, data_between_nadirs)

    # Fix the time
    time = tinp['time'][:p2]

    dcnt = p2 - p1
    t1 = tinp['time'][p1]
    t2 = tinp['time'][p2]
    tdiff = t2 - t1
    tstep = tdiff / dcnt

    tt = np.arange(time[-1] + tstep, time[-1] + (8 * dcnt + 1) * tstep, tstep)
    time = np.append(time, tt)

    data['time'] = time

    return data


def find_orbit_nadir_times(alt):
    """
    find two indecies of the last two nadirs 
    input:  alt --- a list of altitude
    output: indecies of the last two nadir points
    """
    bot = []
    for k in range(0, len(alt)-2):
        v1 = alt[k]
        v2 = alt[k+1]
        v3 = alt[k+2]
        if (v2 <= v1) and (v2 <= v3):
            bot.append(k)

    return [bot[-2], bot[-1]]

#--------------------------------------------------------------------------
#-- create_prediction: create solar particle density and speed prediction models
#--------------------------------------------------------------------------

def create_prediction(adend, aspdd,  mdend, mspdd):
    """
    create solar particle density and speed prediction models
    input:  adend   --- a dictionary of ace particle density 
            aspdd   --- a dictionary of ace particle speed
            mdend   --- a dictionary of soho particle density
            mspdd   --- a dictionary of shoho particle speed
                    key is Chandra Time in hour unit
    output  dtime   --- a list of time in day of year  
            aspd0   --- a list of ace particle speed 0th order
            mspd0   --- a list of soho particle speed 0th order
            aspdu0  --- a list of ace particle speed uncertainty 0th order
            mspdu0  --- a list of soho particle speed uncertainty 0th order
            aden0   --- a list of ace particle density 0th order
            mden0   --- a list of soho particle density 0th order
            adenu0  --- a list of ace particle density uncertainty 0th order
            mdenu0  --- a list of soho particle density uncertainty 0th order
            aspd1   --- a list of ace particle speed 1st order
            mspd1   --- a list of soho particle speed 1st order
            aspdu1  --- a list of ace particle speed uncertainty 1st order
            mspdu1  --- a list of soho particle speed uncertainty 1st order
            aden1   --- a list of ace particle density 1st order
            mden1   --- a list of soho particle density 1st order
            adenu1  --- a list of ace particle density uncertainty 1st order
            mdenu1  --- a list of soho particle density uncertainty 1st order
            aspds
            adens
            mspds
            mdens
    the assumtion is  that the earth faces the same spot of the sun every 27 days and
    the pattern will repeat from the past. 
    """
#
#-- some initalizations
#
    aden0  = []
    aspd0  = []
    mden0  = []
    mspd0  = []
    aden1  = []
    aspd1  = []
    mden1  = []
    mspd1  = []
    adenu0 = []
    aspdu0 = []
    adenu1 = []
    aspdu1 = []
    mdenu0 = []
    mspdu0 = []
    mdenu1 = []
    mspdu1 = []
    dtime  = []
    adens0 = 0
    aspds0 = 0
    mdens0 = 0
    mspds0 = 0
    adens1 = 0
    aspds1 = 0
    mdens1 = 0
    mspds1 = 0

    nadens0 = 0
    naspds0 = 0
    nmdens0 = 0
    nmspds0 = 0
    nadens1 = 0
    naspds1 = 0
    nmdens1 = 0
    nmspds1 = 0
#
#--- convert current Chandra Time into hour unit
#
    current_chandra_time = DateTime().secs
    key0 = int(current_chandra_time / 3600.0)
#
#--- create 30 day prediction in 1hr step
#
    for k in range(0, 720):
        key   = key0 + k
        stime = 3600 * key
#
#--- time is in day of year (fractional)
#
        dtime.append(convert_to_doy(stime))
#
#--- get the values from the past and put in lists of ace/soho density/speed
#
        key1  = key - 655           #--- 27.3 days ago
        key2  = key - 1309          #--- 54.5 days ago
        key3  = key - 1964          #--- 81.8 days ago
        key4  = key - 2618          #--- 109.1 days ago

        aden  = []
        aspd  = []
        mden  = []
        mspd  = []
        for ent in [key1, key2, key3, key4]:
            if ent in adend:
                val = adend[ent]
                if abs(val) < 9900:
                    aden.append(val)

            if ent in aspdd:
                val = aspdd[ent]
                if abs(val) < 9900:
                    aspd.append(val)

            if ent in mdend:
                val = mdend[ent]
                if abs(val) < 9900:
                    mden.append(val)

            if ent in mspdd:
                val = mspdd[ent]
                if abs(val) < 9900:
                    mspd.append(val)
#
#--- 0th order prediction; most of the case, the value from 27days ago is used
#
        aden0.append(-9999) if len(aden) < 1 else aden0.append(aden[0])
        aspd0.append(-9999) if len(aspd) < 1 else aspd0.append(aspd[0])
        mden0.append(-9999) if len(mden) < 1 else mden0.append(mden[0])
        mspd0.append(-9999) if len(mspd) < 1 else mspd0.append(mspd[0])
#
#--- 1st order prediction
#
        aden1.append(-9999) if len(aden) < 2 else aden1.append(aden[0] * 2 - aden[1])
        aspd1.append(-9999) if len(aspd) < 2 else aspd1.append(aspd[0] * 2 - aspd[1])
        mden1.append(-9999) if len(mden) < 2 else mden1.append(mden[0] * 2 - mden[1])
        mspd1.append(-9999) if len(mspd) < 2 else mspd1.append(mspd[0] * 2 - mspd[1])
#
#--- uncertainty is just a difference between two different data points
#
        adenu0.append(-9999) if len(aden) < 2 else adenu0.append(aden[1] - aden[0])
        aspdu0.append(-9999) if len(aspd) < 2 else aspdu0.append(aspd[1] - aspd[0])
        mdenu0.append(-9999) if len(mden) < 2 else mdenu0.append(mden[1] - mden[0])
        mspdu0.append(-9999) if len(mspd) < 2 else mspdu0.append(mspd[1] - mspd[0])

        adenu1.append(-9999) if len(aden) < 3 else adenu1.append(aden[1] * 2 - aden[2] - aden[0])
        aspdu1.append(-9999) if len(aspd) < 3 else aspdu1.append(aspd[1] * 2 - aspd[2] - aspd[0])
        mdenu1.append(-9999) if len(mden) < 3 else mdenu1.append(mden[1] * 2 - mden[2] - mden[0])
        mspdu1.append(-9999) if len(mspd) < 3 else mspdu1.append(mspd[1] * 2 - mspd[2] - mspd[0])

        if len(aden) > 1:
            adens0  += (aden[1] - aden[0])**2 
            nadens0 += 1
        if len(aspd) > 1:
            aspds0  += (aspd[1] - aspd[0])**2 
            naspds0 += 1
        if len(mden) > 1:
            mdens0  += (mden[1] - mden[0])**2 
            nadens0 += 1
        if len(mspd) > 1:
            mspds0  += (mspd[1] - mspd[0])**2 
            nmspds0 += 1

    nadens0 -= 1
    naspds0 -= 1
    nmdens0 -= 1
    nmspds0 -= 1
    nadens1 -= 1
    naspds1 -= 1
    nmdens1 -= 1
    nmspds1 -= 1
    try:
        adens = "%.1f,%.1f" % (math.sqrt(adens0/nadens0), math.sqrt(adens1/nadens1))
    except:
        adens = '0.0, 0.0'
    try:
        aspds = "%d,%d"     % (math.sqrt(aspds0/naspds0), math.sqrt(aspds1/naspds1))
    except:
        aspds = '0, 0'
    try:
        mdens = "%.1f,%.1f" % (math.sqrt(mdens0/nmdens0), math.sqrt(mdens1/nmdens1))
    except:
        mdens = '0.0, 0,0'
    try:
        mspds = "%d,%d"     % (math.sqrt(mspds0/nmspds0), math.sqrt(mspds1/nmspds1))
    except:
        mspds = '0, 0'

    return [dtime, aspd0, mspd0, aspdu0, mspdu0, aden0, mden0, adenu0, mdenu0,\
            aspd1, mspd1, aspdu1, mspdu1, aden1, mden1, adenu1, mdenu1,\
            aspds, adens, mspds, mdens]

#--------------------------------------------------------------------------
#--------------------------------------------------------------------------
#--------------------------------------------------------------------------

def create_plot(otime, alt, lon, lat, dtime,\
                aspd0, mspd0, aspdu0, mspdu0, aden0, mden0, adenu0, mdenu0, 
                aspd1, mspd1, aspdu1, mspdu1, aden1, mden1, adenu1, mdenu1, 
                adens, aspds, mdens, mspds):
    """
    input:  otime   --- a list of time related to orbits; in day of year
            alt     --- a list of altitude
            lon     --- a list of longitude
            lat     --- a list of latitude
            dtime   --- a list of time in day of year  
            aspd0   --- a list of ace particle speed 0th order
            mspd0   --- a list of soho particle speed 0th order
            aspdu0  --- a list of ace particle speed uncertainty 0th order
            mspdu0  --- a list of soho particle speed uncertainty 0th order
            aden0   --- a list of ace particle density 0th order
            mden0   --- a list of soho particle density 0th order
            adenu0  --- a list of ace particle density uncertainty 0th order
            mdenu0  --- a list of soho particle density uncertainty 0th order
            aspd1   --- a list of ace particle speed 1st order
            mspd1   --- a list of soho particle speed 1st order
            aspdu1  --- a list of ace particle speed uncertainty 1st order
            mspdu1  --- a list of soho particle speed uncertainty 1st order
            aden1   --- a list of ace particle density 1st order
            mden1   --- a list of soho particle density 1st order
            adenu1  --- a list of ace particle density uncertainty 1st order
            mdenu1  --- a list of soho particle density uncertainty 1st order
    putput: <orbit_dir>/Plots/solwin.png
    """
    plt.close('all')
#
#---- set a few parameters
#
    mpl.rcParams['font.size'] = 8
    props = font_manager.FontProperties(size=8)
    plt.subplots_adjust(hspace=0.08)

    xmin  = min(dtime)
    xmax  = max(dtime)
    xtxt  = xmin + 0.05 * (xmax- xmin)
    xtxt1 = xmin + 0.35 * (xmax- xmin)
    xtxt2 = xmin + 0.50 * (xmax- xmin)
    xtxt3 = xmin + 0.65 * (xmax- xmin)
    xtxt4 = xmin + 0.80 * (xmax- xmin)

    ymin1 =  -220
    ymax1 =   235
    ytxt1 =   195
    ymin2 =     0
    ymax2 =  1000
    ytxt2 =   880
    ymin3 = -1000
    ymax3 =  1000
    ytxt3 =   800
    ymin4 =     0
    ymax4 =    40
    ytxt4 =    36
    ymin5 =   -40
    ymax5 =    40
    ytxt5 =    32
#
#--- orbital info
#
    ax0 = plt.subplot(511)
    ax0.set_autoscale_on(False)
    ax0.set_xbound(xmin, xmax)
    ax0.set_xlim(xmin=xmin,  xmax=xmax,  auto=False)
    ax0.set_ylim(ymin=ymin1, ymax=ymax1, auto=False)
    ax0.set_facecolor('xkcd:black')

    plt.scatter(otime, alt, color='lime',  marker='.', s=0.3)
    plt.scatter(otime, lat, color='red',   marker='.', s=0.3)
    plt.scatter(otime, lon, color='white', marker='.', s=0.3)
    plt.plot([xmin, xmax], [0, 0], color='white', ls=':', lw=1)

    ax0.set_ylabel('degree/Mm', weight='heavy')
    ax0.text(xtxt,  ytxt1, 'GSM Coordinates', color='white')
    ax0.text(xtxt2, ytxt1, 'alt',             color='lime')
    ax0.text(xtxt3, ytxt1, 'lat',             color='red')
    ax0.text(xtxt4, ytxt1, 'lon',             color='white')
#
#--- no tick labeling 
#
    line = ax0.get_xticklabels()
    for label in line:
        label.set_visible(False)
#
#--- solar wind prediction
#
    ax1 = plt.subplot(512)
    ax1.set_autoscale_on(False)
    ax1.set_xbound(xmin, xmax)
    ax1.set_xlim(xmin=xmin,  xmax=xmax,  auto=False)
    ax1.set_ylim(ymin=ymin2, ymax=ymax2, auto=False)
    ax1.set_facecolor('xkcd:black')

    plt.scatter(dtime, aspd0, color='lime',         marker='o', s=0.5)
    plt.scatter(dtime, aspd1, color='aqua',         marker='+', s=0.5)
    plt.scatter(dtime, mspd0, color='red',          marker='o', s=0.5)
    plt.scatter(dtime, mspd1, color='lightsalmon',  marker='+', s=0.5)

    ax1.set_ylabel('km/s', weight='heavy')
    ax1.text(xtxt,  ytxt2, 'Solar Wind Speed',  color='white')
    ax1.text(xtxt1, ytxt2, 'ACE (0th)',         color='lime',        size=6)
    ax1.text(xtxt2, ytxt2, 'ACE (1st)',         color='aqua',        size=6)
    ax1.text(xtxt3, ytxt2, 'SOHO (0th)',        color='red',         size=6)
    ax1.text(xtxt4, ytxt2, 'SOHO (1st)',        color='lightsalmon', size=6)
#
#--- no tick labeling 
#
    line = ax1.get_xticklabels()
    for label in line:
        label.set_visible(False)
#
#--- solar wind prediction diff
#
    ax2 = plt.subplot(513)
    ax2.set_autoscale_on(False)
    ax2.set_xbound(xmin, xmax)
    ax2.set_xlim(xmin=xmin,  xmax=xmax,  auto=False)
    ax2.set_ylim(ymin=ymin3, ymax=ymax3, auto=False)
    ax2.set_facecolor('xkcd:black')

    plt.scatter(dtime, aspdu0, color='lime',        marker='o', s=0.5)
    plt.scatter(dtime, aspdu1, color='aqua',        marker='+', s=0.5)
    plt.scatter(dtime, mspdu0, color='red',         marker='o', s=0.5)
    plt.scatter(dtime, mspdu1, color='lightsalmon', marker='+', s=0.5)

    ax2.set_ylabel('km/s', weight='heavy')
    ax2.text(xtxt,  ytxt3, 'Solar wind Speed Uncertainty (Predicted- Measured)', color='white')
    #x2.text(xtxt1, ytxt2, aspds, color='lime')
    #x2.text(xtxt2, ytxt2, mspds, color='red')
#
#--- no tick labeling 
#
    line = ax2.get_xticklabels()
    for label in line:
        label.set_visible(False)
#
#--- solar wind density prediction
#
    ax3 = plt.subplot(514)
    ax3.set_autoscale_on(False)
    ax3.set_xbound(xmin, xmax)
    ax3.set_xlim(xmin=xmin,  xmax=xmax,  auto=False)
    ax3.set_ylim(ymin=ymin4, ymax=ymax4, auto=False)
    ax3.set_facecolor('xkcd:black')

    plt.scatter(dtime, aden0, color='lime',         marker='o', s=0.5)
    plt.scatter(dtime, aden1, color='aqua',         marker='+', s=0.5)
    plt.scatter(dtime, mden0, color='red',          marker='o', s=0.5)
    plt.scatter(dtime, mden1, color='lightsalmon',  marker='+', s=0.5)

    ax3.set_ylabel('p/cc', weight='heavy')
    ax3.text(xtxt,  ytxt4, 'Solar Wind Proton Density', color='white')
    #ax3.text(xtxt1, ytxt2, aspdu, color='lime')
    #ax3.text(xtxt2, ytxt2, mspdu, color='red')
#
#--- no tick labeling 
#
    line = ax3.get_xticklabels()
    for label in line:
        label.set_visible(False)
#
#--- solar wind density prediction uncertainty
#
    ax4 = plt.subplot(515)
    ax4.set_autoscale_on(False)
    ax4.set_xbound(xmin, xmax)
    ax4.set_xlim(xmin=xmin,  xmax=xmax,  auto=False)
    ax4.set_ylim(ymin=ymin5, ymax=ymax5, auto=False)
    ax4.set_facecolor('xkcd:black')

    plt.scatter(dtime, adenu0, color='lime',        marker='o', s=0.5)
    plt.scatter(dtime, adenu1, color='aqua',        marker='+', s=0.5)
    plt.scatter(dtime, mdenu0, color='red',         marker='o', s=0.5)
    plt.scatter(dtime, mdenu1, color='lightsalmon', marker='+', s=0.5)

    ax4.set_ylabel('p/cc', weight='heavy')
    ax4.text(xtxt,  ytxt5, 'Solar Wind Proton Density Uncertainty (Predicted - Measured)', color='white')
    #ax4.text(xtxt1, ytxt5, adens, color='lime')
    #x4.text(xtxt2, ytxt5, mdens, color='red')
    ax4.set_xlabel(f'Day of Year (Year: {THIS_YEAR})', weight='heavy')
#
#--- set the size of the plotting area in inch
#
    fig = matplotlib.pyplot.gcf()
    fig.set_size_inches(5.0, 8.0)
#
#--- save the plot in png format
#
    outname = html_dir + 'Orbit/Plots/solwin.png'
    #for writing out files in test directory
    if (os.getenv('TEST') == 'TEST'):
        outname = test_out + "/" + os.path.basename(outname)
    plt.savefig(outname, format='png', dpi=300)

    plt.close('all')
#
#--- copy to SOHO directory
#
    cmd = f'cp -f {outname} {html_dir}/SOHO/Plot/solwin.png'
    os.system(cmd)


def convert_to_doy(ctime):
    """
    Convert to chandra time to fractional day of year of this year
    :param ctime: Chandra.Time.DateTime (an array, or astropy Table column)
    :returns dtime: time in fractional doy of this year
    """
    dtime = (ctime - YEAR_START_SECS) / 86400.0

    if isinstance(dtime, (int, float)):
        if dtime > 0:
            dtime = dtime + 1
    else:
        idx = dtime > 0
        dtime[idx] = dtime[idx] + 1

    return dtime


#-------------------------------------------------------------------------

if __name__ == '__main__':

    create_predicted_solar_wind_plot()
