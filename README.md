
# Grid Tariffs vs EV charging[![DOI](https://zenodo.org/badge/776002789.svg)](https://zenodo.org/doi/10.5281/zenodo.10932795)

![Static Badge](https://img.shields.io/badge/MADE_WITH-PYTHON_-orange?style=for-the-badge)

[![matplotlib](https://img.shields.io/badge/matplotlib-3.9.2-blue.svg)](https://pypi.org/project/matplotlib/3.9.2/)
[![numpy](https://img.shields.io/badge/numpy-2.2.5-blue.svg)](https://pypi.org/project/numpy/2.2.5/)
[![pandas](https://img.shields.io/badge/pandas-2.2.3-blue.svg)](https://pypi.org/project/pandas/2.2.3/)
[![Gurobi Version](https://img.shields.io/badge/Gurobi-12.0.1-blue.svg)](https://www.gurobi.com/)

This repository contains the codes and results of the manuscript titled: **"Can grid tariffs be fair and efficient? A comprehensive evaluation of tariff designs for smart electric vehicle integration"**.

The following repository is maintained by [Nico Brinkel](https://github.com/nicobrinkel) and Floris van Montfoort.

Highlights:

- Grid tariff reforms are needed incentivize efficient grid use and ensure a fair allocation of costs in the face of rising electrification and grid congestion.<br>
- This work aims to comprehensively evaluate grid tariff designs based on regulatory principles, specifically focusing on the impact on EV charging patterns.<br>
- Six grid tariff structures are evaluated based on four performance indicators, linked to regulatory principles.<br>
- No single tariff structure excels across all regulatory principles. Capacity-based tariff structures lead to highest system efficiency.

## File organization

The repository is organized as follows:

- 📁 [data](data/): Contains the data used in the paper. This folder contains the following data:
    - [Day ahead prices for the Netherlands (2022) [PKL]](data/day_ahead_market_prices_NL.pkl) 
    - [Sample of EV charging sessions for two charging stations [PKL]](data/charging_session_data_sample.pkl) 
    - [Household consumption profiles (simulated) for 650 households [PKL]](data/household_profiles.pkl) 
    - [Excel containing source data for all figures [XLSX]](<data/source data.xlsx>)

- 📁 [helperfunctions](helperfunctions/): Contains the required functions needed to run the [modelling_notebook](main.ipynb). This folder contains the following functions:
    - <img src="python_logo.png" alt="python logo" width="15" height="15"> [uncontrolled_charging_model.py](helperfunctions/uncontrolled_charging_model.py): Contains the functions to model EV charging profiles when considering uncontrolled charging.
    - <img src="python_logo.png" alt="python logo" width="15" height="15"> [volumetric_ToU_model.py](helperfunctions/volumetric_ToU_model.py): Contains the functions to optimize EV charging profiles under a volumetric ToU grid tariff structure.
    - <img src="python_logo.png" alt="python logo" width="15" height="15"> [segmented_volumetric_ToU_model.py](helperfunctions/segmented_volumetric_ToU_model.py): Contains the functions to optimize EV charging profiles under segmented volumetric ToU grid tariff structure.
    - <img src="python_logo.png" alt="python logo" width="15" height="15"> [capacity_prepartion_model.py](helperfunctions/capacity_prepartion_model.py): Contains the functions to perform the required preparatory steps to model EV charging profiles under a capacity grid tariff structure.
    - <img src="python_logo.png" alt="python logo" width="15" height="15"> [capacity_model.py](helperfunctions/capacity_model.py): Contains the functions to model EV charging profiles under a capacity grid tariff structure.
    - <img src="python_logo.png" alt="python logo" width="15" height="15"> [capacity_subscription_model.py](helperfunctions/capacity_subscription_model.py): Contains the functions to model EV charging profiles under a capacity-subscription grid tariff structure.
    

- <img src="Jupyter_logo.png" alt="python logo" width="15" height="15"> [main.ipynb](modelling_notebook.py): Contains the code to perform the model simulations conducted in the paper.
- <img src="Jupyter_logo.png" alt="python logo" width="15" height="15"> [main.ipynb](figure_notebook.py): Contains the code to create the figures of the paper from the provided source data.

- [requirements.txt](.requirements.txt): Contains the package versions used in Python for the conducted analysis.
- [.gitignore](.gitignore): Contains the files to be ignored by git.
- [LICENSE](LICENSE): Contains the license information.


## Installation

***Step 1:*** Clone the repository

```bash
git clone <repo-link>
```

***Step 2:*** Install the required packages
The code is tested on [![Python Version](https://img.shields.io/badge/Python-3.10.13-blue.svg)](https://www.python.org/downloads/release/python-3812/). The required packages are listed in the [requirements.txt](requirements.txt) file. To install the required packages, run the following command:

```bash
pip install -r requirements.txt
```

or

```bash
conda install --file requirements.txt
```

For the optimization solver, we used [![gurobipy](https://img.shields.io/badge/gurobipy-11.0.1-blue.svg)](https://www.gurobi.com/)
. You can install the Gurobi license by following the instructions in the [Gurobi Documentation](https://www.gurobi.com/documentation/10.0/quickstart_mac/installing_the_anaconda_py.html) for Mac and Linux and [Gurobi Documentation](https://www.gurobi.com/documentation/10.0/quickstart_windows/installing_the_anaconda_py.html) for Windows.

## Cite this work

If you re-use part of the code or some of the functions, please consider citing the repository:

```bibtex
@software{brinkel_vanmontfoort,
  author       = {Brinkel, Nico and
                  van Montfoort, Floris},
  title        = {{ROBUST-NL/paused\_ev\_charging: Publication ready 
                   code}},
  month        = apr,
  year         = 2024,
  publisher    = {Zenodo},
  version      = {v0.1.0},
  doi          = {10.5281/zenodo.10932796},
  url          = {https://doi.org/10.5281/zenodo.10932796}
}
```

## Funding

This study was supported by the Dutch Ministry of Economic Affairs and Climate Policy and the Dutch Ministry of the Interior and Kingdom Relations through the [ROBUST](https://tki-robust.nl/) project under grant agreement MOOI32014 and by the European Union’s Horizon Europe Research and Innovation program through the [SCALE](https://scale-horizon.eu/) project (Grant Agreement No. 101056874).

