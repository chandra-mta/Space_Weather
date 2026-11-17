import numpy as np
import pandas as pd


def calculate_p3_fluence(p3, window_minutes, now=None):
    """
    Estimate two-hour P3 fluence ending at the current UTC minute.
    Interpolate internal gaps logarithmically (linearly if zero),
    and extrapolate boundary gaps using constant flux.
    Report data completeness and longest missing interval.
    """
    if now is None:
        now = pd.Timestamp.now(tz="UTC")

    end = pd.Timestamp(now).floor("min")

    full_index = pd.date_range(
        end=end,
        periods=window_minutes,
        freq="1min",
        tz="UTC"
    )

    flux = p3.reindex(full_index).copy()
    valid = flux.notna() & np.isfinite(flux) & (flux >= 0)
    flux = flux.where(valid)

    n_valid = int(valid.sum())
    n_missing = window_minutes - n_valid

    # Longest consecutive missing interval
    longest_gap = 0
    current_gap = 0

    for is_valid in valid:
        if is_valid:
            current_gap = 0
        else:
            current_gap = current_gap + 1
            longest_gap = max(longest_gap, current_gap)

    # Initialize
    result = {
        "end_time": end.isoformat(),
        "fluence": None,
        "valid_samples": n_valid,
        "missing_samples": n_missing,
        "valid_percent": 100.0 * n_valid / window_minutes,
        "longest_gap_minutes": longest_gap,
        "latest_valid_time": (
            flux[valid].index[-1].isoformat()
            if n_valid else None
        )
    }

    if n_valid == 0:
        return result

    values = flux.to_numpy(dtype=float)
    valid_positions = np.flatnonzero(valid.to_numpy())

    # Interpolate internal gaps
    for left, right in zip(valid_positions[:-1], valid_positions[1:]):
        if right - left <= 1:
            continue

        a, b = values[left], values[right]
        fractions = np.arange(1, right - left) / (right - left)

        if a > 0 and b > 0:
            values[left + 1:right] = np.exp(
                np.log(a) + fractions * (np.log(b) - np.log(a))
            )
        else:
            values[left + 1:right] = a + fractions * (b - a)

    # Constant extrapolation at boundaries
    first, last = valid_positions[0], valid_positions[-1]
    values[:first] = values[first]
    values[last + 1:] = values[last]

    result["fluence"] = float(np.sum(values) * 60.0)

    return result
