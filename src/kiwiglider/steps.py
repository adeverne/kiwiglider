#!/usr/bin/env python3
# steps.py in kiwiglider
# This is the main code for the package, with itemized steps that follow (in
# spirit) the workflow from the GEOMAR glider package.


def step_00(rootDir: str, verbose: bool = True) -> None:
    """
    function step_00(rootDir, verbose)
    Input:
        rootDir - Path to root processing directory
        verbose - Logical switch to print detailed status
    Output:
        None
    Description:
        This function navigates through all sub-directories in rootDir,
        identifying where there are EBD/DBD and CAC files. Aftewards, a copy
        is made to a "Raw" directory at the rootDir level.
    """
    # Import needed packages
    import os
    from glob import glob
    import shutil
    from datetime import datetime, UTC

    # Test to see if rootDir exists and is not just "."
    if os.path.exists(rootDir) & (rootDir != "."):
        print(f"Path {rootDir} passes initial test...")
    else:
        raise ValueError("This path either does not exist, or it is '.'," +
                         " which cannot be used. Please write full path.")

    # Check to see if Raw directory already exists
    if verbose:
        print("Initiated Step 00 of Kiwiglider at " +
              datetime.strftime(datetime.now(tz=UTC),
                                "%Y-%m-%d %H:%M:%S"))
    if os.path.exists(os.path.join(rootDir, "Raw")):
        if verbose:
            print("Raw directory already exists...")
        if os.path.exists(os.path.join(rootDir, "Raw", "Cache")):
            if verbose:
                print("Raw AND Cache directories exist.")
        else:
            if verbose:
                print("Creating Cache directory")
            os.makedirs(os.path.join(rootDir, "Raw", "Cache"))
    else:
        if verbose:
            print("Making Raw directory for dbd/ebd and cache files.")
        os.makedirs(os.path.join(rootDir, "Raw"))
        os.makedirs(os.path.join(rootDir, "Raw", "Cache"))

    # Walk through rootDir, search for where EBD, DBD, CAC files are stored...
    dbdDirs = []
    nDBD = 0
    ebdDirs = []
    nEBD = 0
    cacDirs = []
    nCAC = 0
    if verbose:
        print(f"About to start navigating through {rootDir} ...")
    for root, _, files in os.walk(rootDir):
        # Skip the Raw directory...
        if ((root != os.path.join(rootDir, "Raw")) &
           (root != os.path.join(rootDir, "Raw", "Cache"))):
            for filename in files:
                # Check to see if ebd...
                if os.path.splitext(filename)[1] in [".EBD", ".ebd"]:
                    nEBD += 1
                    if root not in ebdDirs:
                        ebdDirs.append(root)
                # Check to see if dbd...
                if os.path.splitext(filename)[1] in [".DBD", ".dbd"]:
                    nDBD += 1
                    if root not in dbdDirs:
                        dbdDirs.append(root)
                # Check for CAC cache files...
                if os.path.splitext(filename)[1] in [".CAC", ".cac"]:
                    nCAC += 1
                    if root not in cacDirs:
                        cacDirs.append(root)
    if verbose:
        print(f"Done navigating {rootDir}")
        print(f"Found {len(ebdDirs):02d} directories with a " +
              f"total of {nEBD} ebd files ...")
        [print(f"{x}") for x in ebdDirs]
        print(f"Found {len(dbdDirs):02d} directories with a " +
              f"total of {nDBD} dbd files ...")
        [print(f"{x}") for x in dbdDirs]
        print(f"Found {len(cacDirs):02d} directories with a " +
              f"total of {nCAC} cac files:")
        [print(f"{x}") for x in cacDirs]

    # For simplicity, but also because dbdreader uses glob to list all the
    # DBD/EBD files, re-locate all DBD/EBD files to single "raw" directory
    # with CAC files in sub-directory Cache/, and make extensions upper-case
    # Check to see if copies already exist....
    e1 = glob(os.path.join(rootDir, "Raw", "*.EBD"))
    e1name = [x.split('/')[-1] for x in e1]
    e2 = glob(os.path.join(rootDir, "Raw", "*.ebd"))
    e2name = [x.split('/')[-1] for x in e2]

    if len(e1) + len(e2) != nEBD:
        if verbose:
            print(f"Found {len(e1) + len(e2)} ebd files in Raw, but " +
                  f"detected {nEBD} files in total... will copy new files.")
        for edir in ebdDirs:
            for root, _, files in os.walk(edir):
                for filename in files:
                    if os.path.splitext(filename)[1] in [".EBD", ".ebd"]:
                        if (filename not in e1name) & (filename not in e2name):
                            shutil.copyfile(os.path.join(root, filename),
                                            os.path.join(rootDir, "Raw",
                                                         filename))
    d1 = glob(os.path.join(rootDir, "Raw", "*.DBD"))
    d1name = [x.split('/')[-1] for x in d1]
    d2 = glob(os.path.join(rootDir, "Raw", "*.dbd"))
    d2name = [x.split('/')[-1] for x in d2]
    if len(d1)+len(d2) != nDBD:
        if verbose:
            print(f"Found {len(d1) + len(d2)} dbd files in Raw, but " +
                  f"detected {nDBD} files in total... will copy new files.")
        for ddir in dbdDirs:
            for root, _, files in os.walk(ddir):
                for filename in files:
                    if os.path.splitext(filename)[1] in [".DBD", ".dbd"]:
                        if (filename not in d1name) & (filename not in d2name):
                            shutil.copyfile(os.path.join(root, filename),
                                            os.path.join(rootDir, "Raw",
                                                         filename))
    c1 = glob(os.path.join(rootDir, "Raw", "Cache", "*.CAC"))
    c1name = [x.split('/')[-1] for x in c1]
    c2 = glob(os.path.join(rootDir, "Raw", "Cache", "*.cac"))
    c2name = [x.split('/')[-1] for x in c2]
    if len(c1)+len(c2) != nCAC:
        if verbose:
            print(f"Found {len(c1) + len(c2)} cache files in Raw, but " +
                  f"detected {nCAC} files in total... will copy new files.")
        for cdir in cacDirs:
            for root, _, files in os.walk(cdir):
                for filename in files:
                    if os.path.splitext(filename)[1] in [".CAC", ".cac"]:
                        if (filename not in c1name) & (filename not in c2name):
                            shutil.copyfile(os.path.join(root, filename),
                                            os.path.join(rootDir, "Raw",
                                                         "Cache", filename))
    # Rename ebd/dbd/cac files to have uppercase extensions...
    for root, _, files in os.walk(os.path.join(root, "Raw")):
        for filename in files:
            path, ext = os.path.splitext(filename)
            if ext in ["ebd", "dbd", "cac"]:
                shutil.copyfile(os.path.join(root, filename),
                                os.path.join(root, path, ext.upper()))
    if verbose:
        print("Raw directory exists, and any new EBD/DBD/cache files have" +
              "been copied and have upper-case extension names.")


def setupcheck(rootDir: str, verbose: bool = True) -> tuple:
    """
    function setupcheck(rootDir, verbose)

    Input:
        rootDir - Path to root processing directory
        verbose - Logical switch to print detailed status.

    Output:

    Description:
        Function invoked at beginning of steps to double-check that the
        user-provided directory is a good root directory for processing
        as defined in kiwiglider. Returns tuple with raw and cache paths.
    """
    import os
    if not os.path.exists(os.path.join(rootDir, "Raw")):
        raise Exception(f"Now Raw directory in {rootDir}, either " +
                        "directory or run step_00 first.")
    else:
        rawDir = os.path.join(rootDir, "Raw")
    if not os.path.exists(os.path.join(rawDir, "Cache")):
        raise Exception("Raw directory found, but not Cache. " +
                        "Please re-run step_00")
    else:
        cacheDir = os.path.join(rawDir, "Cache")
    return (rawDir, cacheDir)


def step_01(rootDir: str, verbose: bool = True) -> None:
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
    try:
        import dbdreader
        from dbdreader import DbdError
        have_dbd = True
    except ImportError:
        print("Cannot import dbdreader, will use pyglider utilities instead.")
        have_dbd = False
        from pyglider import slocum

    # Run setup check
    rawDir, cacheDir = setupcheck(rootDir)

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
