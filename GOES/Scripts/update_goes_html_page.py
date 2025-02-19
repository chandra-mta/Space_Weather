#!/proj/sot/ska3/flight/bin/python
"""
**update_goes_html_page.py**: Update goes differential protons html page.

:Author: W. Aaron (william.aaron@cfa.harvard.edu)
:Last Updated: Feb 18, 2025

"""
import os
import signal
from datetime import datetime, timedelta
import urllib.request
import json
import numpy as np
import argparse
import traceback
import getpass
from jinja2 import Environment, FileSystemLoader
#
#--- Define Directory Pathing
#
GOES_DIR = '/data/mta4/Space_Weather/GOES'
GOES_DATA_DIR = f"{GOES_DIR}/Data"
GOES_TEMPLATE_DIR = f"{GOES_DIR}/Scripts/Template"
HTML_GOES_DIR = '/data/mta4/www/RADIATION_new/GOES'
ADMIN = ['mtadude@cfa.harvard.edu']

#
# --- Links to data sources
#
DLINK = 'https://services.swpc.noaa.gov/json/goes/primary/differential-protons-1-day.json'
ILINK = 'https://services.swpc.noaa.gov/json/goes/primary/integral-protons-1-day.json'
ELINK = 'https://services.swpc.noaa.gov/json/goes/primary/integral-electrons-1-day.json'

#
# --- Energy Designations
#
DIFFERENTIAL_LIST = ['1020-1860 keV',   '1900-2300 keV',   '2310-3340 keV',    '3400-6480 keV',\
               '5840-11000 keV',  '11640-23270 keV', '25900-38100 keV',  '40300-73400 keV',\
               '83700-98500 keV', '99900-118000 keV','115000-143000 keV','160000-242000 keV',\
               '276000-404000 keV']

INTEGRAL_LIST = ['>=1 MeV', '>=5 MeV', '>=10 MeV', '>=30 MeV', '>=50 MeV',\
               '>=60 MeV', '>=100 MeV', '>=500 MeV']

ELECTRON_LIST   = ['>=2 MeV',]

DE = {'P1': [1860., 1020.],
      'P2A': [2300., 1900.],
      'P2B': [3340., 2310.],
      'P3': [6480., 3400.],
      'P4': [11000., 5840.],
      'P5': [23270., 11640.],
      'P6': [38100., 25900.],
      'P7': [73400., 40300.],
      'P8A': [98500., 83700.],
      'P8B': [118000., 99900.],
      'P8C': [143000., 115000.],
      'P9': [242000., 160000.],
      'P5P6': [23270., 11640.],
      'P8ABC': [143000., 83700.],
      'P8ABCP9': [242000., 83700.]
} #: GOES-16+ Energy bands (keV) and combinations

for key in DE.keys():
    de = DE[key] 
    de.append(de[0] - de[1]) #: Add delta_e to each list
#
# --- Template Globals
#
_JINJA_ENV = Environment(loader = FileSystemLoader('Template', followlinks = True))

def update_goes_html_page():
    """Update goes differential and integral html pages
    
    :File Out: <html_dir>/GOES>/goes_pchan_p.html, <html_dir>/GOES>/goes_part_p.html

    """

    diff_table = make_diff_table() #: Generate two hour differential table.
    intg_table = make_intg_table() #: Generate two hour integral table.

    #
    # --- Pull and Render Jinja Template
    #
    diff_template = _JINJA_ENV.get_template('goes_diff.jinja')
    diff_render = diff_template.render(data_table = diff_table)
    intg_template = _JINJA_ENV.get_template('goes_intg.jinja')
    intg_render = intg_template.render(data_table = intg_table)
    #
    # --- Write template contents to a html file
    #
    diff_file = f"{HTML_GOES_DIR}/goes_pchan_p.html"
    os.makedirs(os.path.dirname(diff_file), exist_ok=True)
    with open(diff_file, "w") as f:
        f.write(diff_render)
    
    intg_file = f"{HTML_GOES_DIR}/goes_part_p.html"
    os.makedirs(os.path.dirname(intg_file), exist_ok=True)
    with open(intg_file, "w") as f:
        f.write(intg_render)

def make_diff_table():
    """create two hour table of goes differential proton flux

    :return: Differential GOES protons table
    :rtype: str
    :File Out: <goes_data_dir>/Gp_pchan_5m.txt

    """
#
#--- extract proton data
#
    p_data = extract_goes_data(DLINK, DIFFERENTIAL_LIST, TO_MEV = True)
#
#--- time list
#
    t_list = p_data[0][0]
    d_len  = len(t_list)
#
#--- compute hrc proxy
#
    pre_hrc_val = compute_pre2020_hrc(p_data)
    hrc_val = compute_hrc(p_data)
#
#---- create the main table
#
    line = '\t' * 7
    line = line + 'Most Recent GOES Primary Observations\n'
    line = line + '\t' * 7 
    line = line + 'Proton Flux particles/cm2-s-ster-MeV\n\n'
    line = line + '\tTime\t\t\t'
    line = line + 'P1\t'
    line = line + 'P2A\t'
    line = line + 'P2B\t'
    line = line + 'P3\t'
    line = line + 'P4\t'
    line = line + 'P5\t'
    line = line + 'P6\t'
    line = line + 'P7\t'
    line = line + 'P8A\t'
    line = line + 'P8B\t'
    line = line + 'P8C\t'
    line = line + 'P9\t'
    line = line + 'P10\t'
    line = line + 'HRC_Proxy\t'
    line = line + 'HRC_Proxy_Legacy\n'
    line = line + '\t' + '-'*150 +'\n'
#
#--- aline will save the text output of the table which is used by CRM
#
    aline = ''

    for k in range(0, d_len):
        line = line + '\t' +  t_list[k]  + '\t\t'


        try:
            line = line + adjust_format(p_data[0][1][k]) + "\t"
            line = line + adjust_format(p_data[1][1][k]) + "\t"
            line = line + adjust_format(p_data[2][1][k]) + "\t"
            line = line + adjust_format(p_data[3][1][k]) + "\t"
            line = line + adjust_format(p_data[4][1][k]) + "\t"
            line = line + adjust_format(p_data[5][1][k]) + "\t"
            line = line + adjust_format(p_data[6][1][k]) + "\t"
            line = line + adjust_format(p_data[7][1][k]) + "\t"
            line = line + adjust_format(p_data[8][1][k]) + "\t"
            line = line + adjust_format(p_data[9][1][k]) + "\t"
            line = line + adjust_format(p_data[10][1][k]) + "\t"
            line = line + adjust_format(p_data[11][1][k]) + "\t"
            line = line + adjust_format(p_data[12][1][k]) + "\t"
        except:
            pass

        try:
            line = line + "%5.0f\t\t" % (hrc_val[k])
        except:
            line = line + '\t\t '

        try:
            line = line + f"{pre_hrc_val[k]:5.0f}\n" 
        except:
            line = line + '\n'

    line  = line + '\n'
    aline = line
    line  = line + '\t' + '-'*150 +'\n\n'
#
#--- add average and sum
#
    line = line + '\tAVERAGE\t\t\t'

    line = line + adjust_format(np.mean([i for i in p_data[0][1] if i >=0])) + "\t"
    line = line + adjust_format(np.mean([i for i in p_data[1][1] if i >=0])) + "\t"
    line = line + adjust_format(np.mean([i for i in p_data[2][1] if i >=0])) + "\t"
    line = line + adjust_format(np.mean([i for i in p_data[3][1] if i >=0])) + "\t"
    line = line + adjust_format(np.mean([i for i in p_data[4][1] if i >=0])) + "\t"
    line = line + adjust_format(np.mean([i for i in p_data[5][1] if i >=0])) + "\t"
    line = line + adjust_format(np.mean([i for i in p_data[6][1] if i >=0])) + "\t"
    line = line + adjust_format(np.mean([i for i in p_data[7][1] if i >=0])) + "\t"
    line = line + adjust_format(np.mean([i for i in p_data[8][1] if i >=0])) + "\t"
    line = line + adjust_format(np.mean([i for i in p_data[9][1] if i >=0])) + "\t"
    line = line + adjust_format(np.mean([i for i in p_data[10][1] if i >=0])) + "\t"
    line = line + adjust_format(np.mean([i for i in p_data[11][1] if i >=0])) + "\t"
    line = line + adjust_format(np.mean([i for i in p_data[12][1] if i >=0])) + "\t"

    line = line + "%5.0f\t\t" % (np.mean([i for i in hrc_val if i >= 0]))
    line = line + f"{np.mean([i for i in pre_hrc_val if i >= 0]):5.0f}\n" 
#
    line = line + '\tFLUENCE\t\t\t'
    line = line + adjust_format(np.sum([i for i in p_data[0][1] if i >=0])) + "\t"
    line = line + adjust_format(np.sum([i for i in p_data[1][1] if i >=0])) + "\t"
    line = line + adjust_format(np.sum([i for i in p_data[2][1] if i >=0])) + "\t"
    line = line + adjust_format(np.sum([i for i in p_data[3][1] if i >=0])) + "\t"
    line = line + adjust_format(np.sum([i for i in p_data[4][1] if i >=0])) + "\t"
    line = line + adjust_format(np.sum([i for i in p_data[5][1] if i >=0])) + "\t"
    line = line + adjust_format(np.sum([i for i in p_data[6][1] if i >=0])) + "\t"
    line = line + adjust_format(np.sum([i for i in p_data[7][1] if i >=0])) + "\t"
    line = line + adjust_format(np.sum([i for i in p_data[8][1] if i >=0])) + "\t"
    line = line + adjust_format(np.sum([i for i in p_data[9][1] if i >=0])) + "\t"
    line = line + adjust_format(np.sum([i for i in p_data[10][1] if i >=0])) + "\t"
    line = line + adjust_format(np.sum([i for i in p_data[11][1] if i >=0])) + "\t"
    line = line + adjust_format(np.sum([i for i in p_data[12][1] if i >=0])) + "\t"

    line = line + "%5.0f\t\t" % (np.sum([i for i in hrc_val if i >= 0]))
    line = line + f"{np.sum([i for i in pre_hrc_val if i >= 0]):5.0f}\n\n"
    line = line + '\tHRC Proxy is defined as:\n\n'
    line = line + '\tHRC Proxy  = 143 * P5 + 64738 * P6 + 162505 * P7 + 4127\n\n'

    line = line + '\tHRC Proxy Legacy is defined as:\n\n'
    line = line + '\tHRC Proxy Legacy = 6000 * P5P6 + 270000 * P7 + 100000 * P8ABC\n\n'
    line = line + '\twhere P5P6 is a combination of P5 and P6 and P8ABC is a combination of P8A, P8B, and P8C.\n'

    outfile = f"{GOES_DATA_DIR}/Gp_pchan_5m.txt"
    with open(outfile, 'w') as fo:
        fo.write(aline) #: Write out data file for CRM use

    return line

def make_intg_table():
    """create two hour table of goes integral proton/electron flux

    :return: Integral GOES proton/electron table
    :rtype: str
    :File Out: <goes_data_dir>/Gp_part_5m.txt

    """

    p_save = extract_goes_data(ILINK, INTEGRAL_LIST, TO_MEV=False)

    e_save = extract_goes_data(ELINK, ELECTRON_LIST, TO_MEV=False)

    p_save = p_save + e_save
#
#--- start writing the table
#
    line = '\t' * 10
    line = line + 'Most Recent GOES Primary Observations\n'
    line = line + '\t' * 8
    line = line + 'Solar Particle and Electron Flux particles/cm2-s-ster\n\n'
    line = line + '\tTime\t\t\t>1Mev\t\t>5MeV\t\t>10MeV\t\t>30MeV\t\t>50MeV\t\t'
    line = line + '>60MeV\t\t>100MeV\t\t>500MeV\t\tElectron\n'
    line = line + '\t' + '-'*150 +'\n'
#
#--- aline will save the text output of the table which is used by CRM
#
    aline = ''
#
#--- data length
#
    flen = len(p_save[0][0])
    for k in range(0, flen):
#
#--- print time data 
#
        tout  = str(p_save[0][0][k]).strip()
        line  = line + '\t' + tout + '\t\t'
#
#--- data file has a different time format
#
        aline = aline + datetime.strptime(tout, '%Y:%j:%H:%M').strftime('%Y %m %d %H%M')
        aline = aline + ' 99999 99999\t'    #--- adding dummy julian time
#
#--- print flax data
#
        for m in range(0, len(p_save)):
            try:
                out  = adjust_format(p_save[m][1][k])
            except:  # noqa: E722
                continue
            line = line   +  out +"\t\t" 
            aline = aline + "%2.3e\t\t" % (p_save[m][1][k])
        line = line + '\n'
#
#--- electron does not have distinction for 0.8 2.8 or 4.0; so fake with all E>2.0
#
        try:
            aline = aline  + "%2.3e\t%2.3e\n" % (p_save[m][1][k], p_save[m][1][k])
        except:  # noqa: E722
            aline = aline  + "na\t%na\n" % (p_save[m][1][k], p_save[m][1][k])
#
#--- table break
#
    line = line + '\n'
    line = line + '\t' + '-'*150 +'\n\n'
#
#--- add average and sum of the data
#
    line = line + '\tAVERAGE\t\t\t'
    for m in range(0, len(p_save)):
        out = adjust_format(np.mean(p_save[m][1]))
        line  = line + out + '\t\t'

    line = line + '\n'

    line = line + '\tFLUENCE\t\t\t'
    for m in range(0, len(p_save)):
        out = adjust_format(np.sum(p_save[m][1]) * 7200.0)
        line = line + out + '\t\t'
#
#--- set data file 
#
    bline = ':This file contains data used by CRM scripts\n:Created: Unknown\n'
    for k in range(0, 22):
        bline = bline + '#\n'
    bline = bline + '#\tTime\t\t\t\t\t>1Mev\t\t>5MeV\t\t>10MeV\t\t>30MeV\t\t>50MeV\t\t'
    bline = bline + '>60MeV\t\t>100MeV\t\t>500MeV\t\tElectron\n'
    bline = bline + '\t' + '-'*150 +'\n'
    bline = bline + aline

    with open(f"{GOES_DATA_DIR}/Gp_part_5min.txt", 'w') as fo:
        fo.write(bline)

    return line
    

def extract_goes_data(link, energy_list, TO_MEV):
    """
    extract GOES satellite flux data
    input: link        --- json web address or file
            energy_list --- a list of energy designation 
    output: <data_dir>/<out file>
    """
#
#--- read json file from a file or the web
#
    if os.path.isfile(link):
        with open(link) as f:
            data = json.load(f)
    else:
        with urllib.request.urlopen(link) as url:
            data = json.loads(url.read().decode())
#
#--- go through all energy ranges
#
    elen   = len(energy_list)
    d_save = []
    ctime = datetime.strptime(data[-1]['time_tag'], '%Y-%m-%dT%H:%M:%SZ') - timedelta(hours=2)
    for k in range(0, elen):
        t_list = []
        f_list = []
        energy = energy_list[k]
        last_time = datetime.strptime(data[0]['time_tag'], '%Y-%m-%dT%H:%M:%SZ')
#
#--- check the last entry time and select only last 2hrs
#
        for ent in data:
#
#--- read time and flux of the given energy range
#
            if ent['energy'] == energy:
                if TO_MEV:
                    flux  = float(ent['flux']) * 1e3   #--- keV to MeV
                else:
                    flux  = float(ent['flux'])
                otime =  datetime.strptime(ent['time_tag'], '%Y-%m-%dT%H:%M:%SZ')
                #
                #--- If the otime is more than five minutes after the last_time
                #--- then that means the data set is missing an entry for this energy band and zero values should be append.
                #
                diff = (otime - last_time).seconds
                if diff > 300:
                    for i in range(300,int(diff),300): #: All times should be in divisions of 5 minutes/300 seconds.
                        missing_time = last_time + timedelta(seconds=i)
                        if missing_time > ctime:
                            t_list.append(missing_time.strftime('%Y:%j:%H:%M'))
                            f_list.append(-1e5) #: Mark missing data with the invalid data marker (-1e5)

                if otime > ctime:
                    t_list.append(otime.strftime('%Y:%j:%H:%M'))
                    f_list.append(flux)
                    last_time = otime

        d_save.append([t_list, f_list])
#
#--- Check if there is a missing energy at the beginning or ending of a band.
#
    for i in range(len(d_save)):
        #Find a channel with all 24 needed data points and use those time values
        if len(d_save[i][0]) == 24:
            start = d_save[i][0][0]
            stop = d_save[i][0][-1]
            break

    for i in range(len(d_save)):
        if len(d_save[i][0]) < 24:
            #if there is still not 24 data points, then we are missing the start or end of this channel
            if d_save[i][0][0] != start:
                d_save[i][0].insert(0,start)
                d_save[i][1].insert(0,-1e5)
                
            if d_save[i][0][-1] != stop:
                d_save[i][0].append(stop)
                d_save[i][1].append(-1e5)
    return d_save

def compute_hrc(data):
    """
    compute hrc proxy value

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
    input:  data    --- a list of lists of data: [[<time>, <data1>], [<time>, <data2>],...]
    output: hrc     --- hrc proxy list
    """
    c5  = data[5][1]
    c6  = data[6][1]
    c7  = data[7][1]

    hrc = []

    for k in range(0, len(c5)):
        try:
            val = 143.0 * c5[k] + 64738.0 * c6[k] + 162505.0 * c7[k] + 4127 #: After 2021:125:06:05:00 
            if c5[k] < 0 or c6[k] < 0 or c7[k] < 0:
                val = -1e5 #: Missing a channel value

        except:
            val = -1e5 #: Missing a channel value

        hrc.append(val)

    return hrc

def compute_pre2020_hrc(data):
    p5 = data[5][1]
    p6 = data[6][1]
    p7 = data[7][1]
    p8a = data[8][1]
    p8b = data[9][1]
    p8c = data[10][1]

    hrc = []

    p5p6 = combine_rates([p5, p6], ('P5', 'P6'))
    p8abc = combine_rates([p8a, p8b, p8c], ('P8A', 'P8B', 'P8C'))

    for k in range(len(p5p6)):
        try:
            val = 6000 * p5p6[k] + 270000 * p7[k] + 100000 * p8abc[k]
            if p5p6[k] < 0 or p7[k] < 0 or p8abc[k] < 0:
                val = -1e5 #: Missing a channel value
        except:
            val = -1e5 #: Missing a channel value
        hrc.append(val)
    return hrc


def combine_rates(data_list, channel_name):
    """
    Return combined rates for multiple channels
    """
    combined = np.zeros(len(data_list[0]))
    for i, data in enumerate(data_list):
        combined = combined + (np.array(data) * DE[channel_name[i]][2])
    delta_e = DE[channel_name[-1]][0] - DE[channel_name[0]][1]
    final = list(combined / delta_e)
    for i in range(len(final)):
        if final[i] < 0: #: Prevent from computing with missing data value
            final[i] = -1e5
    return final
def adjust_format(val):

    val = float(val)
    if val < 0: #: Missing entry
        out = f"{val:5.0f}"
    elif val < 10:
        out = "%1.5f" % (val)
    elif val < 100:
        out = "%2.4f" % (val)
    elif val < 1000:
        out = "%3.3f" % (val)
    elif val < 10000:
        out = "%4.2f" % (val)
    elif val < 100000:
        out = "%5.1f" % (val)
    else:
        out = "%5.0f" % (val)
    
    return out

def send_mail(content, subject, admin):
    """
    send out a notification email to admin in case the
    script is found to be stalling, which would impact data file
    used in hrc proxy alerting
    """
    content += f'This message was send to {" ".join(admin)}'
    cmd = f'echo "{content}" | mailx -s "{subject}" {" ".join(admin)}'
    os.system(cmd)
                                                                                           
#----------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mode", choices = ['flight','test'], required = True, help = "Determine running mode.")
    parser.add_argument("-p", "--path", help = "Determine data output file path")
    parser.add_argument("-j", "--json", help = "Determine json data file source")
    parser.add_argument("-e", '--email', nargs = '*', required = False, help = "List of emails to receive notifications")
    args = parser.parse_args()

    if args.mode == 'test':
#
#--- Redefine Admin for sending notification email in test mode
#
        if args.email is not None:
            ADMIN = args.email
        else:
            ADMIN = [os.popen(f"getent aliases | grep {getpass.getuser()}").read().split(":")[1].strip()]
#
#---Define pathing for test output
#
        OUT_DIR = f"{os.getcwd()}/test/_outTest"
        os.makedirs(OUT_DIR, exist_ok = True)
        GOES_TEMPLATE_DIR = f"{os.getcwd()}/Template"
        if args.path:
            GOES_DATA_DIR = args.path
            HTML_GOES_DIR = args.path
        else:
            GOES_DATA_DIR = OUT_DIR
            HTML_GOES_DIR = f"{OUT_DIR}/GOES"

        if args.json:
            DLINK = args.json
        update_goes_html_page()
    elif args.mode == "flight":
#
#--- Create a lock file and exit strategy in case of race conditions
#
        name = os.path.basename(__file__).split(".")[0]
        user = getpass.getuser()
        if os.path.isfile(f"/tmp/{user}/{name}.lock"):
            notification = f"Lock file exists as /tmp/{user}/{name}.lock. Process already running/errored out. " 
            notification += "Check calling scripts/cronjob/cronlog. Killing old process."
            #Email alert if the script stalls out, since HRC alerting depends on output
            send_mail(notification,f"Stalled Script: {name}", ADMIN)
            with open(f"/tmp/{user}/{name}.lock") as f:
                pid = int(f.readlines()[-1].strip())
            #Kill old stalling process and remove corresponding lock file.
            os.remove(f"/tmp/{user}/{name}.lock")
            os.kill(pid,signal.SIGTERM)
            #Generate lock file for the current corresponding process
            os.system(f"mkdir -p /tmp/{user}; echo '{os.getpid()}' > /tmp/{user}/{name}.lock")
        else:
            #Previous script run must have completed successfully. Prepare lock file for this script run.
            os.system(f"mkdir -p /tmp/{user}; echo '{os.getpid()}' > /tmp/{user}/{name}.lock")

        try:
            update_goes_html_page()
        except:  # noqa: E722
            traceback.print_exc()
#
#--- Remove lock file once process is completed
#
        os.system(f"rm /tmp/{user}/{name}.lock")