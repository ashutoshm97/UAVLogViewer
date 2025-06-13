# Name: Ashutosh Mishra
# Date of Modification: June 12, 2025
# Description: This module manages the storage and retrieval of flight log data
# received from the frontend, making it globally accessible to analysis tools.

# This global variable will hold the flight data dictionary (parsed JSON)
SHARED_FLIGHT_DATA: dict | None = None

def set_flight_data(data: dict):
    """
    Sets the flight log data received from the frontend.

    This function updates a global variable, making the flight data
    accessible to all backend analysis tools without needing to pass
    it around explicitly.

    Args:
        data: A dictionary containing the parsed flight log data.
              Expected to be structured as a dictionary where keys are
              log message types (e.g., 'BARO', 'GPS', 'ERR') and values
              are lists of dictionaries representing individual log entries.
    """
    global SHARED_FLIGHT_DATA
    SHARED_FLIGHT_DATA = data
    print("Flight data has been successfully loaded and updated.") # Add confirmation


def get_flight_data() -> dict | None:
    """
    Retrieves the currently loaded flight log data.

    This function provides access to the global flight data for any
    analysis tools that need to operate on it.

    Returns:
        A dictionary containing the flight log data if it has been set,
        otherwise None.
    """
    if SHARED_FLIGHT_DATA is None:
        print("Warning: Attempted to retrieve flight data, but no data is currently loaded.")
    return SHARED_FLIGHT_DATA