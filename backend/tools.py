# Name: Ashutosh Mishra
# Date of Modification: June 12, 2025
# Description: This module defines all LangChain tools used by the agent to
# analyze UAV telemetry data parsed from .bin logs. Tools access shared flight
# data and perform domain-specific queries such as altitude analysis, GPS health,
# battery status, RC signal loss detection, mode changes, and critical error lookup.

import json
import pandas as pd
import requests
from bs4 import BeautifulSoup
from data_parser import get_flight_data
from langchain_core.tools import tool
from typing import List
from langchain_core.pydantic_v1 import BaseModel, Field

SUBSYSTEM_MAP = {
    0: "Main system",
    3: "Compass",
    5: "Accelerometer",
    6: "Barometer",
    8: "EKF (Extended Kalman Filter)",
    22: "Gyroscope",
    24: "Board voltage",
    28: "GCS failsafe"
}

ERROR_CODE_MAP = {
    0: "No error (cleared)",
    1: "Error status",
    2: "Warning status",
    3: "Critical",
    4: "Failsafe activated"
}

# Define constants for time window for correlation
CORRELATION_WINDOW_SECONDS = 5.0 # Seconds

class DocLookupInput(BaseModel):
    """
    Defines the input schema for the lookup_ardupilot_documentation tool.
    """
    search_term: str = Field(
        description="The MAVLink message type or keyword to search for "
                    "in the ArduPilot documentation (e.g., 'BARO', 'ERR', 'CTUN')."
    )


# --- Tool Definition ---
@tool(args_schema=DocLookupInput)
def lookup_ardupilot_documentation(search_term: str) -> str:
    """
    Looks up a MAVLink log message, error code, parameter, or general term
    from ArduPilot's official documentation and returns a concise description.

    The function first attempts a direct match by looking for a header with
    a matching ID. If a direct match is not found, it performs a fuzzy
    text search within the entire page content.

    Args:
        search_term: The specific term (e.g., 'ERR', 'GPS', 'MAV_SEVERITY')
                     to search for in the documentation.

    Returns:
        A string containing a relevant documentation snippet if a match is found,
        or an informative message if no documentation is found or an error occurs.
    """
    doc_url = "https://ardupilot.org/plane/docs/logmessages.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        # Fetch the documentation page content
        response = requests.get(doc_url, timeout=10, headers=headers)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)

        soup = BeautifulSoup(response.text, "html.parser")

        # Attempt to find a direct match using header IDs (e.g., <h2 id="ERR">)
        # Convert search term to uppercase for consistent ID matching.
        header = soup.find("h2", id=search_term.upper())
        if header:
            section_content = []
            # Collect content until the next <h2> tag or end of section
            for tag in header.find_next_siblings():
                if tag.name == "h2":
                    break  # Stop at the next main section header
                # Extract text, stripping whitespace and joining with a space
                section_content.append(tag.get_text(strip=True, separator=' '))
                # Limit the length of the extracted section to prevent overwhelming output
                if len(" ".join(section_content)) > 500: # Approximate character limit for a concise snippet
                    break

            if section_content:
                # Return the relevant part of the documentation, limiting to a few paragraphs
                concise_output = " ".join(section_content)
                return f"📘 Documentation for '{search_term.upper()}':\n\n{concise_output[:1000]}..." # Truncate if too long

        # Fallback: Perform a fuzzy text match if no direct header is found
        # Convert entire page text to lowercase for case-insensitive search
        full_text = soup.get_text(separator=" ", strip=True).lower()
        search_term_lower = search_term.lower()

        # Find the starting index of the search term
        idx = full_text.find(search_term_lower)
        if idx != -1:
            # Extract a relevant snippet around the found term
            # Adjust start_idx to get context before the term, but not go negative
            start_idx = max(0, idx - 100)
            # Adjust end_idx to get context after the term
            end_idx = min(len(full_text), idx + len(search_term_lower) + 400) # Get context after the term

            # Ensure the snippet starts and ends cleanly
            snippet = full_text[start_idx:end_idx]
            # Add ellipses to indicate truncation if the snippet doesn't cover the full context
            prefix = "..." if start_idx > 0 else ""
            suffix = "..." if end_idx < len(full_text) else ""

            return f"📘 Partial match for '{search_term}':\n\n{prefix}{snippet}{suffix}"

        # If neither direct nor fuzzy match finds anything
        return f"No relevant documentation section found for '{search_term}'."

    except requests.exceptions.Timeout:
        return "❌ Documentation lookup failed: Request timed out. The documentation server might be slow or unreachable."
    except requests.exceptions.RequestException as e:
        # Catch other requests-related errors (e.g., connection errors, bad status codes)
        return f"❌ Documentation lookup failed due to network or HTTP error: {e}"
    except Exception as e:
        # Catch any other unexpected errors during parsing or processing
        return f"❌ An unexpected error occurred during documentation lookup: {e}"


@tool
def get_highest_altitude() -> str:
    """
    Analyzes BARO (Barometer) log data to find the highest altitude reached during a flight.

    This tool expects flight data to be available via `get_flight_data()` and
    looks for an 'Alt' column within the 'BARO' log. It attempts to detect
    various time fields ('TimeUS', 'time_boot_ms', 'TimeMS') to provide
    a timestamp for the highest altitude.

    Returns:
        A string indicating the highest altitude in meters and the
        corresponding timestamp (if available), or an error message if
        data is missing, malformed, or an unexpected issue occurs.
    """
    flight_data = get_flight_data()

    # Validate the presence of flight data and the BARO log
    if not flight_data:
        return "Flight data is not available. Please upload a log file first."
    if "BARO" not in flight_data:
        return "BARO log data not found in the flight data. Cannot determine highest altitude."

    try:
        baro_df = pd.DataFrame(flight_data["BARO"])

        # Validate that the 'Alt' column exists in the BARO DataFrame
        if "Alt" not in baro_df.columns:
            return "BARO log does not contain an 'Alt' (altitude) field. Unable to find highest altitude."

        # Define potential time columns and their respective divisors for conversion to seconds
        TIME_COLUMNS = {
            "TimeUS": 1_000_000,  # Microseconds to seconds
            "time_boot_ms": 1_000,  # Milliseconds to seconds
            "TimeMS": 1_000       # Milliseconds to seconds
        }

        # Detect the best available time column in the DataFrame
        time_col = next((col for col in TIME_COLUMNS if col in baro_df.columns), None)
        divisor = TIME_COLUMNS.get(time_col, 1) # Default to 1 if no time column found (avoids division by zero)

        # Find the row corresponding to the maximum altitude
        max_row = baro_df.loc[baro_df["Alt"].idxmax()]
        max_altitude = max_row["Alt"]

        time_string = ""
        if time_col and max_row[time_col] is not None:
            timestamp_seconds = max_row[time_col] / divisor
            minutes, seconds_remainder = divmod(timestamp_seconds, 60)
            time_string = f" at {int(minutes)} min {int(seconds_remainder):.2f} sec ({timestamp_seconds:.2f} seconds raw)"
        else:
            time_string = " (timestamp not available)"

        return (
            f"The highest altitude reached was {max_altitude:.2f} meters"
            f"{time_string} (from BARO logs)."
        )

    except KeyError as ke:
        # Catch errors if expected keys are missing after initial checks,
        # indicating malformed data within the BARO log structure.
        return f"Error: Missing expected column in BARO data: {ke}. Please check log integrity."
    except Exception as e:
        # Catch any other unexpected errors during data processing
        return f"An unexpected error occurred while processing BARO data: {e}"

# Define constants for time column processing to avoid magic numbers
TIME_COLUMNS_DIVISORS = {
    "TimeUS": 1_000_000,  # Microseconds to seconds
    "time_boot_ms": 1_000,  # Milliseconds to seconds
    "TimeMS": 1_000       # Milliseconds to seconds
}

def _get_time_column_and_divisor(df: pd.DataFrame) -> tuple[str | None, int]:
    """Helper function to detect the best time column and its divisor."""
    for col, divisor in TIME_COLUMNS_DIVISORS.items():
        if col in df.columns:
            return col, divisor
    return None, 1 # Return None for column and 1 for divisor if no time column found

def _format_time_string(total_seconds: float) -> str:
    """Helper function to format seconds into minutes:seconds and raw seconds."""
    minutes, seconds_remainder = divmod(total_seconds, 60)
    return f"{int(minutes):02d}:{int(seconds_remainder):02d} ({total_seconds:.2f} seconds raw)"


@tool
def find_first_gps_loss() -> str:
    """
    Identifies the first instance of GPS signal degradation during a flight.

    GPS signal degradation is defined by either:
    - Number of satellites (NSats) falling below 6, OR
    - FixType being less than 2 (indicating less than a 2D fix).

    The tool also adds a warning if a complete loss of satellites (NSats = 0)
    persists for a notable duration.

    Returns:
        A string describing the first GPS degradation event with its timestamp
        and the reason(s), along with a potential warning for prolonged signal loss.
        Returns an informative message if GPS data is unavailable, lacks necessary
        fields, or if no degradation is detected.
    """
    flight_data = get_flight_data()

    if not flight_data:
        return "Flight data is not available. Please upload a log file first."
    if 'GPS' not in flight_data:
        return "No 'GPS' log data found in the flight log. Cannot assess GPS signal quality."

    try:
        gps_df = pd.DataFrame(flight_data['GPS'])

        # Check for essential columns (NSats, FixType, and Time)
        has_nsats = 'NSats' in gps_df.columns
        has_fixtype = 'FixType' in gps_df.columns
        time_col, divisor = _get_time_column_and_divisor(gps_df)

        if not time_col:
            return "No valid timestamp column (TimeUS, time_boot_ms, or TimeMS) found in GPS data."
        if not has_nsats and not has_fixtype:
            return "Neither 'NSats' nor 'FixType' fields found in GPS data. Cannot assess GPS signal quality."

        # Define degradation conditions
        degradation_conditions = []
        if has_nsats:
            degradation_conditions.append(gps_df['NSats'] < 6)
        if has_fixtype:
            degradation_conditions.append(gps_df['FixType'] < 2)

        # Combine conditions using logical OR
        # This handles cases where only one of NSats or FixType is present
        combined_condition = pd.Series(False, index=gps_df.index) # Initialize with all False
        for cond in degradation_conditions:
            combined_condition = combined_condition | cond

        degraded_events_df = gps_df[combined_condition]

        if degraded_events_df.empty:
            return "GPS signal remained strong throughout the flight (no degradation events found based on NSats < 6 or FixType < 2)."

        # Get the first degradation event
        first_event = degraded_events_df.iloc[0]
        time_raw = first_event[time_col]
        time_seconds = time_raw / divisor

        # Construct reasons for degradation
        reasons = []
        if has_nsats and first_event['NSats'] < 6:
            reasons.append(f"satellite count ('NSats') dropped to {first_event['NSats']}")
        if has_fixtype and first_event['FixType'] < 2:
            reasons.append(f"fix type ('FixType') was {first_event['FixType']}")

        reason_str = " and ".join(reasons)

        # Check for persistent NSats == 0 (complete signal loss warning)
        warning_message = ""
        if has_nsats:
            # Find consecutive periods of NSats == 0
            zero_sats = gps_df['NSats'] == 0
            # Calculate groups of consecutive True values
            # This creates a series where consecutive True values get the same group ID
            groups = (zero_sats != zero_sats.shift()).cumsum()
            consecutive_zero_sats_durations = gps_df[zero_sats].groupby(groups).size()

            # If there's any group where NSats was 0 for 5 or more consecutive data points
            if any(consecutive_zero_sats_durations >= 5):
                # Calculate the total duration of NSats=0
                total_zero_sat_time_points = gps_df[gps_df['NSats'] == 0].shape[0]
                if total_zero_sat_time_points > 0:
                    # Assuming roughly constant sampling rate, 5 data points is a heuristic for "too long"
                    # For more accuracy, you'd need time differences between points
                    warning_message = (
                        f" (Warning: GPS signal indicated zero satellites for a significant period. "
                        f"Total {total_zero_sat_time_points} data points showed NSats = 0.)"
                    )

        formatted_time = _format_time_string(time_seconds)

        return (
            f"GPS signal degradation was first observed at {formatted_time} "
            f"due to {reason_str}.{warning_message}"
        )

    except KeyError as ke:
        return f"Error: Missing expected column in GPS data: '{ke}'. Please ensure log integrity."
    except Exception as e:
        return f"An unexpected error occurred while processing GPS data for first loss: {e}"


@tool
def get_gps_degradation_duration() -> str:
    """
    Calculates the total approximate duration during which the GPS signal
    was considered degraded (NSats < 6).

    This tool iterates through GPS log entries and sums up time intervals
    where the number of satellites is below the threshold. It provides an
    approximate duration rather than an exact one due to discrete log entries.

    Returns:
        A string indicating the total approximate duration of GPS signal
        degradation in minutes and seconds, or an informative message if
        GPS data is unavailable, lacks necessary fields, or if no degradation
        is detected.
    """
    flight_data = get_flight_data()

    if not flight_data:
        return "Flight data is not available. Please upload a log file first."
    if 'GPS' not in flight_data:
        return "No 'GPS' log data found in the flight log. Cannot calculate GPS degradation duration."

    try:
        gps_df = pd.DataFrame(flight_data['GPS'])

        if 'NSats' not in gps_df.columns:
            return "GPS satellite count ('NSats') not available in the log. Cannot calculate degradation duration."

        time_col, divisor = _get_time_column_and_divisor(gps_df)
        if not time_col:
            return "No valid timestamp column (TimeUS, time_boot_ms, or TimeMS) found in GPS data."

        # Convert time column to seconds for easier calculations
        gps_df['time_seconds'] = gps_df[time_col] / divisor
        gps_df = gps_df.sort_values(by='time_seconds').reset_index(drop=True)

        degraded_segments_duration = 0.0
        # Identify rows where NSats is less than 6
        degraded_indices = gps_df[gps_df['NSats'] < 6].index.tolist()

        if not degraded_indices:
            return "GPS signal remained strong throughout the flight (NSats was always ≥ 6)."

        # Calculate duration of degraded segments
        # Iterate through consecutive degraded points
        i = 0
        while i < len(degraded_indices):
            start_index = degraded_indices[i]
            current_time = gps_df.loc[start_index, 'time_seconds']
            
            # Find the end of the current degraded segment
            j = i
            while j + 1 < len(degraded_indices) and \
                  degraded_indices[j+1] == degraded_indices[j] + 1: # Check for consecutive index
                j += 1
            
            end_index = degraded_indices[j]
            
            # Use the time difference between the last point of the segment and the first point
            # Or if it's a single point, consider a small interval or the interval to the next point
            if start_index == end_index:
                # If it's a single degraded point, consider the average interval around it
                if end_index + 1 < len(gps_df) and start_index > 0:
                    interval = (gps_df.loc[end_index + 1, 'time_seconds'] - gps_df.loc[start_index - 1, 'time_seconds']) / 2
                elif end_index + 1 < len(gps_df): # If it's the first point
                    interval = gps_df.loc[end_index + 1, 'time_seconds'] - gps_df.loc[end_index, 'time_seconds']
                elif start_index > 0: # If it's the last point
                    interval = gps_df.loc[start_index, 'time_seconds'] - gps_df.loc[start_index - 1, 'time_seconds']
                else: # Only one data point or very few
                    interval = 0 # Cannot determine duration from a single point
                degraded_segments_duration += interval
            else:
                segment_duration = gps_df.loc[end_index, 'time_seconds'] - gps_df.loc[start_index, 'time_seconds']
                degraded_segments_duration += segment_duration
            
            i = j + 1 # Move to the next segment


        formatted_duration = _format_time_string(degraded_segments_duration)

        return (
            f"GPS signal was degraded (NSats < 6) for approximately "
            f"{formatted_duration} during the flight."
        )

    except KeyError as ke:
        return f"Error: Missing expected column in GPS data: '{ke}'. Please ensure log integrity."
    except Exception as e:
        return f"An unexpected error occurred while calculating GPS degradation duration: {e}"

@tool
def get_max_battery_temperature() -> str:
    """
    Finds the maximum valid battery temperature recorded in the 'BAT' (Battery) log data.

    This tool processes the 'BAT' log to extract temperature readings. It specifically
    filters out zero or negative temperature values, as these often indicate a
    disabled or malfunctioning sensor rather than actual physical temperatures.

    Returns:
        A string indicating the maximum recorded battery temperature in degrees Celsius (°C),
        or an informative message if battery data is unavailable, lacks a temperature field,
        or contains only invalid (zero or negative) temperature readings.
    """
    flight_data = get_flight_data()

    # Validate the presence of overall flight data
    if not flight_data:
        return "Flight data is not available. Please upload a log file first."

    # Validate the presence of 'BAT' log data
    if 'BAT' not in flight_data or not flight_data['BAT']:
        return "No 'BAT' (battery) log data found in the flight logs."

    try:
        bat_df = pd.DataFrame(flight_data['BAT'])

        # Validate that the 'Temp' column exists in the BAT DataFrame
        if 'Temp' not in bat_df.columns:
            return "Battery temperature data ('Temp' field) is not available in the BAT logs."

        # Filter out invalid temperature values (zero or negative usually indicate sensor issues)
        valid_temps_df = bat_df[bat_df['Temp'] > 0]

        if valid_temps_df.empty:
            return (
                "Battery temperature values are all zero or invalid (non-positive) throughout the log. "
                "The temperature sensor may have been disabled or is malfunctioning for this flight."
            )

        # Find the maximum valid temperature
        max_temp = valid_temps_df['Temp'].max()

        return f"The maximum valid battery temperature recorded was {max_temp:.2f}°C."

    except KeyError as ke:
        # Catch errors if expected keys are missing after initial checks,
        # indicating malformed data within the BAT log structure.
        return f"Error: Missing expected column in BAT data: '{ke}'. Please check log integrity."
    except Exception as e:
        # Catch any other unexpected errors during data processing
        return f"An unexpected error occurred while processing battery temperature data: {e}"


@tool
def get_total_flight_time() -> str:
    """
    Calculates the total flight duration based on the timestamps found in the GPS log data.
    It identifies the start and end timestamps and computes the difference.

    Returns:
        A string detailing the total flight time in minutes and seconds, along with
        the raw start and end timestamps in seconds. It also indicates which time
        column was used. Returns an informative message if flight data or GPS
        data is unavailable, or if timestamps cannot be determined.
    """
    flight_data = get_flight_data()

    # Validate the presence of overall flight data
    if not flight_data:
        return "Flight data is not available. Please upload a log file first."

    # Validate the presence of 'GPS' log data and ensure it's not empty
    if 'GPS' not in flight_data or not flight_data['GPS']:
        return "No 'GPS' data found in the flight log. Unable to calculate flight time."

    try:
        gps_df = pd.DataFrame(flight_data['GPS'])

        # Use the helper function to find the most suitable time column and its divisor
        time_col, divisor = _get_time_column_and_divisor(gps_df)

        if not time_col:
            return "No suitable timestamp column (TimeUS, time_boot_ms, or TimeMS) found in GPS data."

        # Calculate start, end, and duration using the detected time column
        start_raw = gps_df[time_col].min()
        end_raw = gps_df[time_col].max()
        duration_raw = end_raw - start_raw

        # Convert raw timestamps and duration to seconds
        start_seconds = start_raw / divisor
        end_seconds = end_raw / divisor
        duration_seconds = duration_raw / divisor

        # Format the total duration into minutes and seconds
        total_minutes, total_seconds_remainder = divmod(duration_seconds, 60)

        return (
            f"The total flight time was {int(total_minutes)} minutes and {int(total_seconds_remainder)} seconds.\n"
            f"Flight started at: {_format_time_string(start_seconds)}\n"
            f"Flight ended at: {_format_time_string(end_seconds)}\n"
            f"(Based on GPS.{time_col})"
        )

    except KeyError as ke:
        # Catch errors if expected columns are missing, indicating malformed data
        return f"Error: Missing expected column in GPS data: '{ke}'. Please ensure log integrity."
    except Exception as e:
        # Catch any other unexpected errors during data processing
        return f"An unexpected error occurred while processing flight time data: {e}"

# Define constants for RC failsafe IDs and inferred mode changes
RC_FAILSAFE_EV_ID = 10  # Standard Event ID for RC Failsafe in ArduPilot
# Common flight modes often triggered by RC failsafe (e.g., RTL, Land, Loiter)
# These may vary slightly by ArduPilot version or vehicle type.
RC_FAILSAFE_INFERRED_MODES = [5, 6, 9, 11] # 5: RTL, 6: LOITER, 9: AUTO, 11: LAND


@tool
def check_rc_signal_loss() -> str:
    """
    Checks for Remote Control (RC) signal loss events in UAV flight logs.

    The primary method is to look for specific 'EV' (Event) log entries
    (typically Id == 10 for RC Failsafe). If the 'EV' log is not available
    or does not contain RC failsafe events, it attempts to infer RC loss
    based on automatic 'MODE' changes that commonly occur during an RC failsafe
    (e.g., switching to Return-to-Launch or Land mode).

    Returns:
        A string indicating if RC signal loss was detected, the method used (EV or MODE),
        and the approximate timestamp. Returns an informative message if no RC loss
        is detected or if insufficient log data is available to make a determination.
    """
    flight_data = get_flight_data()

    if not flight_data:
        return "Flight data is not available. Please upload a log file first."

    # --- Primary Check: Using 'EV' (Event) logs ---
    if "EV" in flight_data and flight_data["EV"]:
        try:
            ev_df = pd.DataFrame(flight_data["EV"])

            if "Id" not in ev_df.columns:
                return "The 'EV' log is present, but lacks the 'Id' field necessary to detect RC signal loss events."

            rc_failsafe_events = ev_df[ev_df["Id"] == RC_FAILSAFE_EV_ID]

            if not rc_failsafe_events.empty:
                time_col, divisor = _get_time_column_and_divisor(rc_failsafe_events)

                if time_col:
                    first_failsafe_time_raw = rc_failsafe_events.iloc[0][time_col]
                    first_failsafe_time_seconds = first_failsafe_time_raw / divisor
                    formatted_time = _format_time_string(first_failsafe_time_seconds)
                    return (
                        f"✅ RC signal loss detected! The first RC Failsafe (EV.Id = {RC_FAILSAFE_EV_ID}) "
                        f"occurred at {formatted_time}."
                    )
                else:
                    return (
                        f"✅ RC signal loss detected (EV.Id = {RC_FAILSAFE_EV_ID}), "
                        "but no timestamp could be accurately determined from EV logs."
                    )
            else:
                return "✅ 'EV' log is present, and no RC signal loss (EV.Id = 10) was detected."

        except KeyError as ke:
            return f"Error: Missing expected column in EV data: '{ke}'. Cannot process RC signal loss via EV logs."
        except Exception as e:
            return f"An unexpected error occurred while processing 'EV' logs for RC signal loss: {e}"

    # --- Fallback Check: Inferring from 'MODE' changes ---
    elif "MODE" in flight_data and flight_data["MODE"]:
        try:
            mode_df = pd.DataFrame(flight_data["MODE"])

            if "Mode" not in mode_df.columns:
                return "Fallback to MODE log failed: no 'Mode' column present to infer RC signal loss."

            # Filter for modes commonly associated with failsafe triggers
            suspected_failsafe_modes = mode_df[mode_df["Mode"].isin(RC_FAILSAFE_INFERRED_MODES)]

            if not suspected_failsafe_modes.empty:
                time_col, divisor = _get_time_column_and_divisor(suspected_failsafe_modes)

                if time_col:
                    first_suspected_time_raw = suspected_failsafe_modes.iloc[0][time_col]
                    first_suspected_time_seconds = first_suspected_time_raw / divisor
                    formatted_time = _format_time_string(first_suspected_time_seconds)
                    return (
                        f"⚠️ No 'EV' log found. However, based on 'MODE' changes "
                        f"to known failsafe modes (e.g., RTL, Loiter, Auto, Land), "
                        f"an RC failsafe is suspected around {formatted_time}. "
                        "This is an inference, not a direct failsafe event record."
                    )
                else:
                    return (
                        "⚠️ No 'EV' log found, and possible RC failsafe inferred from mode change, "
                        "but no timestamp could be accurately determined from MODE logs."
                    )
            else:
                return (
                    "No 'EV' log found, and no common RC failsafe modes were detected "
                    "in the 'MODE' log. RC signal loss is unlikely."
                )
        except KeyError as ke:
            return f"Error: Missing expected column in MODE data: '{ke}'. Cannot infer RC signal loss."
        except Exception as e:
            return f"An unexpected error occurred while processing 'MODE' logs for RC signal loss inference: {e}"

    # --- No usable logs for determination ---
    return (
        "❌ Neither 'EV' nor 'MODE' logs are available in the flight data. "
        "Unable to determine RC signal loss or provide an inference."
    )


@tool
def analyze_flight_anomalies() -> str:
    """
    Provides a high-level overview of flight anomaly analysis capabilities.

    This tool acts as a general guide, informing the user about the types of
    anomalies that can be analyzed and prompting them to ask more specific
    questions, which will then trigger more specialized tools.

    Returns:
        A string encouraging the user to ask more specific questions about
        flight anomalies.
    """
    return (
        "To analyze flight anomalies, please ask about specific areas of concern, "
        "such as 'list critical errors', 'when did the GPS signal get lost?', "
        "or 'were there any unusual altitude drops?'"
    )


# --- Input Schema for detect_unusual_altitude_drops ---
class AltitudeDropInput(BaseModel):
    """
    Defines the input schema for the detect_unusual_altitude_drops tool.
    """
    threshold_m: float = Field(
        default=10.0,
        description="The minimum altitude drop in meters to be considered unusual. "
                    "Defaults to 10.0 meters if not specified."
    )
    window_s: float = Field(
        default=5.0,
        description="The time window in seconds within which the altitude drop must occur. "
                    "Defaults to 5.0 seconds if not specified."
    )


@tool(args_schema=AltitudeDropInput)
def detect_unusual_altitude_drops(threshold_m: float = 10.0, window_s: float = 5.0) -> str:
    """
    Detects unusual altitude drops in the BARO (Barometer) log data.

    An unusual drop is defined as a decrease in altitude exceeding `threshold_m`
    within a time `window_s`. The function iterates through the altitude data
    to find such occurrences.

    Args:
        threshold_m: The minimum vertical distance (in meters) that constitutes an
                     "unusual" drop. Defaults to 10.0 meters.
        window_s: The maximum time duration (in seconds) over which the altitude
                  drop must occur to be considered "unusual". Defaults to 5.0 seconds.

    Returns:
        A string listing any detected unusual altitude drops with their magnitude,
        duration, and approximate start time, or a message indicating no such drops
        were found. Returns an error message if BARO data is unavailable or malformed.
    """
    flight_data = get_flight_data()

    if not flight_data:
        return "Flight data is not available. Please upload a log file first."
    if "BARO" not in flight_data or not flight_data["BARO"]:
        return "BARO log data not found in the flight data. Cannot detect altitude drops."

    try:
        df = pd.DataFrame(flight_data["BARO"])

        if "Alt" not in df.columns:
            return "Altitude data ('Alt' field) not found in BARO log. Cannot detect altitude drops."

        # Use the helper function to get the time column and its divisor
        time_col, divisor = _get_time_column_and_divisor(df)
        if not time_col:
            return "No valid timestamp column (TimeUS, time_boot_ms, or TimeMS) found in BARO log."

        df["TimeSec"] = df[time_col] / divisor
        df = df.sort_values(by="TimeSec").reset_index(drop=True)

        drops_found = []

        # Optimized iteration for detecting drops
        # This nested loop is acceptable for typical log sizes.
        # For very large logs, more advanced windowing functions might be needed.
        for i in range(len(df)):
            current_time = df.loc[i, "TimeSec"]
            current_alt = df.loc[i, "Alt"]

            # Look ahead in the DataFrame for a drop within the window
            # Use `loc` for explicit index access, `iloc` for positional
            # Filter for points within the time window and lower altitude
            potential_drops = df.loc[
                (df["TimeSec"] > current_time) &
                (df["TimeSec"] <= current_time + window_s) &
                (df["Alt"] < current_alt)
            ]

            if not potential_drops.empty:
                # Find the maximum drop within this window
                # A single max drop might obscure multiple smaller drops, but it's a good summary
                max_alt_in_window = potential_drops['Alt'].min()
                time_of_max_drop = potential_drops.loc[potential_drops['Alt'].idxmin(), 'TimeSec']

                delta_alt = current_alt - max_alt_in_window
                delta_t = time_of_max_drop - current_time

                if delta_alt >= threshold_m:
                    formatted_start_time = _format_time_string(current_time)
                    drops_found.append(
                        f"⚠️ Drop of {delta_alt:.2f}m detected over {delta_t:.2f}s "
                        f"starting at approximately {formatted_start_time}."
                    )

        if drops_found:
            return "Unusual altitude drops detected:\n" + "\n".join(drops_found)
        else:
            return "✅ No unusual altitude drops were detected during the flight based on the given criteria."

    except KeyError as ke:
        return f"Error: Missing expected column in BARO data: '{ke}'. Please ensure log integrity."
    except Exception as e:
        return f"An unexpected error occurred while analyzing altitude data: {e}"


@tool
def analyze_raw_telemetry() -> str:
    """
    Summarizes key telemetry data points from the flight log for high-level anomaly detection
    by the Language Model.

    This tool extracts a limited number of data points (e.g., first 200) from various
    log types (BARO, GPS, BAT, RCIN) to provide the LLM with a snapshot of raw values.
    The LLM can then use this data to identify patterns such as sudden drops, flatlines,
    spikes, or general erratic behavior across different sensor readings.

    Returns:
        A JSON-formatted string containing summarized telemetry data (altitude, GPS quality,
        battery voltage/temperature, RC input), or an informative message if no flight
        data is loaded or an error occurs during summarization.
    """
    flight_data = get_flight_data()
    if not flight_data:
        return "No flight data loaded. Cannot summarize telemetry."

    telemetry_summary = {}
    data_found = False # Flag to track if any relevant data was summarized

    try:
        # BARO (Altitude)
        if 'BARO' in flight_data and flight_data['BARO']:
            baro_df = pd.DataFrame(flight_data['BARO'])
            if 'Alt' in baro_df.columns:
                # Limit to a reasonable number of points for LLM context, drop NaNs
                telemetry_summary['altitude_m'] = baro_df['Alt'].dropna().tolist()[:200]
                data_found = True

        # GPS (Satellites, HDop - Horizontal Dilution of Precision)
        if 'GPS' in flight_data and flight_data['GPS']:
            gps_df = pd.DataFrame(flight_data['GPS'])
            if 'NSats' in gps_df.columns and 'HDop' in gps_df.columns:
                telemetry_summary['gps_quality'] = {
                    'num_satellites': gps_df['NSats'].dropna().tolist()[:200],
                    'hdop': gps_df['HDop'].dropna().tolist()[:200],
                }
                data_found = True

        # BAT (Battery Voltage and Temperature)
        if 'BAT' in flight_data and flight_data['BAT']:
            bat_df = pd.DataFrame(flight_data['BAT'])
            battery_data = {}
            if 'Volt' in bat_df.columns:
                battery_data['voltage_v'] = bat_df['Volt'].dropna().tolist()[:200]
            if 'Temp' in bat_df.columns:
                # Filter out commonly invalid temperature readings (e.g., 0 for disabled sensor)
                battery_data['temperature_c'] = bat_df[bat_df['Temp'] > 0]['Temp'].dropna().tolist()[:200]
            if battery_data:
                telemetry_summary['battery'] = battery_data
                data_found = True

        # RCIN (RC Input - e.g., channel 3 for throttle)
        if 'RCIN' in flight_data and flight_data['RCIN']:
            rcin_df = pd.DataFrame(flight_data['RCIN'])
            # Assuming 'C3' is a common throttle channel, but might need to be dynamic
            if 'C3' in rcin_df.columns:
                telemetry_summary['rc_throttle_input'] = rcin_df['C3'].dropna().tolist()[:200]
                data_found = True

        if not data_found:
            return "No relevant telemetry data (BARO, GPS, BAT, RCIN) found in the flight log for summarization."

        # Return the summarized data as a string for the LLM to analyze
        # Using a simple string representation of the dictionary. For very complex data,
        # consider `json.dumps` for stricter JSON formatting.
        return f"Here is a summary of key telemetry data points:\n{telemetry_summary}"

    except KeyError as ke:
        return f"Error: Missing expected column in telemetry data: '{ke}'. Please ensure log integrity."
    except Exception as e:
        return f"An unexpected error occurred while summarizing telemetry data: {e}"

@tool
def check_battery_temp_stability() -> str:
    """
    Analyzes the 'BAT.Temp' field in the flight logs to determine if the battery
    temperature remained relatively constant throughout the flight.

    It calculates the temperature range (max - min) and standard deviation of
    valid temperature readings. Values of 0 or less are considered invalid
    and are filtered out, as they often indicate a disabled or malfunctioning sensor.

    Returns:
        A string indicating whether the battery temperature was stable or
        fluctuated, including the range and standard deviation if fluctuations
        are detected. Returns an informative message if battery temperature data
        is unavailable or all readings are invalid.
    """
    flight_data = get_flight_data()

    if not flight_data:
        return "Flight data is not available. Please upload a log file first."

    if 'BAT' not in flight_data or not flight_data['BAT']:
        return "No 'BAT' (battery) log data found in the flight logs."

    try:
        bat_df = pd.DataFrame(flight_data['BAT'])

        if 'Temp' not in bat_df.columns:
            return "Battery temperature data ('Temp' field) is not available in the BAT logs."

        # Filter out zero or negative temperatures, which are typically invalid readings
        valid_temps = bat_df[bat_df['Temp'] > 0]['Temp']

        if valid_temps.empty:
            return (
                "All battery temperature values are zero or invalid (non-positive) throughout the log. "
                "The temperature sensor may have been disabled or is malfunctioning."
            )

        temp_range = valid_temps.max() - valid_temps.min()
        temp_std = valid_temps.std()

        # Define thresholds for stability (these can be adjusted based on typical battery behavior)
        # A very small range and standard deviation suggest stability
        if temp_range < 1.5 and temp_std < 0.75: # Slightly relaxed thresholds for real-world minor fluctuations
            return (
                f"✅ The battery temperature remained relatively constant throughout the flight. "
                f"The temperature varied by only ±{temp_range/2:.2f}°C "
                f"(Std Dev: {temp_std:.2f}°C)."
            )
        else:
            return (
                f"⚠️ The battery temperature fluctuated during the flight. "
                f"Range: {valid_temps.min():.2f}°C to {valid_temps.max():.2f}°C "
                f"(Total variation: {temp_range:.2f}°C; Std Dev: {temp_std:.2f}°C)."
            )

    except KeyError as ke:
        return f"Error: Missing expected column in BAT data: '{ke}'. Please ensure log integrity."
    except Exception as e:
        return f"An unexpected error occurred while processing battery temperature stability: {e}"


# --- Output Schema for list_mode_changes ---
class ModeChangeResult(BaseModel):
    """
    Defines the output schema for the list_mode_changes tool, providing
    a list of distinct mode changes and a descriptive note.
    """
    modes: List[str] = Field(
        description="A list of distinct flight mode names or identifiers encountered in sequence."
    )
    note: str = Field(
        description="A descriptive note about the listed mode changes."
    )


@tool
def list_mode_changes() -> str:
    """
    Lists all flight mode changes that occurred during the flight.

    Returns:
        A formatted list of mode transitions with timestamps, or an error/fallback message.
    """
    flight_data = get_flight_data()
    if not flight_data or 'MODE' not in flight_data or not flight_data['MODE']:
        return "MODE log is missing or empty. Cannot determine flight mode changes."

    try:
        mode_log = flight_data["MODE"]

        # --- Normalize wide format dict into row-wise records ---
        if isinstance(mode_log, dict):
            keys = list(mode_log.keys())
            mode_records = [dict(zip(keys, vals)) for vals in zip(*[mode_log[k] for k in keys])]
            mode_df = pd.DataFrame(mode_records)
        elif isinstance(mode_log, list):
            mode_df = pd.DataFrame(mode_log)
        else:
            return "MODE log format is not recognized."

        # Check required columns
        if 'ModeNum' not in mode_df.columns:
            return "MODE log does not contain a 'ModeNum' field, which is required to detect changes."

        # --- Normalize time ---
        time_col, divisor = _get_time_column_and_divisor(mode_df)
        if not time_col:
            return "No usable timestamp column (TimeUS, time_boot_ms, or TimeMS) found in MODE log."

        mode_df['time_sec'] = mode_df[time_col] / divisor

        # --- Detect changes ---
        mode_df = mode_df.sort_values(by='time_sec')
        mode_changes = []
        previous_mode = None

        for _, row in mode_df.iterrows():
            current_mode = row['ModeNum']
            if pd.isna(current_mode):
                continue
            if previous_mode is None or current_mode != previous_mode:
                timestamp = _format_time_string(row['time_sec'])
                mode_name = row.get('ModeText', f"Mode {int(current_mode)}")
                mode_changes.append(f"• `{mode_name}` at {timestamp}")
                previous_mode = current_mode

        if not mode_changes:
            return "✅ No flight mode changes were detected during the flight."
        return (
            "### 📋 Flight Mode Changes Detected\n\n" +
            "\n".join(mode_changes)
        )

    except Exception as e:
        return f"❌ An unexpected error occurred while listing mode changes: {e}"

# --- ArduPilot Subsystem Error Mapping (for list_critical_errors) ---
# This dictionary is based on common ArduPilot log error IDs and their descriptions.
# It should be kept up-to-date with official ArduPilot documentation if new IDs are added.
ARDUPILOT_SUBSYSTEM_MAP = {
    1: "Main system", 2: "Radio", 3: "Compass", 4: "Optical Flow",
    5: "Failsafe: Radio", 6: "Failsafe: Battery", 7: "Failsafe: GPS",
    8: "Failsafe: GCS", 9: "Failsafe: Fence", 10: "Flight mode",
    11: "GPS", 12: "Crash check", 13: "Flip", 14: "Autotune",
    15: "Parachute", 16: "EKF check", 17: "Failsafe: EKF Inav",
    18: "Barometer", 19: "CPU", 20: "Failsafe: ADSB", 21: "Terrain",
    22: "Navigation", 23: "Failsafe: Terrain", 24: "EKF primary",
    25: "Thrust loss check", 26: "Failsafe: Sensors", 27: "Failsafe: Leak",
    28: "Pilot input", 29: "Failsafe: Vibration", 30: "Internal error",
    31: "Failsafe: Dead reckoning",
    # Add other common codes if applicable, e.g., for ECode
    # ECode 0: Clear, 1: Set, 2: Recover, 3: Bad Data etc. (often context-dependent)
}

# General ECode descriptions for common values
ERROR_CODE_DESCRIPTIONS = {
    0: "Cleared",
    1: "Set (error occurred)",
    2: "Recovered from error",
    # Other ECode values are often specific to the Subsystem and might require a more detailed lookup.
}


@tool
def list_critical_errors() -> str:
    """
    Lists all critical error messages recorded in the 'ERR' log of the flight data.

    For each error, it provides the timestamp, the responsible subsystem (e.g., Radio, GPS),
    and the error code with a general explanation (e.g., error set, recovered).
    It uses a built-in mapping for common ArduPilot subsystem and error codes.
    Duplicate (Subsystem, ECode) pairs are filtered to provide a concise list of distinct errors.

    Returns:
        A formatted string detailing the critical errors found, or a message
        indicating no errors were recorded or if data is unavailable/malformed.
    """
    flight_data = get_flight_data()

    if not flight_data:
        return "Flight data is not available. Please upload a log file first."
    if 'ERR' not in flight_data or not flight_data['ERR']:
        return "✅ No 'ERR' (error) messages found in the flight log."

    try:
        err_df = pd.DataFrame(flight_data['ERR'])

        if err_df.empty:
            return "✅ The 'ERR' log is present, but no critical errors were recorded."

        # Use the helper function to find the most suitable time column and its divisor
        time_col, divisor = _get_time_column_and_divisor(err_df)
        if not time_col:
            return "No valid timestamp column (TimeUS, time_boot_ms, or TimeMS) found in ERR log."

        output_lines = ["🛑 **Critical Errors Detected in Flight Log:**"]
        # Use a set to track (subsystem, ecode) pairs to avoid listing redundant errors
        seen_error_types = set()

        for _, row in err_df.iterrows():
            subsys_id = row.get('Subsys')
            ecode = row.get('ECode')
            raw_time = row.get(time_col)

            # Basic validation for Subsys and ECode
            if subsys_id is None or ecode is None:
                # Optionally log a warning here if some entries are malformed
                continue

            # Convert to int, handling potential non-integer types gracefully
            try:
                subsys_id = int(subsys_id)
                ecode = int(ecode)
            except (ValueError, TypeError):
                # Optionally log a warning if conversion fails
                continue

            error_key = (subsys_id, ecode)
            if error_key in seen_error_types:
                continue # Skip if this exact error type (Subsys+ECode) has already been reported
            seen_error_types.add(error_key)

            # Format timestamp
            timestamp_sec = raw_time / divisor
            formatted_timestamp = _format_time_string(timestamp_sec)

            # Get descriptions from maps
            subsys_desc = ARDUPILOT_SUBSYSTEM_MAP.get(subsys_id, f"Unknown Subsystem ({subsys_id})")
            ecode_desc = ERROR_CODE_DESCRIPTIONS.get(ecode, f"Code {ecode}") # Fallback for unknown ECode

            output_lines.append(
                f"- 🕒 `{formatted_timestamp}` — **Subsystem**: {subsys_desc}, "
                f"**Error Code**: {ecode_desc}"
            )

        if len(output_lines) == 1: # Only contains the header
            return "✅ The 'ERR' log is present, but no distinct critical errors were recorded."
        else:
            return "\n".join(output_lines)

    except KeyError as ke:
        return f"Error: Missing expected column in ERR data: '{ke}'. Please ensure log integrity."
    except Exception as e:
        return f"An unexpected error occurred while processing 'ERR' log: {e}"


@tool
def summarize_all_anomalies() -> str:
    """
    Summarizes all detected anomalies and classifies them by severity.
    """
    flight_data = get_flight_data()
    if not flight_data:
        return "⚠️ Flight data not found. Please upload a valid log file first."

    try:
        summaries = []

        err_summary = list_critical_errors.invoke({})
        if "Subsystem" in err_summary:
            summaries.append("🟥 **Critical Errors (Subsystem Faults):**\n" + err_summary)

        gps_health = analyze_gps_health.invoke({})
        summaries.append("🟧 **GPS Signal Anomalies:**\n" + gps_health)

        rc_status = check_rc_signal_loss.invoke({})
        if "loss" in rc_status.lower():
            summaries.append("🟥 **RC Signal Loss:**\n" + rc_status)
        else:
            summaries.append("🟨 **RC Signal Check:**\n" + rc_status)

        ekf_status = analyze_ekf_health_status.invoke({})
        if "error" in ekf_status.lower():
            summaries.append("🟧 **EKF Health Warnings:**\n" + ekf_status)

        drop_check = detect_unusual_altitude_drops.invoke({})
        if "Drop of" in drop_check:
            summaries.append("🟨 **Altitude Drop Detected:**\n" + drop_check)

        battery_check = check_battery_temp_stability.invoke({})
        if "fluctuated" in battery_check or "invalid" in battery_check:
            summaries.append("🟨 **Battery Temperature:**\n" + battery_check)

        return "\n\n".join(summaries) or "✅ No significant anomalies were detected in the flight logs."

    except Exception as e:
        return f"❌ Error while summarizing anomalies: {e}"

@tool
def analyze_gps_health() -> str:
    """
    Provides a comprehensive summary of GPS signal health during the flight.

    This tool consolidates information from:
    1. The first detected instance of GPS signal degradation.
    2. The total approximate duration when the GPS signal was degraded.
    3. A summary of raw GPS telemetry data (NSats, HDop) for detailed inspection.

    Returns:
        A formatted string summarizing GPS health, including degradation events,
        duration, and a snippet of raw data. Returns an error message if
        underlying GPS analysis tools fail.
    """
    try:
        # Invoke other tools to get their respective results
        first_loss_summary = find_first_gps_loss.invoke({})
        degradation_duration_summary = get_gps_degradation_duration.invoke({})
        raw_gps_telemetry_summary = analyze_raw_telemetry.invoke({})

        return (
            "---"
            "## GPS Signal Health Summary\n\n"
            f"📍 **First GPS Degradation Event**: {first_loss_summary}\n\n"
            f"⏱️ **Total Degradation Duration**: {degradation_duration_summary}\n\n"
            f"📊 **Raw GPS Telemetry Snapshot for Further Analysis**:\n"
            f"{raw_gps_telemetry_summary}"
        )
    except Exception as e:
        return f"❌ An error occurred during the comprehensive GPS health analysis: {e}"


@tool
def correlate_errors_with_mode_changes() -> str:
    """
    Correlates ERR (error) logs with MODE (flight mode) changes to detect if
    mode changes may have been triggered by error events.
    """
    try:
        flight_data = get_flight_data()
        if not flight_data:
            return "No flight data available."

        # --- ERR log ---
        if "ERR" not in flight_data:
            return "ERR log not found in the data."

        err_df = pd.DataFrame(flight_data["ERR"])
        if not {"Subsys", "ECode"}.issubset(err_df.columns):
            return "ERR log is missing required fields (Subsys and ECode)."

        time_col_err = next((col for col in ["TimeUS", "TimeMS", "time_boot_ms"] if col in err_df.columns), None)
        if not time_col_err:
            return "Could not find timestamp column in ERR log."

        # --- MODE log ---
        if "MODE" not in flight_data:
            return "MODE log not found in the data."

        mode_log = flight_data["MODE"]
        if isinstance(mode_log, dict):
            try:
                keys = list(mode_log.keys())
                records = [dict(zip(keys, vals)) for vals in zip(*[mode_log[k] for k in keys])]
                mode_df = pd.DataFrame(records)
            except Exception as e:
                return f"⚠️ Failed to normalize MODE log: {e}"
        elif isinstance(mode_log, list):
            mode_df = pd.DataFrame(mode_log)
        else:
            return "MODE log format is unrecognized."

        if not {"Mode", "ModeNum"}.intersection(mode_df.columns):
            return "MODE log is missing required fields (Mode or ModeNum)."

        time_col_mode = next((col for col in ["TimeUS", "TimeMS", "time_boot_ms"] if col in mode_df.columns), None)
        if not time_col_mode:
            return "Could not find timestamp column in MODE log."

        # Normalize timestamps to seconds
        divisor_err = 1_000_000 if time_col_err == "TimeUS" else 1_000
        divisor_mode = 1_000_000 if time_col_mode == "TimeUS" else 1_000
        err_df["time_sec"] = err_df[time_col_err] / divisor_err
        mode_df["time_sec"] = mode_df[time_col_mode] / divisor_mode

        # Analyze correlation
        results = []
        for _, err in err_df.iterrows():
            t_err = err["time_sec"]
            recent_mode_changes = mode_df[(mode_df["time_sec"] >= t_err) & (mode_df["time_sec"] <= t_err + 1)]
            if not recent_mode_changes.empty:
                for _, mode_row in recent_mode_changes.iterrows():
                    t_mode = mode_row["time_sec"]
                    delta = t_mode - t_err
                    subsystem = err.get("Subsys", "Unknown")
                    code = err.get("ECode", "Unknown")
                    mode = mode_row.get("Mode", f"Mode {mode_row.get('ModeNum', '?')}")
                    results.append(f"• Subsystem {subsystem}, Code {code} at {t_err:.2f}s → Mode change to {mode} at {t_mode:.2f}s (Δt = {delta:.2f}s)")

        if not results:
            return "No mode changes were detected within 1 second of error events."
        return "Yes, the following mode changes closely followed error events:\n\n" + "\n".join(results)

    except Exception as e:
        return f"❌ Error during correlation analysis: {str(e)}"

@tool
def detect_sensor_triggered_failsafe() -> str:
    """
    Identifies failsafe events triggered by sensors (e.g., compass, barometer, accelerometer).
    Based on Subsystem and ECode values from ERR logs.
    """
    try:
        flight_data = get_flight_data()
        if not flight_data:
            return "No flight data available."

        if "ERR" not in flight_data:
            return "No ERR logs found. Cannot detect sensor-triggered failsafes."

        err_log = flight_data["ERR"]
        if not isinstance(err_log, list) or len(err_log) == 0:
            return "ERR log is empty or malformed."

        df = pd.DataFrame(err_log)
        if not {"Subsys", "ECode"}.issubset(df.columns):
            return "ERR log is missing required fields (Subsys and ECode)."

        # Filter for known sensor-related subsystems
        sensor_subsystems = [3, 5, 6, 8, 22]
        relevant = df[df["Subsys"].isin(sensor_subsystems)]

        # Look for meaningful error codes: 1 (Error), 3 (Critical), 4 (Failsafe)
        triggered = relevant[relevant["ECode"].isin([1, 3, 4])]

        if triggered.empty:
            return "No sensor-triggered failsafes occurred during the flight."

        messages = []
        for _, row in triggered.iterrows():
            subsystem = SUBSYSTEM_MAP.get(row["Subsys"], f"Subsystem {row['Subsys']}")
            code = ERROR_CODE_MAP.get(row["ECode"], f"Code {row['ECode']}")
            time_field = next((col for col in ["TimeUS", "TimeMS", "time_boot_ms"] if col in row), None)

            if time_field:
                raw_time = row[time_field]
                timestamp = raw_time / (1_000_000 if time_field == "TimeUS" else 1_000)
                minutes, seconds = divmod(timestamp, 60)
                time_str = f"{int(minutes)}:{seconds:.2f}"
            else:
                time_str = "unknown time"

            messages.append(f"• At {time_str}, {subsystem} triggered a failsafe: {code}")

        return "\n".join(messages)

    except Exception as e:
        return f"❌ Internal error while detecting sensor failsafes: {str(e)}"

@tool
def analyze_ekf_health_status() -> str:
    """
    Analyzes the health status of the Extended Kalman Filter (EKF) based on 'ERR' logs.

    It specifically looks for errors related to EKF (Subsystem IDs 16 for EKF_CHECK and 24 for EKF_PRIMARY).
    The tool reports the entry and exit timestamps of the first detected EKF error state
    (ECode=1 for set/error, ECode=0 for clear/recovery) and calculates the duration.

    Returns:
        A formatted string describing the EKF health status, including error periods,
        or a message indicating no EKF errors were found or if data is insufficient.
        Returns an error message if the 'ERR' log is unavailable or malformed.
    """
    flight_data = get_flight_data()

    if not flight_data:
        return "Flight data is not available. Please upload a log file first."
    if "ERR" not in flight_data or not flight_data["ERR"]:
        return "No 'ERR' log data found to analyze EKF health status."

    try:
        err_df = pd.DataFrame(flight_data["ERR"])

        time_col, divisor = _get_time_column_and_divisor(err_df)
        if not time_col:
            return "No valid timestamp column (TimeUS, time_boot_ms, or TimeMS) found in ERR log."

        # Filter for EKF-related errors
        ekf_error_rows = err_df[(err_df["Subsys"].isin([16, 24]))].copy()
        if ekf_error_rows.empty:
            return "✅ No EKF-related errors (Subsystem 16 or 24) found during the flight."

        ekf_error_rows['time_sec'] = ekf_error_rows[time_col] / divisor
        ekf_error_rows = ekf_error_rows.sort_values(by='time_sec').reset_index(drop=True)

        ekf_error_start_time = None
        ekf_error_end_time = None
        all_ekf_events = [] # To list all distinct EKF events for a more comprehensive report

        for _, row in ekf_error_rows.iterrows():
            subsys = int(row.get('Subsys', -1))
            ecode = int(row.get('ECode', -1))
            event_time = row['time_sec']

            subsys_desc = ARDUPILOT_SUBSYSTEM_MAP.get(subsys, f"Unknown EKF Subsystem ({subsys})")
            ecode_desc = ERROR_CODE_DESCRIPTIONS.get(ecode, f"Code {ecode}")
            formatted_event_time = _format_time_string(event_time)

            all_ekf_events.append(
                f"- EKF Event: {subsys_desc}, {ecode_desc} at `{formatted_event_time}`"
            )

            # Detect the first error period (ECode 1 for error, 0 for clear)
            if ecode == 1 and ekf_error_start_time is None:
                ekf_error_start_time = event_time
            elif ecode == 0 and ekf_error_start_time is not None and ekf_error_end_time is None:
                # This finds the first recovery after the first error
                ekf_error_end_time = event_time
                # break # Remove break to find all periods, or keep to focus on first
        
        summary_lines = ["---", "## EKF Health Status Analysis"]
        summary_lines.extend(all_ekf_events) # Include all events for detail

        if ekf_error_start_time is not None and ekf_error_end_time is not None:
            duration = ekf_error_end_time - ekf_error_start_time
            summary_lines.append(
                f"\n**Summary**: EKF entered an error state at `{_format_time_string(ekf_error_start_time)}` "
                f"and recovered at `{_format_time_string(ekf_error_end_time)}`, "
                f"lasting approximately **{duration:.2f} seconds**."
            )
        elif ekf_error_start_time is not None:
            summary_lines.append(
                f"\n**Summary**: EKF entered an error state at `{_format_time_string(ekf_error_start_time)}`, "
                f"but no recovery event (ECode 0) was explicitly logged within the available data."
            )
        else:
            # This case should ideally be caught by ekf_error_rows.empty check
            # but serves as a fallback.
            summary_lines.append("\nNo clear EKF error start or recovery events were found matching the criteria.")
        
        return "\n".join(summary_lines)

    except KeyError as ke:
        return f"Error: Missing expected column in ERR data for EKF analysis: '{ke}'. Please ensure log integrity."
    except Exception as e:
        return f"❌ An unexpected error occurred while analyzing EKF health: {e}"


# --- THE COMPLETE TOOLBOX ---
all_tools = [
    get_highest_altitude,
    find_first_gps_loss,
    get_max_battery_temperature,
    get_total_flight_time,
    list_critical_errors,
    check_rc_signal_loss,
    analyze_flight_anomalies,
    lookup_ardupilot_documentation,
    get_gps_degradation_duration,
    detect_unusual_altitude_drops,
    analyze_raw_telemetry,
    check_battery_temp_stability,
    list_mode_changes,
    analyze_gps_health,
    correlate_errors_with_mode_changes,
    detect_sensor_triggered_failsafe,
    analyze_ekf_health_status,
    summarize_all_anomalies,
]