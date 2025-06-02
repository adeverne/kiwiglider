![image](kiwiglider_logo.png)

# kiwiglider
A Python package to process Teledyne Webb Research SLOCUM glider data, incorporating pre-existing packages PyGliders and GliderTools.

---

## General Description
Gliders are autonomous sampling platforms that have become popular in the oceanographic research community over the past two decades. Teledyne Webb Research's Slocum gliders are among the most popular. Here the goal is to provide code to facilitate two main uses cases:
1. Near real time processing of data being sent via satellite during a glider deployment, including IOOS-recommended quality control checks, for submission to data assembly centers
2. Delayed time processing of scientific data to publication quality status, including routines to perform well-established corrections for known instrument.

## Installation

You will need a C-compiler to use kiwiglider, since it relies on a package called dbdreader. See dbdreader installation suggestions for [Linux](https://github.com/smerckel/dbdreader?tab=readme-ov-file#installation-linux) and [Windows](https://github.com/smerckel/dbdreader?tab=readme-ov-file#installation-on-windows) for information about C-compilers (note that you do not need to install dbdreader itself at this stage)

We recommend creating a virtual environment.

1. `conda create -n kiwiglider`
1. `conda activate kiwiglider`

As of 26 May 2025, one dependency fails under pip but works with conda. As such, also do `conda install compliance-checker cc-plugin-glider`

From your new virtual environment, you can now install kiwiglider. The easiest method is with `pip install kiwiglider@git+https://github.com/adeverne/kiwiglider`

Another method of installation is through git and pip. This will allow you to edit kiwiglider in a local repository. After you have [Git](https://git-scm.com/downloads) installed on your machine: 

1. Clone kiwiglider to your local machine: `git clone https://github.com/adeverne/kiwiglider`
1. Change to parent directory of kiwiglider
1. Install kiwiglider with `pip install -e ./kiwiglider`

For the moment we are not listed on PyPi due to ongoing testing, but if you wish to install from TestPyPi please do the following:

`pip install --index-url https://test.pypi.org/simple --extra-index-url https:/pypi.org/simple/ kiwiglider`

---

# Getting started

For the June 2025 Hack-a-thon:
[Hackathon Summary Page Notebook](https://github.com/adeverne/kiwiglider/blob/main/notebooks/Hackathon_summaries.ipynb)

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
