# -*- coding: utf-8 -*-
"""
Created on Fri Apr 25 16:49:21 2025

Author: 4013425
"""

import gurobipy as gp
import pandas as pd
import numpy as np
import datetime
import warnings
warnings.filterwarnings('ignore')

def volumetric_ToU(charging_session_data, timesteplist, CS, grid_tariff_df, DA_prices, dynamic_retail_prices_considered):
    """
    Optimizes the charging schedule for electric vehicles (EVs) using a **Volumetric Time-of-Use (ToU) pricing model**. 
    The goal is to minimize the charging cost considering grid tariffs and possibly dynamic retail prices.
    
    Parameters
    ----------
    charging_session_data : pd.DataFrame
        DataFrame containing information about the charging sessions. The columns expected are:
            'Arrival time' : The arrival time of the EV to the charging station.
            'Departure time' : The departure time of the EV from the charging station.
            'Max. charging power (kW)' : The maximum charging power of the EV.
            'Charging demand (kWh)' : The total energy demand of the EV for the session.
    
    timesteplist : list
        List of all considered timesteps in the optimization, typically each 15-minute interval.

    CS : str
        Charging station identifier for the current charging station.
    
    grid_tariff_values : pd.DataFrame
        DataFrame containing grid tariffs at each timestep in the form of €/kWh. It must have a datetime index 
        representing the times of grid tariff prices.
    
    DA_prices : pd.DataFrame
        DataFrame containing the day-ahead electricity prices in €/MWh for each timestep.
        The index should be datetime objects, with one entry per time period.

    dynamic_retail_prices : bool
        Flag to specify whether to include dynamic retail prices in the objective function.
        If True, the dynamic retail prices will be used along with the grid tariff prices for optimization.

    Returns
    -------
    resultdf : pd.DataFrame
        DataFrame indexed by timesteps with the charging power for each timestep at the charging station `CS`.
        The charging power is in kW.

    """

    # Initialize an empty DataFrame with all values set to 0 to store the results
    resultdf = pd.DataFrame(0, index=timesteplist, columns=[CS])

    # Convert timesteplist to a pandas DatetimeIndex to facilitate time-based slicing
    timesteps_index = pd.DatetimeIndex(timesteplist)
    
    # Time resolution (15 minutes = 0.25 hours)
    delta_t = 0.25
    
    # Large constant for scaling priority-related cost term
    M = 1e9

    # Loop through each charging session
    for session in charging_session_data.index:
        # Extract session details from the input data
        arrival_time = charging_session_data.loc[session, 'Arrival time']
        departure_time = charging_session_data.loc[session, 'Departure time']
        p_max = charging_session_data.loc[session, 'Max. charging power (kW)']
        vol = charging_session_data.loc[session, 'Charging demand (kWh)']
        
        # Filter timesteps that fall within this session's arrival and departure times
        timesteplist_session = timesteps_index[(timesteps_index >= arrival_time) & (timesteps_index < departure_time)]
        
        # Create a new optimization model using Gurobi
        m = gp.Model()
        m.Params.outputFlag = 0  # Suppresses all Gurobi output

        m.Params.LogToConsole = 0  # Suppress Gurobi output to console
        
        # Define decision variables for charging power at each timestep
        p_ch = m.addVars(timesteplist_session, lb=0, ub=p_max)
        
        # Define a variable for the total grid cost
        C_grid = m.addVar()
        
        # New variable to prioritize charging at certain times (priority cost)
        C_priority = m.addVar()

        # Constraint: Total energy delivered (sum of power * time step) must equal the charging demand
        m.addConstr(gp.quicksum(p_ch[t] * delta_t for t in timesteplist_session) == vol)
        
        # Constraint: Total cost of grid consumption
        m.addConstr(C_grid == gp.quicksum(p_ch[t] * delta_t * grid_tariff_df.loc[t, 'Grid tariff (€/kWh)'] 
                                           for t in timesteplist_session))
        
        # The goal is to prioritize charging earlier in the session if this leads to the same costs
        # The priority term is based on the order of timesteps (earlier timesteps get higher weights)
        m.addConstr(C_priority == gp.quicksum(p_ch[timesteplist_session[i]] * i for i in range(len(timesteplist_session))))

        # If dynamic retail prices are used, we add another cost term for the dynamic prices
        if dynamic_retail_prices_considered:
            C_DA = m.addVar(lb=-np.inf)  # Day-ahead price cost variable
            m.addConstr(C_DA == gp.quicksum(p_ch[t] * delta_t * DA_prices.loc[t - datetime.timedelta(minutes=t.minute), 
                                            'Day-ahead price (€/MWh)'] / 1000 for t in timesteplist_session))
            # Objective function: Minimize both day-ahead price cost, grid consumption cost, and the priority cost. 
            # By dividing C_priority by M, we ensure that the optimizer only prioritizes if this leads to the same grid costs and dynamic retail prices.
            obj = C_DA + C_grid + C_priority / M
        else:
            # If no dynamic retail prices, minimize only grid cost and priority cost.
            # By dividing C_priority by M, we ensure that the optimizer only prioritizes if this leads to the same grid costs and dynamic retail prices.
            obj = C_grid + C_priority / M

        # Set the objective function (to minimize the total cost)
        m.setObjective(obj, gp.GRB.MINIMIZE)
        
        # Update and optimize the model
        m.update()
        m.optimize()

        # Create a temporary DataFrame to store the charging power for this session
        resultdf_session = pd.DataFrame(0, index=resultdf.index, columns=['Charging power session'])
        
        # Store the optimal charging power for each timestep in the result dataframe
        for t in timesteplist_session:
            resultdf_session.at[t, 'Charging power session'] = round(p_ch[t].X, 1)

        # Add the result from this session to the overall result DataFrame
        resultdf[CS] += resultdf_session['Charging power session']
    
    return resultdf
