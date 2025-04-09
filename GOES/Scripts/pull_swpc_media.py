#!/proj/sot/ska3/flight/bin/python
"""
**pull_swpc_media.py**: Fetches SWPC media for use in the GOES X-Ray webpage

:Author: W. Aaron (william.aaron@cfa.harvard.edu)
:Last Updated: Apr 09, 2025

"""
import os
import sys
import argparse
from urllib.parse import urlparse
#
#--- Define Directory Pathing
#
GOES_MEDIA_DIR = '/data/mta4/www/RADIATION_new/GOES/Media'
#
# --- Links to media sources
#
CCOR_1_7DAYS = 'https://services.swpc.noaa.gov/products/ccor1/mp4s/ccor1_last_7_days.mp4'
SOLAR_MAP = "https://services.swpc.noaa.gov/images/synoptic-map.jpg"
URL_FILES = [CCOR_1_7DAYS,SOLAR_MAP]

def pull_swpc_media():
    """
    Periodically pull SWPC media for GOES web pages.
    """
    for url in URL_FILES:
        file_name = os.path.basename(urlparse(url).path)
        cmd = f"wget -O {GOES_MEDIA_DIR}/{file_name} {url}"
        os.system(cmd)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mode", choices = ['flight','test'], required = True, help = "Determine running mode.")
    parser.add_argument("-p", "--path", help = "Determine data output file path")
    args = parser.parse_args()

    if args.mode == 'test':
        OUT_DIR = f"{os.getcwd()}/test/_outTest"
        if args.path:
            GOES_MEDIA_DIR = args.path
        else:
            GOES_MEDIA_DIR = f"{OUT_DIR}/GOES/Media"
        os.makedirs(GOES_MEDIA_DIR, exist_ok=True)

        pull_swpc_media()

    elif args.mode == "flight":
        pull_swpc_media()