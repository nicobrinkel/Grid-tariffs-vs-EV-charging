# -*- coding: utf-8 -*-
"""
Created on Fri Apr 25 17:39:20 2025

@author: 4013425
"""

import gurobipy as gp
import pandas as pd
import numpy as np
import datetime
import warnings
import pytz
warnings.filterwarnings('ignore')
def segmented_volumetric_ToU(charging_session_data, timesteplist, CS, grid_tariff_threshold_df, DA_prices, dynamic_retail_prices_considered, low_tariff, medium_tariff, high_tariff):
    """
    Function to solve a segmented volumetric time-of-use (ToU) optimization problem for electric vehicle (EV) charging sessions.
    
    Args:
        charging_session_data (pd.DataFrame): DataFrame containing charging session details such as arrival and departure times, maximum charging power, and charging demand (in kWh).
        timesteplist (list): List of timestamps representing the grid's time resolution for the optimization process.
        CS (str): Name of the charging station.
        grid_tariff_df (pd.DataFrame): DataFrame with the grid tariff information, including thresholds for price categories.
        DA_prices (pd.DataFrame): Day-ahead prices for energy, with a column for price values.
        dynamic_retail_prices_considered (bool): Flag to indicate whether dynamic retail prices should be considered in the optimization.
        low_tariff (float): The price per kWh for the consumption at low tariff times/power
        medium_tariff (float): The price per kWh for the consumption at medium tariff times/power
        high_tariff (float): The price per kWh for the consumption at high tariff times/power
    Returns:
        pd.DataFrame: DataFrame containing the optimized charging power for each time step at the given charging station.
    """

    # Initialize an empty DataFrame to store results, with all values initially set to 0.
    resultdf = pd.DataFrame(0, index=timesteplist, columns=[CS])

    # Convert timesteplist to a pandas DatetimeIndex to facilitate time-based slicing.
    timesteps_index = pd.DatetimeIndex(timesteplist)
    
    # Time resolution (15 minutes = 0.25 hours).
    delta_t = 0.25
    
    # Large constant for scaling priority-related cost term.
    M = 1e9
    
    # Initialize a Gurobi model to formulate the optimization problem.
    m = gp.Model()
    m.Params.outputFlag = 0  # Suppresses all Gurobi output.
    m.Params.LogToConsole = 0
    
    # Dictionaries to hold variables for charging sessions, cost terms, and power totals.
    p_ch_session = {}  # Dictionary to store charging power for each session at each timestep.
    C_DA_session = {}  # Dictionary to store day-ahead price-related costs for each charging session.
    C_DA_tot = m.addVar(lb=-np.inf)  # Total day-ahead cost for all charging sessions.
    p_tot = {}  # Dictionary to store total charging power at each timestep.
    p_tot_pricecat1 = {}  # Dictionary to store charging power for the first price category at each timestep.
    p_tot_pricecat2 = {}  # Dictionary to store charging power for the second price category at each timestep.
    p_tot_pricecat3 = {}  # Dictionary to store charging power for the third price category at each timestep.
    C_grid = m.addVar(lb=-np.inf)  # Total grid tariff cost.
    C_priority_session = {}  # Dictionary to store the priority cost term for each charging session.
    C_priority_tot = m.addVar(lb=-np.inf)  # Total priority cost for all sessions.
    
    # Loop over each charging session to define variables and constraints.
    for session in charging_session_data.index:
        # Extract session details from the input data.
        arrival_time = charging_session_data.loc[session, 'Arrival time']
        departure_time = charging_session_data.loc[session, 'Departure time']
        p_max = charging_session_data.loc[session, 'Max. charging power (kW)']
        vol = charging_session_data.loc[session, 'Charging demand (kWh)']

        # Filter timesteps that fall within this session's arrival and departure times.
        timesteplist_session = timesteps_index[(timesteps_index >= arrival_time) & (timesteps_index < departure_time)]
        
        # Add a variable for the charging power at each timestep for the current session.
        p_ch_session[session] = m.addVars(timesteplist_session, lb=0, ub=p_max)
        
        # Add a constraint ensuring that the total charging power over the session matches the charging demand.
        m.addConstr(gp.quicksum(p_ch_session[session][t] * delta_t for t in timesteplist_session) == vol)
        
        # Add a variable for the priority cost term related to this session.
        C_priority_session[session] = m.addVar(lb=-np.inf)
        m.addConstr(C_priority_session[session] == gp.quicksum(p_ch_session[session][timesteplist_session[i]] * i for i in range(len(timesteplist_session))))

        # If dynamic retail prices are considered, add a cost term for day-ahead prices.
        if dynamic_retail_prices_considered:
            C_DA_session[session] = m.addVar(lb=-np.inf)
            m.addConstr(C_DA_session[session] == gp.quicksum(p_ch_session[session][t] * delta_t * DA_prices.loc[t - datetime.timedelta(minutes=t.minute), 'Day-ahead price (€/MWh)'] / 1000 for t in timesteplist_session))

    # Loop over each timestep to calculate total charging power and costs.
    for t in timesteplist:
        # Identify the charging sessions active at the current timestep.
        charging_sessions_active_at_t = charging_session_data[(charging_session_data['Arrival time'] <= t) & (charging_session_data['Departure time'] > t)]
        
        # Add variables for total charging power and price categories at each timestep.
        p_tot[t] = m.addVar(lb=0)
        p_tot_pricecat1[t] = m.addVar(lb=0, ub=grid_tariff_threshold_df.loc[t, 'Threshold_1'])
        p_tot_pricecat2[t] = m.addVar(lb=0, ub=grid_tariff_threshold_df.loc[t, 'Threshold_2'])
        p_tot_pricecat3[t] = m.addVar(lb=0)
        
        # Add constraints for total charging power and price category sums.
        m.addConstr(p_tot[t] == gp.quicksum(p_ch_session[session][t] for session in charging_sessions_active_at_t.index))
        m.addConstr(p_tot[t] == p_tot_pricecat1[t] + p_tot_pricecat2[t] + p_tot_pricecat3[t])
    
    # Add a constraint for the total priority cost across all sessions.
    m.addConstr(C_priority_tot == gp.quicksum(C_priority_session[session] for session in charging_session_data.index))
    
    # Add constraints for dynamic retail prices if applicable.
    if dynamic_retail_prices_considered:
        m.addConstr(C_DA_tot == gp.quicksum(C_DA_session[session] for session in charging_session_data.index))
        m.addConstr(C_grid == gp.quicksum(p_tot_pricecat1[t] * low_tariff * delta_t for t in timesteplist) +
                    gp.quicksum(p_tot_pricecat2[t] * medium_tariff * delta_t for t in timesteplist) +
                    gp.quicksum(p_tot_pricecat3[t] * high_tariff * delta_t for t in timesteplist))
        
        # Define the objective function (minimizing total cost including day-ahead prices, grid costs, and priority costs).
        obj = C_DA_tot + C_grid + C_priority_tot / M
    else:
        # Define the objective function (minimizing total cost including grid costs and priority costs).
        m.addConstr(C_grid == gp.quicksum(p_tot_pricecat1[t] * low_tariff * delta_t for t in timesteplist) +
                    gp.quicksum(p_tot_pricecat2[t] * medium_tariff * delta_t for t in timesteplist) +
                    gp.quicksum(p_tot_pricecat3[t] * high_tariff * delta_t for t in timesteplist))
        
        obj = C_grid + C_priority_tot / M
    
    # Set the objective function to be minimized and solve the model.
    m.setObjective(obj, gp.GRB.MINIMIZE)
    m.update()
    m.optimize()
    
    # After optimization, store the results (optimized charging power) in the result dataframe.
    for t in timesteplist:
        resultdf.at[t, CS] = round(p_tot[t].X, 1)

    return resultdf
