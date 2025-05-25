# kiwiglider
NIWA's python library to process SLOCUM glider data, incorporating pre-existing packages PyGliders and GliderTools.

---

# Installation

You will need a C-compiler to use kiwiglider, since it relies on a package called dbdreader. See dbdreader installation suggestions for [Linux](https://github.com/smerckel/dbdreader?tab=readme-ov-file#installation-linux) and [Windows](https://github.com/smerckel/dbdreader?tab=readme-ov-file#installation-on-windows) for information about C-compilers (note that you do not need to install dbdreader itself at this stage)

We recommend creating a virtual environment.

1. `conda create -n kiwiglider`
1. `conda activate kiwiglider`

Installing kiwiglider in your environment needs to be done through git and pip, so also be sure that you have [Git](https://git-scm.com/downloads) installed on your machine. With Git installed, 

1. Clone kiwiglider to your local machine: `git clone https://github.com/adeverne/kiwiglider`
1. Change to parent directory of kiwiglider
1. Install kiwiglider with `pip install -e ./kiwiglider`

---

# Getting started

See [Jupyter notebook](https://github.com/adeverne/kiwiglider/tree/main/notebooks/Glider_BasicProcessing.ipynb)

---

# Requirements

- [pyglider](https://github.com/c-proof/pyglider)
- [GliderTools](https://github.com/GliderToolsCommunity/GliderTools/)
- [ioos_qc](https://github.com/ioos/ioos_qc)
- [openpyxl](https://github.com/theorchard/openpyxl)
- [palettable](https://github.com/jiffyclub/palettable)
- [compliance-checker](https://github.com/ioos/compliance-checker)
- [cc-plugin-glider](https://github.com/ioos/cc-plugin-glider)
- [pocean-core](https://github.com/pyoceans/pocean-core)
- [pygmt](https://github.com/GenericMappingTools/pygmt)
- [utm](https://github.com/Turbo87/utm)
- [distinctipy](https://github.com/alan-turing-institute/distinctipy)
- [colormap](https://github.com/mjziebarth/gmt-python-extensions/blob/master/gmt_extensions/colormap.py)
