#!/usr/bin/python3
# steps.py in kiwiglider
# This is the main postprocesing code for the kiwiglider package, with itemized
# steps that follow (in spirt) the workflow from the GEOMAR glider matlab
# package. It is assumed that project setup has already been run with functions
# from setup.py, namely copies of .*bd and cache files to the Raw/ directory.
# From here, we create an initial load of raw data (L0) to a netCDF using
# xarray and PyGlider's functionality.


def step_01(rootDir: str, verbose: bool = True, start_date: float = None,
            end_date: float = None) -> None:
    """
    function step01(procDir, verbose)
    Input:
        rootDir - Path to root processing directory
        verbose - Logical switch to print detailed status.
    Output:
    Description:
        Load raw data loaded from DBD and EBD files detected in step00. Saves
        data in xarray Dataset as L0 for faster loading later. Variables chosen
        to be loaded can be found in included "XXXXXX.txt"
    """
    # Import packages, including attempt of dbdreader...
    from glob import glob
    import os
    import sys
    import numpy as np
    import xarray as xr
    from . import setup
    try:
        import dbdreader
        from dbdreader import DbdError
        have_dbd = True
    except ImportError:
        print("Cannot import dbdreader, will use pyglider utilities instead.")
        have_dbd = False
        from pyglider import slocum

    # Run setup check
    rawDir, cacheDir = setup._setupcheck(rootDir)

    # Check for EBD/DBD and .CAC files in Raw and Raw/Cache (if they exist)...
    eList = sorted(glob(os.path.join(rawDir, "*.EBD")))
    dList = sorted(glob(os.path.join(rawDir, "*.DBD")))
    cList = sorted(glob(os.path.join(cacheDir, "*.CAC")))
    if eList:
        if verbose:
            print(f"Found {len(eList)} EBD files...")
        if dList:
            if verbose:
                print(f"Found {len(dList)} DBD files...")
            if cList:
                if verbose:
                    print(f"Found {len(cList)} CAC files...")
            else:
                raise Exception("Found EBD, DBD but no CAC files, " +
                                "make sure they are there or run " +
                                "step_00 again.")
        else:
            raise Exception("Found EBD but not DBD files, make " +
                            "sure they are there or run step_00 again.")
    else:
        raise Exception("Could not find EBD files, make sure " +
                        "they are there or run step_00 again.")

    # Get list of unique variables from EBD and DBD raw files...
    varList = []
    unitList = []
    if have_dbd:
        if verbose:
            print("Using DBDreader, creating MultiDBD object...")
        mDBD = dbdreader.MultiDBD(os.path.join(rawDir, "*[DE]BD"),
                                  cacheDir=cacheDir)
        varList = mDBD.parameterUnits.keys()
        unitList = mDBD.parameterUnits.values()
    else:
        if verbose:
            print("Cycling through files to get variables..." +
                  " may take a while.")
        for f in np.union1d(dList, eList):
            try:
                meta = slocum.dbd_get_meta(f, cachedir=cacheDir)
                for entry in meta[0]['activeSensorList']:
                    # If new, add to varList...
                    if entry['name'] not in varList:
                        varList.append(entry['name'])
                    if entry['unit'] not in unitList:
                        unitList.append(entry['unit'])
            except Exception:
                e = sys.exc_info()[0]
                print(f"Error: {e}")
                print(f"Cannot load metadata for file {f}")
                print("Moving on to next file...")

    # Now, load the raw timeseries data into xarray datasets and save as
    # netCDF files, one each for machine and science computers.
    if have_dbd:
        # Grab all the machine variables, first try to get timestamps
        if np.where([x == 'm_present_time' for x in varList])[0].size == 0:
            raise Exception("Did not find m_present_time in variable list...")
        else:
            _, mTimeStamps = mDBD.get('m_present_time')
            mTimeStamps = np.sort(mTimeStamps)
            nTimeStamps = len(mTimeStamps)
            if verbose:
                print(f"Loaded machine time, {nTimeStamps} observations...")
        # Now load the rest of the machine data
        machineList = ['m_lon', 'm_lat', 'm_gps_lon', 'm_gps_lat',
                       'm_gps_invalid_lon', 'm_gps_invalid_lat',
                       'm_gps_toofar_lon', 'm_gps_toofar_lat',
                       'm_gps_ignored_lon', 'm_gps_ignored_lat',
                       'm_depth', 'm_gps_utc_year', 'm_gps_utc_month',
                       'm_gps_utc_day', 'm_gps_utc_hour',
                       'm_gps_utc_minute', 'm_gps_utc_second',
                       'm_tot_num_inflections']
        machineUnits = ['degree_East', 'degree_North',
                        'degree_East', 'degree_North',
                        'degree_East', 'degree_North',
                        'degree_East', 'degree_North',
                        'm', 'year', 'month', 'day', 'hour',
                        'minute', 'second', '_']
        for mName in machineList:
            if np.where([x == mName for x in varList])[0].size > 0:
                if verbose:
                    print("Found variable {mName} in list, trying to load...")
                try:
                    varTime, varVal = mDBD.get(mName)
                except DbdError:
                    print("Could not load {mName}...")
                exec(f"{mName} = np.zeros((ntimeStamps,))*np.nan")
                timeIdx = np.squeeze(np.asarray([np.where(mTimeStamps == x)[0]
                                                for x in varTime]))
                exec(f"{mName}[timeIdx] = varVal")
                # Create Xarray DataArray from variable
                exec(f"{mName}_DA = xr.DataArray({mName}," +
                     "dims=['time'],coords=dict(time=mTimeStamps)," +
                     f"attrs=dict(long_name='{machineName}'," +
                     f"units='{machineUnits}',_FillValue='')")
            else:
                raise Exception("Did not find {mName} in found variables...")

        _,mTime = mDBD.get('m_present_time')
        nTimeStamps = len(mTime)
        m_lon = np.ones((nTimeStamps,))*np.nan
        m_lat = np.ones((nTimeStamps,))*np.nan
        m_gps_lon = np.ones((nTimeStamps,))*np.nan
        m_gps_lat = np.ones((nTimeStamps,))*np.nan
        m_gps_invalid_lon = np.ones((nTimeStamps,))*np.nan
        m_gps_invalid_lat = np.ones((nTimeStamps,))*np.nan
        m_gps_toofar_lon = np.ones((nTimeStamps,))*np.nan
        m_gps_toofar_lat = np.ones((nTimeStamps,))*np.nan
        m_gps_ignored_lon = np.ones((nTimeStamps,))*np.nan
        m_gps_ignored_lat = np.ones((nTimeStamps,))*np.nan

        # Load the dead-reckoned lon/lat
        mlonTime, mlon = mDBD.get("m_lon")
        mlatTime, mlat = mDBD.get("m_lat")
        print("Found m_lon, m_lat machine variables...")
    # Check for CTD variables sci_water_*
    # Check for "typical" extra science variables...


def step02telemetry(verbose: bool = True):
    """
    function telemetry(): -> None

    Input:
        verbose - Logical switch to print detailed status
    Output:


    Description:
        Function to do QC and merging of GPS lon/lat fixes with dead-reckoned lon/lat timeseries.
    """


def step03defineCast(verbose: bool = True):
    """
    function step03_defineCast(verbose): -> None

    Input:
        verbose - Logical switch
    Output:

    Description:
        Function to go through pressure timeseries and determine where casts begin/end.

    """

def step04salinityQC(verbose: bool = True):
    """
    function step04_"""
