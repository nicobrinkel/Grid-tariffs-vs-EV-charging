# -*- coding: utf-8 -*-

import gurobipy as gp
import pandas as pd
import numpy as np
import datetime
import warnings
import pytz

def capacity_tariffs(charging_session_data, timesteplist, CS, DA_prices, dynamic_retail_prices_considered, capacity_tariff, initial_peak):
    """
    Rolling optimization model under capacity tariffs, optimizing each individual timestep to avoid that the model anticipates future charging session in the optimization.
    Args:
        charging_session_data (pd.DataFrame): EV sessions, including arrival/departure, max charging power, and demand (kWh).
        timesteplist (list): List of datetime timestamps to loop over.
        CS (str): Name to represent the column storing the total charging power in the result DataFrame.
        DA_prices (pd.DataFrame): DataFrame with day-ahead prices indexed by timestamp (€/MWh).
        dynamic_retail_prices_considered (bool): If True, energy costs are included in the objective.
        capacity_tariff (float): Annual cost per extra kW of peak capacity.
        initial_peak (float): Initial contracted or observed peak (kW) available before optimization.

    Returns:
        pd.DataFrame: DataFrame indexed by timestep, containing optimized total charging power (column CS).
    """

    # Initialize results DataFrame
    resultdf = pd.DataFrame()

    # Large number to scale the priority term
    M = 1e9

    # Loop over each timestep
    for counter, timestep in enumerate(timesteplist):
        
        # Find active charging sessions at current timestep
        charging_session_data_timestep = charging_session_data[
            (charging_session_data['Arrival time'] <= timestep) &
            (charging_session_data['Departure time'] > timestep)
        ]

        # Only optimize if there are active sessions
        if len(charging_session_data_timestep) > 0:

            # Create list of future timesteps since the considered timestep until the latest departure
            timesteplist_remaining = [
                t for t in timesteplist if t >= timestep and t < charging_session_data_timestep['Departure time'].max()
            ]

            # 15-minute time resolution (in hours)
            delta_t = 0.25

            # Create new Gurobi model
            m = gp.Model()
            m.Params.outputFlag = 0  # Suppress Gurobi output
            m.Params.LogToConsole = 0

            # Initialize variables
            p_ch_session = {}       # Charging power per session
            C_DA_session = {}        # Energy cost per session
            C_DA_tot = m.addVar(lb=-np.inf)  # Total energy cost
            p_tot = {}               # Total power per timestep
            C_priority_session = {}  # Priority cost per session
            C_priority_tot = m.addVar(lb=-np.inf)  # Total priority cost
            C_grid = m.addVar(lb=-np.inf)   # Grid (capacity) cost
            p_peak_extra = m.addVar(lb=0)   # Extra peak needed beyond initial contracted peak

            # Convert timesteplist into DatetimeIndex for quick filtering
            timesteps_index = pd.DatetimeIndex(timesteplist)

            # Define variables and constraints for each active session
            for session in list(charging_session_data_timestep.index):
                # Session characteristics
                arrival_time = charging_session_data_timestep.loc[session, 'Arrival time']
                departure_time = charging_session_data_timestep.loc[session, 'Departure time']
                p_max = charging_session_data_timestep.loc[session, 'Max. charging power (kW)']
                vol = charging_session_data_timestep.loc[session, 'Charging demand (kWh)']

                # Determine already charged volume (if the session started before the current timestep)
                if session in resultdf.columns:\
                    previously_charged_volume = resultdf[session].sum() * delta_t
                else:
                    previously_charged_volume = 0
                    
                # Filter future timesteps for this session
                timesteplist_session = timesteps_index[
                    (timesteps_index >= arrival_time) & (timesteps_index < departure_time)
                ]

                # Define charging power variables (bounded by session max power)
                p_ch_session[session] = m.addVars(timesteplist_session, lb=0, ub=p_max)

                # Ensure the correct amount of energy is delivered
                m.addConstr(
                    gp.quicksum(p_ch_session[session][t] * delta_t for t in timesteplist_session) ==
                    (vol - previously_charged_volume)
                )

                # If dynamic pricing is active, define energy cost variable
                if dynamic_retail_prices_considered:
                    C_DA_session[session] = m.addVar(lb=-np.inf)
                    m.addConstr(
                        C_DA_session[session] == gp.quicksum(
                            p_ch_session[session][t] * delta_t *
                            DA_prices.loc[t - datetime.timedelta(minutes=t.minute), 'Day-ahead price (€/MWh)'] / 1000
                            for t in timesteplist_session
                        )
                    )

                # Priority term to encourage early charging
                C_priority_session[session] = m.addVar(lb=0)
                m.addConstr(
                    C_priority_session[session] == gp.quicksum(
                        p_ch_session[session][timesteplist_session[i]] * i for i in range(len(timesteplist_session))
                    )
                )
            m.addConstr(C_priority_tot == gp.quicksum(C_priority_session[session] for session in charging_session_data_timestep.index))

            # Define total power at each future timestep
            for t in timesteplist_remaining:
                # Find active sessions at time t
                charging_sessions_active_at_t = charging_session_data[
                    (charging_session_data_timestep['Arrival time'] <= t) &
                    (charging_session_data['Departure time'] > t)
                ]

                # Total charging power variable
                p_tot[t] = m.addVar(lb=0)

                # Total power = sum of active session powers
                m.addConstr(p_tot[t] == gp.quicksum(
                    p_ch_session[session][t] for session in list(charging_sessions_active_at_t.index)
                ))

                # Total power must not exceed initial peak + extra peak bought
                m.addConstr(p_tot[t] <= initial_peak + p_peak_extra)

            # Define objective and constraints
            if dynamic_retail_prices_considered:
                # Total day-ahead cost
                m.addConstr(C_DA_tot == gp.quicksum(C_DA_session[session] for session in list(charging_sessions_active_at_t.index)))

                # Grid cost is the extra peak capacity multiplied by tariff
                m.addConstr(C_grid == p_peak_extra * capacity_tariff)

                # Objective: minimize energy + (grid/12 months) + priority term
                obj = C_DA_tot + C_grid / 12 + C_priority_tot / M
            else:
                # If no DA prices, grid cost dominates
                m.addConstr(C_grid == p_peak_extra * capacity_tariff)
                obj = C_grid / 12 + C_priority_tot / M

            # Set and optimize the objective
            m.setObjective(obj, gp.GRB.MINIMIZE)
            m.update()
            m.optimize()

            # Save optimized total power for the current timestep
            resultdf.at[timestep, CS] = p_tot[timestep].X

            # Save session-level charging power decisions
            for session in list(charging_session_data_timestep.index):
                resultdf.at[timestep, session] = p_ch_session[session][timestep].X

            # Update initial_peak after buying any extra peak capacity
            initial_peak += p_peak_extra.X

        else:
            # No active sessions at this timestep
            resultdf.at[timestep, CS] = 0

    # Only return the total system power (CS column)
    resultdf = pd.DataFrame(resultdf[CS])

    return resultdf
