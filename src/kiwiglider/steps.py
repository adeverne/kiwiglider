#!/usr/bin/env python3

import xarray as xr

def step00(procDir: str = ".", verbose: bool = True):
    """
    function step00(procDir, verbose)
    Input:
        procDir - Path to processing directory, which has sub-directories for
                  raw data and cache files.
        verbose - Logical switch to print detailed status
    Output:
        None
    Description:
        This function navigates to the provided procDir directory, then
        navigates through all sub-folders to search for DBD and EBD files, and
        CAC cache files. The results are saved in a dictionary that is then
        saved in procDir.
    """
    # Import needed packages
    import os
    from glob import glob
    # Navigate to procDir, get list of sub-directories to navigate...
    dirConts = sorted(glob(procDir))
    subDirs = []
    #[subDirs.append(x) if os]

def step01(procDir: str = ".", verbose: bool = True):
    """
    function step01(procDir, verbose)
    Input:
        procDir - Path to processing directory
        verbose - Logical switch to print detailed status.
    Output:
    Description:
        Load raw data loaded from DBD and EBD files detected in step00. Saves
        data in xarray Dataset as L0 for faster loading later.
    """

def step02telemetry(verbose: bool = True):
    """
    function telemetry(): -> None

    Input:
        verbose - Logical switch to print detailed status
    Output:


    Description:
    """


# if __name__ == "__main__":
