import os
import time
import json
import io
from datetime import timedelta
import pandas as pd
import requests
import logging
from pathlib import Path
import argparse
from fluence import calculate_p3_fluence

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s UTC [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.Formatter.converter = time.gmtime

SPACE_WEATHER = Path(os.getenv("SPACE_WEATHER", "/data/mta4/Space_Weather"))

SPACE_WEATHER_WEB = Path(os.getenv("SPACE_WEATHER_WEB", "/data/mta4/www/RADIATION"))
#SPACE_WEATHER_WEB = Path(os.getenv("SPACE_WEATHER_WEB", "/data/mta4/malgosia"))

JSON_FILE = SPACE_WEATHER_WEB / "Solar-1" / "solar-1-protons.json"

BASE_DIR = Path(__file__).resolve().parent
PARQUET_FILE = BASE_DIR / "proton_history.parquet"
FLUENCE_PARQUET_FILE = BASE_DIR / "fluence_history.parquet"

ACE_FILE = SPACE_WEATHER / "ACE" / "Data" / "ace_7day_archive"

# Base HAPI server URL found with network inspector
SOLAR1_URL = "https://tlv-swpc.woc.noaa.gov/hapi/data"

ION_SPECS = {
    "channels": [f"p{i}" for i in range(1, 9)],
    
    "colors": [
        "#1f77b4",  # C0
        "#ff7f0e",  # C1
        "#2ca02c",  # C2
        "#d62728",  # C3
        "#9467bd",  # C4
        "#8c564b",  # C5
        "#e377c2",  # C6
        "#7f7f7f"   # C7
    ],

    "labels": [
        "47-68 keV",
        "68-117 keV",
        "116-180 keV",
        "180-342 keV",
        "342-537 keV",
        "537-1061 keV",
        "1061-1847 keV",
        "1847-5263 keV"
    ]
}

# For fluence, 2 hours
WINDOW_MINUTES = 120


def load_ace_p3(filename):
    """
    Load ACE P3 data from MTA's ACE 7 day archive.
    """
    columns = [
        "year", "month", "day", "hhmm", "mjd", "seconds",
        "s1", "de1", "de2", "s2",
        "p1", "p3", "p4", "p5", "p6", "index"
    ]

    df = pd.read_csv(
        filename,
        sep=r"\s+",
        names=columns,
        comment="#"
    )

    # Construct UTC timestamps from Year, Month, Day, HHMM
    date = pd.to_datetime(
        df[["year", "month", "day"]],
        utc=True
    )

    hhmm = df["hhmm"].astype(int)

    df["datetime"] = (
        date
        + pd.to_timedelta(hhmm // 100, unit="h")
        + pd.to_timedelta(hhmm % 100, unit="m")
    )

    # Extract P3 and use UTC datetime as index
    df["p3"] = pd.to_numeric(df["p3"], errors="coerce")

    df = df.set_index("datetime")[["p3"]].sort_index()

    df = df[~df.index.duplicated(keep="last")]

    return df


def load_proton_history():
    """
    Load previously stored proton flux measurements from the Parquet file.
    Return the historical DataFrame if the file exists, or an empty
    DataFrame if no saved history is available.
    """
    if os.path.exists(PARQUET_FILE):
        return pd.read_parquet(PARQUET_FILE)
    return pd.DataFrame()


def update_proton_data(df_history, dt_hours, overlap_minutes, timeout=30):
    """
    Update the rolling proton flux history spanning dt_hours using NOAA Solar-1
    measurements. Fetch new data with a configurable overlap to recover delayed
    or revised measurements, and retrieve additional history if the requested
    window expands. Merge records, replace duplicate timestamps with the latest
    values, and return DataFrame limited to the requested time window.
    Parameters
    ----------
    df_history : pandas.DataFrame
        Existing proton flux measurements indexed by UTC timestamps.
    dt_hours : float
        Duration of the rolling historical data window, in hours.
    overlap_minutes : float
        Overlap with previously fetched data, in minutes, to capture
        delayed or revised measurements.
    timeout : int or float, optional
        Maximum time in seconds to wait for the NOAA HTTP response
        (default: 30).
    """
    stop = pd.Timestamp.now(tz="UTC")
    requested_start = stop - timedelta(hours=dt_hours)

    if df_history.empty:
        # Initial download
        start = requested_start
    else:
        # Fetch from overlap_minutes before the last recorded observation
        # with valid data
        valid = df_history[ION_SPECS["channels"]].notna().any(axis=1)

        last_valid = df_history.index[valid].max() if valid.any() else None

        start = (
            last_valid - timedelta(minutes=overlap_minutes)
            if last_valid is not None
            else requested_start
        )

    # Fetch recent measurements
    logging.info(
        "Fetching recent Solar-1 data: %s to %s (%.1f minutes)",
        start, stop, (stop - start).total_seconds() / 60
    )

    df_new = fetch_suprathermal_ions_and_electrons(start, stop, timeout)

    logging.info("Downloaded records: %d", len(df_new))

    if df_history.empty and df_new.empty:
        logging.warning("No Solar-1 measurements available")
        return df_history

    if not df_new.empty:
        # Merge existing and new observations
        df_history = pd.concat([df_history, df_new])

        # Remove overlapping timestamps, keeping latest values
        df_history = df_history[~df_history.index.duplicated(keep="last")]

        logging.info("Merged records: %d", len(df_history))

    # Construct complete one-minute UTC time grid
    full_index = pd.date_range(
        start=requested_start.ceil("min"),
        end=stop.floor("min"),
        freq="1min",
        tz="UTC",
        name="datetime"
    )

    # Remove observations outside the requested interval
    df_history = df_history.loc[
        (df_history.index >= full_index[0]) &
        (df_history.index <= full_index[-1])
    ].sort_index()

    # Insert missing timestamps with NaN values
    df_history = df_history.reindex(full_index)

    return df_history


def fetch_suprathermal_ions_and_electrons(start, stop, timeout):
    """
    Fetch suprathermal ion and electron flux measurements from the NOAA HAPI server.
    Retrieve P1-P8 ion and DE1-DE4 electron channels for the specified UTC interval.
    Parse the response into a Pandas DataFrame indexed by UTC timestamps.
    Return the DataFrame.

    Parameters
    ----------
    start : datetime or pandas.Timestamp
        Start of the requested measurement interval, in UTC.
    stop : datetime or pandas.Timestamp
        End of the requested measurement interval, in UTC.
    timeout : int or float
        Maximum time in seconds to wait for the NOAA HTTP response.
    """

    params = {
        "id": "active-ions-pt1m",
        "parameters": "p1,p2,p3,p4,p5,p6,p7,p8,de1,de2,de3,de4,quality,source",
        "time.min": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time.max": stop.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    # Initialize a clean, empty DataFrame to use as a fallback return value
    # ACE channel energies from LEMS120, see Table 1 in
    # https://www.nesdis.noaa.gov/s3/2025-01/SWFO-L1-Temporal-Spectral-Binning-ATBD.pdf
    columns = ["time_tag",
               "p1", # 47-68 keV, ACE: 46-67 keV
               "p2", # 68-117 keV, ACE: 67-115 keV
               "p3", # 116-180 keV, ACE: 115-193 keV,
               "p4", # 180-342 keV, ACE: 193-315 keV
               "p5", # 342-537 keV, ACE: 315-580 keV,
               "p6", # 537-1,061 keV, ACE: 580-1,060 keV
               "p7", # 1,061-1,847 keV, ACE: 1,060-1,880 keV,
               "p8", # 1,847-5,363 keV, ACE: 1,880-4,700 keV
               "de1", # 47-63 keV, ACE: 45-62 keV
               "de2", # 63-104 keV, ACE: 62-102 keV
               "de3", # 104-169 keV, ACE: 102-175 keV
               "de4", # 169-333 keV, ACE: 175-315 keV
               "quality",
               "source"]

    empty_df = pd.DataFrame(columns=columns)
    empty_df.index = pd.DatetimeIndex([], name="datetime", tz="UTC")

    try:
        response = requests.get(SOLAR1_URL, params=params, timeout=timeout)
        response.raise_for_status()

        raw_text_data = response.text

        # Handle case where server responds with no text contents
        if not raw_text_data or not raw_text_data.strip():
            raise ValueError("NOAA HAPI server returned an empty data payload")

        # Ingest the string stream natively into Pandas
        df = pd.read_csv(io.StringIO(raw_text_data), names=columns, header=1)

        # Handle case where the dataframe was created but contains zero rows
        if df.empty:
            logging.warning("NOAA HAPI returned no measurement records")
            return empty_df

        # Convert to datetime objects
        df["datetime"] = pd.to_datetime(df["time_tag"], utc=True)

        # Set the timestamp as the index for native time-series plotting
        df.set_index("datetime", inplace=True)

        # Ensure all flux channels contain numeric values
        # "coerce" will replace non numeric values with NaN
        flux_channels = [f"p{i}" for i in range(1, 9)] + [f"de{i}" for i in range(1, 5)]
        df[flux_channels] = df[flux_channels].apply(pd.to_numeric, errors="coerce")

        return df.sort_index()

    except requests.exceptions.RequestException as e:
        raise RuntimeError("NOAA HAPI network request failed") from e

    except Exception as e:
        raise RuntimeError("NOAA HAPI data parsing failed") from e


def save_protons_json(df, df_ace, p3_fluence, df_fluence):
    """
    Export Solar-1 differential proton flux data and ACE P3 for Plotly.js.
    """

    channels = ION_SPECS["channels"]

    data = {
        "time": [
            t.isoformat().replace("+00:00", "Z")
            for t in df.index
        ],
        "ions": {
            "channels": channels,
            "colors": ION_SPECS["colors"],
            "labels": ION_SPECS["labels"],
            "flux": {
                ch: df[ch].astype(object)
                         .where(pd.notna(df[ch]), None)
                         .tolist()
                for ch in channels
            }
        },
        "ace": {
            "time": [
                t.isoformat().replace("+00:00", "Z")
                for t in df_ace.index
            ],
            "p3": df_ace["p3"].astype(object)
                             .where(pd.notna(df_ace["p3"]), None)
                             .tolist()
        },
        "p3_fluence": p3_fluence,
        "fluence_history": {
            "time": [
                t.isoformat().replace("+00:00", "Z")
                for t in df_fluence.index
            ],
            "solar1": df_fluence["fluence"].astype(object)
                                 .where(pd.notna(df_fluence["fluence"]), None)
                                 .tolist()
            }
    }

    # Write complete JSON to temporary file, then replace
    # the name to avoid partial json reads by html
    temp_file = JSON_FILE.with_suffix(".json.tmp")

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, allow_nan=False)

    os.replace(temp_file, JSON_FILE)


def update_fluence_history(fluence_result, dt_hours):
    """
    Append the latest Solar-1 P3 fluence estimate to a rolling history.
    Preserve previously calculated values without recalculation.
    """

    timestamp = pd.Timestamp(fluence_result["end_time"])
    fluence = fluence_result["fluence"]

    if FLUENCE_PARQUET_FILE.exists():
        df = pd.read_parquet(FLUENCE_PARQUET_FILE)
    else:
        df = pd.DataFrame(
            {"fluence": pd.Series(dtype=float)},
            index=pd.DatetimeIndex([], name="datetime", tz="UTC")
        )

    # Append only if this timestamp has not been recorded
    if timestamp not in df.index:
        df.loc[timestamp, "fluence"] = fluence

    # Keep only the requested rolling history
    cutoff = timestamp - timedelta(hours=dt_hours)
    df = df.loc[df.index >= cutoff].sort_index()

    # Save atomically
    temp_file = FLUENCE_PARQUET_FILE.with_name(
        FLUENCE_PARQUET_FILE.name + ".tmp"
    )

    df.to_parquet(temp_file)
    os.replace(temp_file, FLUENCE_PARQUET_FILE)

    return df


def production_update(dt_hours, overlap_minutes):
    """
    Fetch Solar-1 and ACE P3 measurements, maintain rolling history,
    and publish JSON for Plotly.js.

    Parameters
    ----------
    dt_hours : float
        Duration of the rolling historical data window, in hours.
    overlap_minutes : float
        Overlap with previously fetched data, in minutes, to capture
        delayed or revised measurements.
    """

    df_history = load_proton_history()
    
    # Fetch and merge latest measurements
    df_history = update_proton_data(df_history, dt_hours, overlap_minutes)

    if df_history.empty:
        return

    solar1_p3_fluence = calculate_p3_fluence(df_history["p3"], WINDOW_MINUTES)

    # Maintain rolling history of calculated Solar-1 P3 fluence
    df_fluence = update_fluence_history(solar1_p3_fluence, dt_hours)

    # Save Solar-1 history for recovery after restart
    df_history.to_parquet(PARQUET_FILE)

    # Load ACE P3 measurements
    df_ace = load_ace_p3(ACE_FILE)

    # Restrict ACE data to the Solar-1 time interval
    df_ace = df_ace.loc[
        (df_ace.index >= df_history.index.min()) &
        (df_ace.index <= df_history.index.max())
    ]

    ace_p3_fluence = calculate_p3_fluence(df_ace["p3"], WINDOW_MINUTES)

    p3_fluence = {
        "solar1": solar1_p3_fluence,
        "ace": ace_p3_fluence
    }

    # Publish combined JSON for Plotly.js
    save_protons_json(df_history, df_ace, p3_fluence, df_fluence)

    logging.info(
        "Updated %d Solar-1 records, latest: %s",
        len(df_history), df_history.index.max()
    )


def main(dt_hours, overlap_minutes):
    """
    Run one Solar-1 and ACE P3 data update.

    TODO:
    The code does not identify instrument-specific numeric fill
    values or invalid measurements indicated by quality flags.
    """

    try:
        production_update(dt_hours, overlap_minutes)
    except Exception:
        logging.exception("Solar-1 update failed")
        raise


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument("--dt_hours", type=float, default=7 * 24)
    parser.add_argument("--overlap_minutes", type=float, default=5)

    args = parser.parse_args()

    # Validate parameters
    if not 0 < args.dt_hours <= 24 * 7:
        parser.error("--dt_hours must be between 0 and 168 hours (7 days)")

    if not 0 <= args.overlap_minutes < args.dt_hours * 60:
        parser.error("--overlap_minutes must be non-negative and shorter than dt_hours")

    main(args.dt_hours, args.overlap_minutes)
