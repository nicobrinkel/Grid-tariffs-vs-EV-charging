# -*- coding: utf-8 -*-
"""
Created on Mon Apr 28, 2025

@author: 4013425

This script defines a function to optimize EV (electric vehicle) charging sessions 
under capacity-based tariffs (where a fee is paid based on peak monthly usage).
It considers optionally dynamic retail prices and minimizes the total costs, 
including grid capacity fees and energy usage, subject to charging needs.

The optimization uses Gurobi to minimize:
- Monthly peak power fees
- Optionally day-ahead energy costs
- A priority term that encourages earlier charging.
"""

import gurobipy as gp
import pandas as pd
import numpy as np
import datetime
import warnings
import pytz

def capacity_tariffs_preparation(charging_session_data, timesteplist, DA_prices, dynamic_retail_prices_considered, capacity_tariff):
    """
    Optimize EV charging under a capacity tariff (monthly peak pricing).

    Args:
        charging_session_data (pd.DataFrame): DataFrame containing EV session details (arrival time, departure time, max power, demand in kWh).
        timesteplist (list): List of datetime timestamps representing available charging periods.
        DA_prices (pd.DataFrame): DataFrame containing day-ahead electricity prices (€/MWh).
        dynamic_retail_prices_considered (bool): If True, account for dynamic retail prices in the optimization objective.
        capacity_tariff (float): Annual grid capacity tariff (cost per kW per year).

    Returns:
        dict: Dictionary with months as keys (1-12) and corresponding optimized peak power values (kW) as values.
    """

    # Initialize a results DataFrame (index = time steps)
    resultdf = pd.DataFrame(index=timesteplist)
    
    # Dictionary to hold monthly timesteps (for each month)
    timestepdict = {}

    # Large number to scale the priority cost
    M = 1e9

    # Create a list of all 15-minute intervals for each month
    for month in range(1, 13):
        start_date_month = datetime.datetime(2022, month, 1, tzinfo=pytz.timezone('CET'))
        try:
            end_date_month = datetime.datetime(2022, month + 1, 1, tzinfo=pytz.timezone('CET'))
        except:
            end_date_month = datetime.datetime(2023, 1, 1, tzinfo=pytz.timezone('CET'))  # For December
        timestepdict[month] = pd.date_range(start=start_date_month, end=end_date_month, freq='15Min', tz='CET')

    # 15-minute time resolution in hours
    delta_t = 0.25

    # Initialize Gurobi optimization model
    m = gp.Model()
    m.Params.outputFlag = 0  # Suppress Gurobi output
    m.Params.LogToConsole = 0

    # Initialize variables
    p_ch_session = {}  # Charging power (kW) for each session at each timestep
    C_DA_session = {}  # Day-ahead price cost for each session
    C_DA_tot = m.addVar(lb=-np.inf)  # Total day-ahead costs
    p_tot = {}  # Total charging power at each timestep
    p_peak = {}  # Peak power per month
    C_priority_session = {}  # Priority term per session (to encourage early charging)
    C_priority_tot = m.addVar(lb=-np.inf)  # Total priority term
    C_grid = m.addVar(lb=-np.inf)  # Total grid cost

    # Convert timesteplist into a Pandas DatetimeIndex
    timesteps_index = pd.DatetimeIndex(timesteplist)

    # Define variables and constraints for each charging session
    for session in charging_session_data.index:
        # Session characteristics
        arrival_time = charging_session_data.loc[session, 'Arrival time']
        departure_time = charging_session_data.loc[session, 'Departure time']
        p_max = charging_session_data.loc[session, 'Max. charging power (kW)']
        vol = charging_session_data.loc[session, 'Charging demand (kWh)']

        # Filter timesteps within the session window
        timesteplist_session = timesteps_index[(timesteps_index >= arrival_time) & (timesteps_index < departure_time)]

        # Define charging power variables for each timestep of this session
        p_ch_session[session] = m.addVars(timesteplist_session, lb=0, ub=p_max)

        # Enforce that total energy charged matches demand
        m.addConstr(gp.quicksum(p_ch_session[session][t] * delta_t for t in timesteplist_session) == vol)

        # If dynamic pricing is considered, define session-specific DA cost
        if dynamic_retail_prices_considered:
            C_DA_session[session] = m.addVar(lb=-np.inf)
            m.addConstr(C_DA_session[session] == gp.quicksum(
                p_ch_session[session][t] * delta_t *
                DA_prices.loc[t - datetime.timedelta(minutes=t.minute), 'Day-ahead price (€/MWh)'] / 1000
                for t in timesteplist_session
            ))

        # Priority cost term for this session (penalizes late charging)
        C_priority_session[session] = m.addVar(lb=-np.inf)
        m.addConstr(
            C_priority_session[session] == gp.quicksum(
                p_ch_session[session][timesteplist_session[i]] * i for i in range(len(timesteplist_session))
            )
        )

    # Define total power at each timestep across all sessions
    for t in timesteplist:
        # Sessions active at this timestep
        charging_sessions_active_at_t = charging_session_data[
            (charging_session_data['Arrival time'] <= t) & (charging_session_data['Departure time'] > t)
        ]

        # Total power at timestep t
        p_tot[t] = m.addVar(lb=0)
        m.addConstr(p_tot[t] == gp.quicksum(
            p_ch_session[session][t] for session in list(charging_sessions_active_at_t.index)
        ))

    # Define monthly peak variables
    for month in range(1, 13):
        # Peak power for the month
        p_peak[month] = m.addVar()

        # Peak must be at least as large as any individual timestep in that month
        m.addConstrs(p_tot[t] <= p_peak[month] for t in timestepdict[month])

    # Priority cost constraint (sum over all sessions)
    m.addConstr(C_priority_tot == gp.quicksum(C_priority_session[session] for session in list(charging_session_data.index)))

    # Define the objective function
    if dynamic_retail_prices_considered:
        # Total day-ahead cost constraint
        m.addConstr(C_DA_tot == gp.quicksum(C_DA_session[session] for session in list(charging_session_data.index)))

        # Total grid cost = sum of monthly peak fees
        m.addConstr(C_grid == gp.quicksum(p_peak[month] * capacity_tariff / 12 for month in range(1, 13)))

        # Objective: minimize total cost (DA + grid + priority term)
        obj = C_DA_tot + C_grid + C_priority_tot / M
    else:
        # Grid cost only if no dynamic prices
        m.addConstr(C_grid == gp.quicksum(p_peak[month] * capacity_tariff / 12 for month in range(1, 13)))
        obj = C_grid + C_priority_tot / M

    # Set and optimize the objective function
    m.setObjective(obj, gp.GRB.MINIMIZE)
    m.update()
    m.optimize()

    # Retrieve optimized peak values for each month
    peakdict = {}
    for month in range(1, 13):
        peakdict[month] = p_peak[month].X

    return peakdict
