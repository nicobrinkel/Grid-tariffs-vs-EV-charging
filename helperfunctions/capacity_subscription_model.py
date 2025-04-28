# -*- coding: utf-8 -*-

import gurobipy as gp
import pandas as pd
import numpy as np
import datetime
import warnings
import pytz

def capacity_subscription(charging_session_data, timesteplist, CS, DA_prices, dynamic_retail_prices_considered, exceedance_fee, subscribed_capacity):
    """
    Optimize EV charging to minimize energy costs, exceedance fees, and promote early charging,
    under a subscribed capacity constraint.

    Args:
        charging_session_data (pd.DataFrame): EV sessions, including arrival/departure, max charging power, and demand (kWh).
        timesteplist (list): List of datetime timestamps representing discrete optimization periods.
        CS (str): Name for the column that stores total charging power in the results.
        DA_prices (pd.DataFrame): DataFrame indexed by time, containing the day-ahead market prices (€/MWh).
        dynamic_retail_prices_considered (bool): Whether to include dynamic energy prices in the objective.
        exceedance_fee (float): Penalty cost (€/kWh) for energy consumption exceeding subscribed capacity.
        subscribed_capacity (float): Subscribed maximum allowable charging power (kW).

    Returns:
        pd.DataFrame: DataFrame indexed by timestep with optimized total power (column CS).
    """

    # Initialize result dataframe
    resultdf = pd.DataFrame(index=timesteplist)

    # Time resolution in hours (15 min)
    delta_t = 0.25

    # Create Gurobi model
    m = gp.Model()
    m.Params.outputFlag = 0  # Suppress Gurobi output
    m.Params.LogToConsole = 0

    # Initialize variables
    p_ch_session = {}     # Charging power per session
    C_DA_session = {}     # Energy cost per session
    C_DA_tot = m.addVar(lb=-np.inf)  # Total energy cost
    p_tot = {}            # Total charging power at each timestep
    p_subscribed_capacity = {}  # Charging power within subscribed limit
    p_exceedance = {}     # Charging power exceeding subscribed limit
    C_grid = m.addVar(lb=-np.inf)  # Exceedance cost
    M = 1e9               # Large number for priority scaling
    C_priority_session = {}  # Priority cost per session
    C_priority_tot = m.addVar(lb=-np.inf)  # Total priority cost

    # Convert timesteplist into a DatetimeIndex
    timesteps_index = pd.DatetimeIndex(timesteplist)

    # Create variables and constraints for each charging session
    for session in list(charging_session_data.index):
        # Session characteristics
        arrival_time = charging_session_data.loc[session, 'Arrival time']
        departure_time = charging_session_data.loc[session, 'Departure time']
        p_max = charging_session_data.loc[session, 'Max. charging power (kW)']
        vol = charging_session_data.loc[session, 'Charging demand (kWh)']

        # Relevant timesteps for this session
        timesteplist_session = timesteps_index[
            (timesteps_index >= arrival_time) & (timesteps_index < departure_time)
        ]

        # Charging power variable for each active timestep
        p_ch_session[session] = m.addVars(timesteplist_session, lb=0, ub=p_max)

        # Charging demand constraint (energy must match requested volume)
        m.addConstr(
            gp.quicksum(p_ch_session[session][t] * delta_t for t in timesteplist_session) == vol
        )

        # Priority term to favor early charging
        C_priority_session[session] = m.addVar(lb=-np.inf)
        m.addConstr(
            C_priority_session[session] == gp.quicksum(
                p_ch_session[session][timesteplist_session[i]] * i for i in range(len(timesteplist_session))
            )
        )

        # Dynamic pricing cost per session
        if dynamic_retail_prices_considered:
            C_DA_session[session] = m.addVar(lb=-np.inf)
            m.addConstr(
                C_DA_session[session] == gp.quicksum(
                    p_ch_session[session][t] * delta_t *
                    DA_prices.loc[t - datetime.timedelta(minutes=t.minute), 'Day-ahead price (€/MWh)'] / 1000
                    for t in timesteplist_session
                )
            )

    # Create variables and constraints for each timestep
    for t in timesteplist:
        # Find active sessions at timestep t
        charging_sessions_active_at_t = charging_session_data[
            (charging_session_data['Arrival time'] <= t) & (charging_session_data['Departure time'] > t)
        ]

        # Define variables
        p_tot[t] = m.addVar(lb=0)
        p_subscribed_capacity[t] = m.addVar(lb=0, ub=subscribed_capacity)
        p_exceedance[t] = m.addVar(lb=0)

        # Total power constraint
        m.addConstr(
            p_tot[t] == gp.quicksum(
                p_ch_session[session][t] for session in list(charging_sessions_active_at_t.index)
            )
        )

        # Decompose total power into subscribed and exceedance parts
        m.addConstr(
            p_tot[t] == p_subscribed_capacity[t] + p_exceedance[t]
        )

    # Priority cost constraint
    m.addConstr(
        C_priority_tot == gp.quicksum(C_priority_session[session] for session in charging_session_data.index)
    )

    # Objective function definition
    if dynamic_retail_prices_considered:
        m.addConstr(
            C_DA_tot == gp.quicksum(C_DA_session[session] for session in charging_session_data.index)
        )
        m.addConstr(
            C_grid == gp.quicksum(p_exceedance[t] * exceedance_fee * delta_t for t in timesteplist)
        )
        obj = C_DA_tot + C_grid + C_priority_tot / M
    else:
        m.addConstr(
            C_grid == gp.quicksum(p_exceedance[t] * exceedance_fee * delta_t for t in timesteplist)
        )
        obj = C_grid + C_priority_tot / M

    # Set and solve the optimization model
    m.setObjective(obj, gp.GRB.MINIMIZE)
    m.update()
    m.optimize()

    # Store results
    for t in timesteplist:
        resultdf.at[t, CS] = round(p_tot[t].X, 1)

    return resultdf
