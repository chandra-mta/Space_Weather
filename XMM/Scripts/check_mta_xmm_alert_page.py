#!/proj/sot/ska3/flight/bin/python

#################################################################################################
#                                                                                               #
#   check_mta_xmm_alert_page.py: check the latest count Il count rate and xmm orbital           #
#                                altitude and send out warning if mta_XMM_alert file            #
#                                does not exist.                                                #
#                                                                                               #
#           author: t. isobe (tisobe@cfa.harvard.edu)                                           #
#                                                                                               #
#           last update: Mar 16, 2021                                                           #
#                                                                                               #
#################################################################################################

import sys
import os
import string
import re
import time
import random
import math
import Chandra.Time
import numpy
from subprocess import Popen, PIPE
#
#--- reading directory list
#
path = '/data/mta4/Space_Weather/house_keeping/dir_list'
with open(path, 'r') as f:
    data = [line.strip() for line in f.readlines()]

for ent in data:
    atemp = re.split(':', ent)
    var  = atemp[1].strip()
    line = atemp[0].strip()
    exec("%s = %s" %(var, line))
#for writing out files in test directory
if (os.getenv('TEST') == 'TEST'):
    os.system('mkdir -p TestOut')
    test_out = os.getcwd() + '/TestOut'
#
#--- temp writing file name
#
rtail  = int(time.time() * random.random())
zspace = '/tmp/zspace' + str(rtail)
ADMIN = ['mtadude@cfa.harvard.edu']
#
#-- convert factor to change time to start from 1.1.1998
#
tcorrect = (28.0 * 365.0 + 8.0) * 3600.0 * 24.0
#
#--- Earth radius and the altitude limit, L1 count rate and output file
#
earth      =  6378.0
alt_limit  = 80000.0 + earth
l1_limit   = 10
alert_file = '/pool1/mta_XMM_alert'
data_dir   = xmm_dir + 'Data/'
#
#--- current time
#
current              = time.strftime('%Y:%j:%H:%M:%S', time.gmtime())
current_chandra_time = Chandra.Time.DateTime(current).secs

#--------------------------------------------------------------------------
#-- run_test: check the latest count l1 count rate and xmm orbital altitude 
#--------------------------------------------------------------------------

def run_test():
    """
    check the latest count Il count rate and xmm orbital altitude and
    send out warning if mta_XMM_alert file does not exist.
    input: none
    output: /pool1/mta_XMM_alert if it does not exist already warning eamil
            <data_dir>/l1_alt_record   --- keeps l1 level and altitude data
    """
#
#--- data file which keeps l1 level and altitude
#
    l1_file = data_dir + 'l1_alt_records'
#
#--- check the last entry time so that we don't add too many record
#
    le_time = find_the_last_entry_time(l1_file)
    t_diff  = current_chandra_time - le_time
#
#--- find the latest 30 mins of l1 average and their time span as there are
#--- often slight delay in time in the data aquisition
#
    [l1, start, stop] = l1_median()
#
#--- read xmm altitude data
#
    [atime, alt]      = read_xmm_orbit()
#
#--- check the altitude during the time period
#
    height = 0
    for i in range(0, len(atime)):
        if atime[i] < start:
            continue

        elif atime[i] > stop:
            break

        else:
            if alt[i] > height:
                height = alt[i]
                stime  = atime[i]
#
#--- keep the record if the last entry was more than 5 mins ago
#
    if t_diff >= 300:
        r_time = 0.5 * (start + stop)
        stime  = Chandra.Time.DateTime(r_time).date
        line   = str(stime) + ' : ' + str(r_time) + '\t\t' + str(round(l1,1)) 
        line   = line + '\t\t' + str(round(height,1)) + '\n'

        outfile = l1_file
        #for writing out files in test directory
        if (os.getenv('TEST') == 'TEST'):
            outfile = test_out + "/" + os.path.basename(outfile)
        with open(outfile, 'a') as fo:
            fo.write(line)
#
#--- if the altitude of the satellite is lower then "alt_limit" during the time period,
#--- condtion is not met; stop the program
#    
    if l1 < l1_limit:
        exit(1)

    if height < alt_limit:
        exit(1)
#
#--- both conditions are met; check alert file already exists
#
#
#--- keep the record of alert time
#
    keep_record(stime, height, l1)
#
#--- check wether the alert file exists
#
    go = 0
    if not os.path.isfile(alert_file):
        go = 1
#
#--- if the file exists, check whether the file was created more than 18 hrs ago.
#
    else:
        if check_time_span(alert_file, 64800):
            go = 2
#
#--- if the file does not exist or more than 18 hrs past after creating the file,
#--- create/recreate the file and also send out a warning email.
#
    if go > 0:
#
#--- read the last 30 mins of data
#
        adata = read_data_file(l1_file)

        dline = ''
        for ent in adata[-7:]:
            dline = dline + ent + '\n'
#
#--- alt in kkm
#
        chigh = round((height/1000.0), 3)
#
#--- create email content
#
        line = 'Test threshold crossed, Altitude = ' + str(chigh) + ' kkm with '
        line = line + 'L1 30 min median counts @ ' + str(round(l1,2)) + '.'

        line = line + '\n\n\n'
        line = line + 'Time              \t  (sec)         \t\t L1 cnt      Alt\n'
        line = line + '------------------------------------------------------\n'
        line = line + dline
        line = line + '\n\n\n'

        line = line + 'see:\n\n '  
        line = line + '\t\thttps://cxc.cfa.harvard.edu/mta/RADIATION_new/XMM/ '
        line = line + '\n\nfor the current condition.\n'

        outfile = zspace
        #for writing out files in test directory
        if (os.getenv('TEST') == 'TEST'):
            outfile = test_out + "/" + os.path.basename(outfile)
        with open(outfile, 'w') as fo:
            fo.write(line)
        #for writing out files in test directory
        if (os.getenv('TEST') != 'TEST'):  
        
            cmd = 'cat ' + zspace + '|mailx -s\"Subject: mta_XMM_alert \n\" ' + ' '.join(ADMIN) 
            os.system(cmd)

            cmd = 'rm ' + zspace
            os.system(cmd)
#
#--- create/renew alert_file
#
        rm_file(alert_file)
        newfile = alert_file
        #for writing out files in test directory
        if (os.getenv('TEST') == 'TEST'):
            newfile = test_out + "/" + os.path.basename(newfile)
        cmd = 'touch ' + newfile
        os.system(cmd)

#--------------------------------------------------------------------------
#-- read_xmm_orbit: read xmm orbital elements and return list of distance to XMM 
#--------------------------------------------------------------------------

def read_xmm_orbit():
    """
    read xmm orbital elements and return list of distance to XMM
    input: none but read from /data/mta4/proj/rac/ops/ephem/TLE/xmm.spctrk
    output: [time, alt] time in seconds from 1998.1.1
                        alt  in km from the center of the Earth
    """
#
#--- read xmm orbital elements
#
    cxofile = tle_dir + "Data/xmm.spctrk"
    data    = read_data_file(cxofile)

    atime = []
    alt   = []
    chk   = 0
    for ent in data[6:]:
        atemp = re.split('\s+', ent)
        try:
            chk = float(atemp[0])
        except:
           continue 
#
#--- compute the distance to xmm from the center of the earth
#
        try:
            x = float(atemp[6])
        except:
            continue

        y    = float(atemp[7])
        z    = float(atemp[8])

        dist = math.sqrt(x * x + y * y + z * z)
        alt.append(dist)
#
#--- convert time to seconds from 1998.1.1
#
        atime.append(float(atemp[0])- tcorrect)

    return[atime, alt]

#--------------------------------------------------------------------------
#-- l1_median: find the l1 average count rate for the given time period  -
#--------------------------------------------------------------------------

def l1_median():
    """
    find the l1 median count rate for the given time period
    input:  none but read from: /data/mta4/space_weather/XMM/xmm.archive
    output: med     --- median of L1 over the given time period for last 30 min
            start   --- data period stating time in seconds from 1998.1.1
            stop    --- data period ending time in seconds from 1998.1.1
    """
#
#--- read the data
#
    ifile = xmm_dir + 'Data/xmm_7day.archive2'
    data  = read_data_file(ifile)
#
#--- reverse the data so that we can read from the latest count
#
    rdata  = list(reversed(data))
#
#--- collect the data between start and stop and take l1 average
#
    dsave  = []
    chk    = 0
    for ent in rdata:
        atemp = re.split('\s+', ent)
#
#--- check the line has a correct entry format 
#
        if len(atemp) != 8:
            continue
        try:
            atime = float(atemp[0])
            l1    = float(atemp[2])
        except:
            continue
#
#--- find the time of the first entry (last recoreded entry)
#--- and set the starting time 30 min before that
#
        if chk == 0:
            stop  = atime
            start = stop - 1800
            chk   = 1

        if atime < start:
            break

        dsave.append(l1)
#
#--- take a median
#
    try:
        med = numpy.median(dsave)
    except:
        med = l1

    return [med, start, stop]

#--------------------------------------------------------------------------
#-- check_time_span: check whether the file was created more than or equal to a given time period
#--------------------------------------------------------------------------

def check_time_span(file, tspan):
    """
    check whether the file was created more than or equal to a given time period .
    input:  file    --- a file name
            tspan   --- time span in seconds
    output: True or False
    """
    try:
#
#--- time.time creates the current time
#--- st_ctime extracts the file creation time.
#
        diff = time.time() - os.stat(file).st_ctime
    except:
        diff = 0
#
#--- check the file is older than tspan seconds
#
    if diff >= tspan:
        return True
    else:
        return False
    
#--------------------------------------------------------------------------
#-- keep_record:  keep a record of alert time                            --
#--------------------------------------------------------------------------

def keep_record(time, alt, l1):
    """
    keep a record of alert time
    input:  time    --- alert time
            alt     --- altitude of the xmm of the alert time
            l1      --- 30 min average of l1 rate prior to the alert
    """
    chigh = round((alt/1000.0), 3)

    line = 'Test threshold crossed, Altitude = ' + str(chigh) + ' kkm with '
    line = line + 'L1 30 min average counts @ ' + str(round(l1,2)) + '.\n'
    outfile = zspace#for writing out files in test directory
    if (os.getenv('TEST') == 'TEST'):
        outfile = test_out + "/" +os.path.basename(outfile)
    with open(outfile, 'w') as fo:
        fo.write(line)

    out= xmm_dir + 'Data/alt_trip_records'
    line = str(time) + ': ' + str(chigh) + '\t\t' + str(l1) + '\n'
    #for writing out files in test directory
    if (os.getenv('TEST') == 'TEST'):
        out = test_out + "/" +os.path.basename(out)
    with open(out, 'a') as fo:
        fo.write(line)

#--------------------------------------------------------------------------
#--------------------------------------------------------------------------
#--------------------------------------------------------------------------

def read_data_file(ifile, remove=0):
    if not os.path.isfile(ifile):
        return []
    with open(ifile, 'r') as f:
        data = [line.strip() for line in f.readlines()]

    if remove > 0:
        rm_file(ifile)

    return data

#--------------------------------------------------------------------------
#--------------------------------------------------------------------------
#--------------------------------------------------------------------------

def rm_file(ifile):
    if os.path.isfile(ifile):
        cmd = 'rm -f ' + ifile
        os.system(cmd)

#--------------------------------------------------------------------------
#-- find_the_last_entry_time: find the last entry time                   --
#--------------------------------------------------------------------------

def find_the_last_entry_time(ifile):
    """
    find the last entry time
    input:  ifile   --- data file name. assume that the time is the first entry
    output: stime   --- the last entry time
    """
    p = Popen(['tail', '-1', ifile],shell=False, stderr=PIPE, stdout=PIPE)
    res, err = p.communicate()
    if err:
        print(err.decode())
        stime = current_chandra_time - 600.0
    else:
        last_line = res.decode().strip()
        atemp = re.split('\s+', last_line)
    try:
        stime = float(atemp[1])
    except:
        stime = current_chandra_time - 600.0
    
    return stime

#--------------------------------------------------------------------------

if __name__ == "__main__":

    run_test()
