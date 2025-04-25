# -*- coding: utf-8 -*-
"""
Created on Fri Apr 25 16:27:14 2025

@author: 4013425
"""
def uncontrolled_charging(charging_session_data, timesteplist):
    """
    In this model, the charging schedules for all considered charging sessions are assigned in an uncontrolled manner,
    meaning each EV begins charging at its maximum power from its arrival time until its energy demand is fulfilled 
    or until departure.

    Parameters
    ----------
    charging_session_data : pd.DataFrame
        Pandas DataFrame containing information about the considered charging sessions. It should contain the following columns:
            'Arrival time': the arrival time of the EV to the charging station, rounded to the nearest 15-minute timestamp.
            'Departure time': the departure time of the EV from the charging station, rounded to the nearest 15-minute timestamp. 
            If the connection time exceeds 24 hours, the departure time should be capped accordingly.
            'Charging demand (kWh)': the required energy of the charging session in kWh.
            'Max charging power (kW)': maximum charging power of the session in kW.
            'Charging station ID': identifier for the charging station used in the session.
    
    timesteplist : list
        List of all considered 15-minute timesteps for the simulation.

    Returns
    -------
    resultdf : pd.DataFrame
        DataFrame indexed by timesteps and with one column per charging station, representing the total EV load (kW)
        per timestep per station.
    """
    
    import pandas as pd
    import warnings
    warnings.filterwarnings('ignore')
    
    # Create an empty DataFrame with timesteps as index
    resultdf = pd.DataFrame(index=timesteplist)
    
    # Time resolution (15 minutes = 0.25 hours)
    delta_t = 0.25
    timesteps_index = pd.DatetimeIndex(timesteplist)

    # Iterate through each unique charging station
    for CS in charging_session_data['Charging station ID'].unique():
        # Initialize the column for this charging station with zeros
        resultdf[CS] = [0] * len(resultdf)

        # Filter sessions for this charging station
        charging_session_data_sample = charging_session_data[charging_session_data['Charging station ID'] == CS]

        # Iterate through each session
        for n in charging_session_data_sample.index:
            # Get timesteps that fall within this EV session (arrival to departure)
            start = charging_session_data_sample['Arrival time'][n]
            end = charging_session_data_sample['Departure time'][n]
            timesteplist_session = timesteps_index[(timesteps_index >= start) & (timesteps_index < end)]
            # Charging demand (in kWh)
            E_dem = charging_session_data_sample['Charging demand (kWh)'][n]
            
            # Max charging power (in kW)
            P_max = charging_session_data_sample['Max. charging power (kW)'][n]
            
            # Calculate the number of 15-minute timesteps needed to deliver the total energy
            required_timesteps = E_dem / (P_max * delta_t)

            # Apply full charging power for each full 15-minute timestep
            for t in timesteplist_session[:int(required_timesteps)]:
                resultdf.at[t, CS] += P_max

            # If there's a partial timestep remaining (e.g., 2.75 timesteps = 2 full + 1 partial)
            remaining_fraction = required_timesteps - int(required_timesteps)
            if remaining_fraction > 0:
                # Apply reduced power for the partial timestep
                # This charges only the leftover energy in the next available timestep
                for t in timesteplist_session[int(required_timesteps):int(required_timesteps)+1]:
                    resultdf.at[t, CS] += P_max * remaining_fraction


    return resultdf