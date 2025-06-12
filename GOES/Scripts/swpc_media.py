#!/proj/sot/ska3/flight/bin/python
"""
**pull_swpc_media.py**: Fetches SWPC media for use in the GOES X-Ray webpage

:Author: W. Aaron (william.aaron@cfa.harvard.edu)
:Last Updated: Apr 09, 2025

:INFO:
    - https://sdo.gsfc.nasa.gov/data/rules.php
    - https://sdo.gsfc.nasa.gov/assets/docs/HMI_M.ColorTable.pdf

"""
import os
import argparse
import json
import math
from urllib.parse import urlparse
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from astropy.table import Table
#
#--- Define Directory Pathing
#
GOES_MEDIA_DIR = '/data/mta4/www/RADIATION_new/GOES/Media'
#
# --- Links to media sources
#
CCOR_1_7DAYS = 'https://services.swpc.noaa.gov/products/ccor1/mp4s/ccor1_last_7_days.mp4'
MAGNETOGRAM_MAP = 'https://sdo.gsfc.nasa.gov/assets/img/latest/latest_2048_HMIBC.jpg'
SOLAR_REGIONS = 'https://services.swpc.noaa.gov/json/solar_regions.json'

URL_FILES = [CCOR_1_7DAYS,MAGNETOGRAM_MAP,SOLAR_REGIONS]
TODAY = datetime.now().strftime("%Y-%m-%d")

def swpc_media():
    """
    Periodically pull SWPC media for GOES web pages.
    """
    for url in URL_FILES:
        file_name = os.path.basename(urlparse(url).path)
        cmd = f"wget -O {GOES_MEDIA_DIR}/{file_name} {url}"
        os.system(cmd)
    #: Select today's active regions
    with open(f"{GOES_MEDIA_DIR}/{os.path.basename(urlparse(SOLAR_REGIONS).path)}") as f:
        raw_json = json.load(f)
        all_regions_table = Table(rows = raw_json)
        todays_regions = all_regions_table[all_regions_table['observed_date'] == TODAY]
    #: 
    img = Image.open(f"{GOES_MEDIA_DIR}/{os.path.basename(urlparse(MAGNETOGRAM_MAP).path)}")
    annotated_img = img.copy()
    w,h = annotated_img.size
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 46)
    draw = ImageDraw.Draw(annotated_img)
    #: Annotate the magnetogram image with the active region locations
    for region in todays_regions:
        lat = region['latitude']
        long = -region['longitude']
        x,y = _to_pixel(w,h,lat,long)
        draw.text((x-112,y+48),str(region['region']), fill='white', font=font)
    
    annotated_img.save(f"{GOES_MEDIA_DIR}/annotated_sdo_hmi_magnetogram.png")
    annotated_img.close()
    img.close()

def _deg2rad(deg):
    return (deg * math.pi) /180

def _to_pixel(w,h,lat,long):
    """
    Use image size to convert lat, long coordinates into pixel locations
    
    :w,h: The pixel size of the image
    :lat: Latitude
    :long: Longitude
    """
    spacing = int(w * 0.042) #: Pixel distance inward of edge of picture to edge of map
    #: Origin of pixel coordinate system is top left
    map_width = w - 2 * spacing
    
    #: Spherical coordinates
    radius = map_width / (2) #: Pixel Units
    latRad = _deg2rad(lat)
    longRad = _deg2rad(long)
    #: Conversion to Cartesian (Origin in center of map is tangent point of image plane to sphere surface)
    
    #: Note that latitude is polar angle with different starting point and axis direction, therefore convert linearly
    horizontal = radius * math.sin((math.pi/2) - latRad) * math.sin(longRad)
    vertical = radius * math.cos((math.pi/2) - latRad)
    
    #: Convert from Cartesian coordinate origin to image origin and rightward downward axis directions.
    x = int(horizontal + w/2)
    y = int(h/2 - vertical)
    
    return x,y

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

        swpc_media()

    elif args.mode == "flight":
        swpc_media()