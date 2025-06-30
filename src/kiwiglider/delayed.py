#!/usr/bin/python3
# delayed.py in kiwiglider
# This is the main postprocesing code for the kiwiglider package, with itemized
# steps that follow (in spirit) the workflow from the GEOMAR glider matlab
# package. It is assumed that project setup has already been run with functions
# from setup.py, namely copies of .*bd and cache files to the Kiwi/Raw/
# directory. From here, we create an initial load of raw data (L0) to a netCDF
# using xarray and PyGlider's functionality.

import os
import sys
import numpy as np
import xarray as xr
from glob import glob
import logging
from . import setup

_log = logging.getLogger(__name__)

try:
    import dbdreader
    have_dbd = True
except ImportError:
    print("Cannot import dbdreader, will use pyglider utilities instead.")
    have_dbd = False
    from pyglider import slocum


def step_01(rootdir: str, start_date: float = None,
            end_date: float = None) -> None:
    """
    function step01(procDir, verbose)
        Function to load ebd/dbd data into a single xarray object, then save
        to netCDF file(s).

    Parameters
    rootdir     : str
        Path to root processing directory, which should contain Kiwi/
    start_date  : float
        POSIX time for the start of the deployment
    end_date    : float
        POSIX time for the end of the deployment

    """
    # Run setup check
    rawdir, cachedir = setup._setupcheck(rootdir)

    # Get list of ebd, dbd, and cac files (also check if they exist)
    elist = sorted(glob(os.path.join(rawdir, "*.ebd")))
    dlist = sorted(glob(os.path.join(rawdir, "*.dbd")))
    clist = []
    [clist.append(x) for x in
        set.union(set([x.split('/')[-1] for x in
                       glob(os.path.join(cachedir, "*.CAC"))]),
                  set([x.split('/')[-1] for x in
                       glob(os.path.join(cachedir, "*.cac"))]))]
    if elist:
        _log.info(f"Found {len(elist)} EBD files.")
        if dlist:
            _log.info(f"Found {len(dlist)} DBD files.")
            if clist:
                _log.info(f"Found {len(clist)} CAC files.")
                _log.info('Found EBD, DBD, and CAC files.')
            else:
                _log.info('Found EBD, DBD, but not CAC files.')
                raise Exception("Cannot find cache files.")
        else:
            _log.info('Found EBD but not DBD files.')
            raise Exception("Found EBE but not DBD files.")
    else:
        _log.info("Could not even find EBD files.")
        raise Exception("Could not find EBD files.")

    # Get list of unique variables from EBD and DBD raw files...
    vardict = {}
    if have_dbd:
        mDBD = dbdreader.MultiDBD(os.path.join(rawdir, "*[de]bd"),
                                  cacheDir=cachedir)
        vardict = mDBD.parameterUnits
    else:
        for f in np.union1d(dlist, elist):
            try:
                meta = slocum.dbd_get_meta(f, cachedir=cachedir)
                for entry in meta[0]['activeSensorList']:
                    # If new, add to varList...
                    if entry['name'] not in vardict.keys():
                        vardict[entry['name']] = entry['unit']
            except Exception:
                e = sys.exc_info()[0]
                print(f"Error: {e}")
                print(f"Cannot load metadata for file {f}")
                print("Moving on to next file...")

    # Files have two distinct timestamps, for DBD it's m_present_time
    # and for EBD it's
    # Now, load the raw timeseries data into xarray datasets and save as
    # netCDF files, one each for machine and science computers.
    if 'm_present_time' not in vardict.keys():
        raise Exception("Did not find m_present_time in variable list...")
    if 'sci_m_present_time' not in vardict.keys():
        raise Exception("Did not find sci_m_present_time in variable list...")

    machinelist = ['m_lon', 'm_lat', 'm_gps_lon', 'm_gps_lat',
                   'm_gps_invalid_lon', 'm_gps_invalid_lat',
                   'm_gps_toofar_lon', 'm_gps_toofar_lat',
                   'm_gps_ignored_lon', 'm_gps_ignored_lat',
                   'm_depth', 'm_gps_utc_year', 'm_gps_utc_month',
                   'm_gps_utc_day', 'm_gps_utc_hour', 'm_gps_utc_minute',
                   'm_gps_utc_second', 'm_tot_num_inflections', 'm_heading',
                   'm_pitch', 'm_roll', 'm_water_vx', 'm_water_vy']
    if have_dbd:
        # First grab m_present_time, then create empty variables for the rest
        # of the machine variables before filling them in...
        print("Reading in machine timestamps...")
        temtime, machinetime = mDBD.get('m_present_time')
        if np.nansum(temtime == machinetime) != len(temtime):
            raise Exception("dbdreader returned time and m_present_time" +
                            " do not match...")
        del temtime
        nTmach = len(machinetime)
        machinetime = np.sort(machinetime)
        for mvar in machinelist:
            if mvar not in vardict.keys():
                raise Exception(f"Did not find machine variable {mvar}...")
            print(f"Working on variable {mvar}...")
            mvartime, mvarvals = mDBD.get(mvar)
            ord = np.zeros((mvartime.shape), dtype=int)
            for ind, x in enumerate(mvartime):
                ord[ind] = np.where(machinetime == x)[0][0]
            exec(f"{mvar} = np.ones(({nTmach},))*np.nan")
            exec(f"{mvar}[ord] = mvarvals")
            del mvartime, mvarvals, ord
        # We've loaded all the machine variables, create Xarray and save to
        # intermediate netCDF file.
        datavardict = ','.join([f'{x}=(["time"],{x})' for x in machinelist])
        exec(f"datavar = dict({datavardict})")
        machinexr = xr.Dataset(data_vars=datavar,
                               coords=dict(time=machinetime),
                               attrs=dict(description="Intermediate file " +
                                          "storing machine variables.",
                                          timeunits="seconds since 1970-01-" +
                                          "01T00:00:00Z"))
        machinexr.to_netcdf(os.path.join(rootdir, "Kiwi", "temp_Machine.nc"))
    else:
        print("Reading dbd files using pyglider, will take some time.")
        nfiles = len(dlist)
        for ind, dfile in enumerate(dlist):
            temdat = slocum.dbd_to_dict(dfile, cachedir=cachedir)
            if ind == 0:
                machinetime = temdat[0]['m_present_time'][:]
                for mvar in machinelist:
                    if mvar not in vardict.keys():
                        raise Exception("Did not find machine " +
                                        f"variable {mvar}...")
                    exec(f"{mvar} = temdat[0]['{mvar}'][:]")
            else:
                machinetime = np.concatenate((machinetime,
                                              temdat[0]['m_present_time'][:]))
                for mvar in machinelist:
                    exec(f"{mvar} = np.concatenate(({mvar}, " +
                         f"temdat[0]['{mvar}'][:]))")
            print(f"Done with file #{ind+1:02d} out of {nfiles}...")
        # Sort arrays, then create xarray to save netCDF file...
        indsort = np.argsort(machinetime)
        machinetime = machinetime[indsort]
        for mvar in machinelist:
            exec(f"{mvar} = {mvar}[indsort]")
        datavardict = ','.join([f'{x}=(["time"],{x})' for x in machinelist])
        exec(f"datavar = dict({datavardict})")
        #datavar = exec(f"dict({datavardict})")
        machinexr = xr.Dataset(data_vars=datavar,
                               coords=dict(time=machinetime),
                               attrs=dict(description="Intermediate file " +
                                          "storing machine variables.",
                                          timeunits="seconds since 1970-01-" +
                                          "01Z00:00:00"))
        machinexr.to_netcdf(os.path.join(rootdir, "Kiwi", "temp_Science.nc"))

    # Science variables
    scivarnames = []
    externaldevice = False
    # Search for CTD variables...
    print("Searching for CTD variables...")
    # Pressure
    if 'sci_water_pressure' in vardict.keys():
        presname = 'sci_water_pressure'
    elif 'sci_rbrctd_pressure_00' in vardict.keys():
        presname = 'sci_rbrctd_pressure_00'
    scivarnames.append(presname)
    if 'sci_water_pressure2' in vardict.keys():
        backuppres = True
        pres2name = 'sci_water_pressure2'
        scivarnames.append(pres2name)
    else:
        backuppres = False
    # Temperature
    if 'sci_water_temp' in vardict.keys():
        tempname = 'sci_water_temp'
    elif 'sci_rbrctd_temperature_00' in vardict.keys():
        tempname = 'sci_rbrctd_temperature_00'
    scivarnames.append(tempname)
    if 'sci_water_temp2' in vardict.keys():
        backuptemp = True
        temp2name = 'sci_water_temp2'
        scivarnames.append(temp2name)
    else:
        backuptemp = False
    # Conductivity
    if 'sci_water_cond' in vardict.keys():
        condname = 'sci_water_cond'
    elif 'sci_rbrctd_conductivity' in vardict.keys():
        condname = 'sci_rbrctd_conductivity'
    scivarnames.append(condname)
    if 'sci_water_cond2' in vardict.keys():
        backupcond = True
        cond2name = 'sci_water_cond2'
        scivarnames.append(cond2name)
    else:
        backupcond = False

    print(f"Found P:{presname}, T:{tempname}, C:{condname}")
    if backuppres or backuptemp or backupcond:
        print("Also found secondary CTD sensor(s).")

    # Start looking for other sensors...
    # Attenuation
    if 'sci_bbam_beam_c' in vardict.keys():
        print("Found Wetlabs BAM beam attenuation meter...")
        attenname = 'sci_bbam_beam_c'
        scivarnames.append(attenname)
    # Backscatter (no wavelength information)
    numback = 0
    for vname in ['sci_bbfl2s_bb_scaled', 'sci_flbbrh_bb_units',
                  'sci_flbbcd_bb_units', 'sci_flbb_bb_units',
                  'sci_flbbbbV1_bb1_scaled', 'sci_flbbbbV1_bb2_scaled',
                  'sci_flbbbbV2_bb1_scaled', 'sci_flbbbbV2_bb2_scaled']:
        if vname in vardict.keys():
            print(f"Found backscatter (generic) variable: {vname}")
            numback += 1
            scivarnames.append(vname)
    # Backscatter 412
    if 'sci_bb2flsV4_b412_scaled' in vardict.keys():
        print("Found backscatter (412nm)")
        back412name = 'sci_bb2flsV4_b412_scaled'
        scivarnames.append(back412name)
    # Backscatter 470
    for vname in ['sci_bb2f_b470', 'sci_bb2flsV2_b470_scaled',
                  'sci_bb3slo_b470_scaled', 'sci_bb2fV2_b470_scaled',
                  'sci_bb2flsV4_b470_scaled', 'sci_bb2flsV8_b470_scaled']:
        if vname in vardict.keys():
            print("Found Backscatter(470nm)")
            back470name = vname
            scivarnames.append(back470name)
    # Backscatter 532
    for vname in ['sci_bb2c_beta532_eng_units', 'sci_bbfl2sV2_bb_scaled',
                  'sci_bb3slo_b532_scaled', 'sci_bb3sloV2_b532_scaled',
                  'sci_bb3sloV3_b532_scaled', 'sci_bb2flsV2_b532_scaled',
                  'sci_bb2flsV5_b532_scaled', 'sci_bb2flsV6_b532_scaled',
                  'sci_bb2flsV7_b532_scaled', 'sci_bb2flsV9_b532_scaled']:
        if vname in vardict.keys():
            print("Found backscatter (532nm)")
            back532name = vname
            scivarnames.append(back532name)
    # Backscatter 630
    if 'sci_bb3sloV3_b630_scaled' in vardict.keys():
        print("Found backscatter (632nm)")
        back630name = 'sci_bb3sloV3_b630_scaled'
        scivarnames.append(back630name)
    # Backscatter 650
    if 'sci_bb2flsV7_b650_scaled' in vardict.keys():
        print("Found backscatter (650nm)")
        back650name = 'sci_bb2flsV7_b650_scaled'
        scivarnames.append(back650name)
    # Backscatter 660
    for vname in ['sci_bb2c_beta660_eng_units', 'sci_bb3slo_b660_scaled',
                  'sci_bb3sloV2_b660_scaled', 'sci_bb2fls_b660_scaled',
                  'sci_bb2flsV5_b660_scaled']:
        if vname in vardict.keys():
            print("Found backscatter (660nm)")
            back660name = vname
            scivarnames.append(back660name)
    # Backscatter 700
    for vname in ['sci_bb2f_b700', 'sci_bb2fV2_b700_scaled',
                  'sci_bb2flsV8_b700_scaled', 'sci_bb2flsV9_b700_scaled']:
        if vname in vardict.keys():
            print("Found backscatter (700nm)")
            back700name = vname
            scivarnames.append(back700name)
    # Backscatter 715
    if 'sci_bb2flsV3_b715_scaled' in vardict.keys():
        print("Found backscatter (715nm)")
        back715name = 'sci_bb2flsV3_b715_scaled'
        scivarnames.append(back715name)
    # Backscatter 880
    for vname in ['sci_bb2lss_beta880_eng_units', 'sci_bb3sloV2_b880_scaled',
                  'sci_bb3sloV3_b880_scaled', 'sci_bb2fls_b880_scaled',
                  'sci_bb2flsV3_b880_scaled', 'sci_bb2flsV6_b880_scaled']:
        if vname in vardict.keys():
            print("Found backscatter (880nm)")
            back800name = vname
            scivarnames.append(back800name)
    # CDOM
    for vname in ['sci_bb2c_cdom', 'sci_bbfl2s_cdom_scaled',
                  'sci_bbfl2sV2_fl2_scaled', 'sci_fl3slo_cdom_units',
                  'sci_fl3sloV2_cdom_units', 'sci_bb2fls_cdom_scaled',
                  'sci_bb2flsV5_cdom_scaled', 'sci_bb2flsV6_cdom_scaled',
                  'sci_flbbcd_cdom_units', 'sci_fl2PeCdom_cdom_units']:
        if vname in vardict.keys():
            print("Found CDOM")
            cdomname = vname
            scivarnames.append(cdomname)
    # Chl-a
    for vname in ['sci_bb2f_fluor', 'sci_bbfl2s_chlor_scaled',
                  'sci_fl3slo_chlor_units', 'sci_flntu_chlor_units',
                  'sci_fl3sloV2_chlor_units', 'sci_bb2flsV2_chl_scaled',
                  'sci_bb2fV2_chlor_scaled', 'sci_bb2flsV4_chl_scaled',
                  'sci_flbbrh_chlor_units', 'sci_bb2flsV7_chl_scaled',
                  'sci_flbbcd_chlor_units', 'sci_flbb_chlor_units',
                  'sci_bb2flsV8_chl_scaled', 'sci_bb2flsV9_chl_scaled',
                  'sci_flbbbbV1_fl_scaled', 'sci_flbbbbV2_fl_scaled']:
        if vname in vardict.keys():
            print("Found chl-a")
            chlname = vname
            scivarnames.append(chlname)
    # CO2
    if 'sci_miniProCO2_correctedCO2' in vardict.keys():
        print("Found CO2 sensor.")
        co2name = 'sci_miniProCO2_correctedCO2'
        scivarnames.append(co2name)
    # LISST
    if 'sci_lisst_is_installed' in vardict.keys():
        print("Found LISST installed variable...")
        print("If a LISST is installed, load data separately...")
        externaldevice = True
    # methane
    if 'sci_lm_methane' in vardict.keys():
        print("Found methane sensor")
        methname = 'sci_lm_methane'
        scivarnames.append(methname)
    # MicroRider (ROCKLAND turbulence sensor)
    if 'sci_microrider_is_installed' in vardict.keys():
        print("Found Microrider installed variable...")
        print("If a Microrider is installed, load data separately...")
        print("Glider flight model will be calculated.")
        externaldevice = True
    # Nitrate
    if 'sci_suna_nitrate_concentration' in vardict.keys():
        print("Found SUNA nitrate sensor")
        nitratename = 'sci_suna_nitrate_concentration'
        scivarnames.append(nitratename)
    # Oxygen
    for vname in ['sci_oxy3835_oxygen', 'sci_oxy3835_wphase_oxygen',
                  'sci_oxy4_oxygen', 'sci_rinkoII_DO']:
        if vname in vardict.keys():
            print("Found oxygen")
            oxyname = vname
            scivarnames.append(oxyname)
    # PAR
    for vname in ['sci_whpar_par', 'sci_satpar_par', 'sci_bsipar_par']:
        if vname in vardict.keys():
            print("Found PAR")
            parname = vname
            scivarnames.append(parname)
    # PCO2
    if 'sci_pCO2_pCO2' in vardict.keys():
        print("Found pCO2")
        pco2name = 'sci_pCO2_pCO2'
        scivarnames.append(pco2name)
    # pH
    if 'sci_sbe41n_ph_electrode_voltage' in vardict.keys():
        print("Found pH")
        phname = 'sci_sbe41n_ph_electrode_voltage'
        scivarnames.append(phname)
    # Phycoerythrin
    for vname in ['sci_bbfl2sV2_fl1_scaled', 'sci_fl3slo_phyco_units',
                  'sci_bb2flsV3_pe_scaled', 'sci_fl2PeCdom_pe_units']:
        if vname in vardict.keys():
            print("Found Phycoerythrin")
            phyconame = vname
            scivarnames.append(phyconame)
    # Turbidity
    if 'sci_flntu_turb_units' in vardict.keys():
        print("Found turbidity")
        turbname = 'sci_flntu_turb_units'
        scivarnames.append(turbname)

    print("Done searching for science variables.")
    if externaldevice:
        print("Found external device (e.g. microrider, lisst), make sure " +
              "to download data separately from the device.")
    print("Will load the following science variables...")
    for ind, name in enumerate(scivarnames):
        print(f"{ind:03d}: {name}, raw unit: {vardict[name]}")

    if have_dbd:
        # grab sci_m_present_time, then create empty variables for rest of
        # science variables before filling them...
        temtime, sciencetime = mDBD.get('sci_m_present_time')
        if np.nansum(temtime == sciencetime) != len(temtime):
            raise Exception("dbdreader returned time and sci_m_present time" +
                            " do not match...")
        del temtime
        nTmach = len(sciencetime)
        sciencetime = np.sort(sciencetime)
        for svar in scivarnames:
            if svar not in vardict.keys():
                raise Exception(f"Did not find science variabes {svar}...")
            print(f"Working on variable {svar}...")
            svartime, svarvals = mDBD.get(svar)
            ord = np.zeros((svartime.shape), dtype=int)
            for ind, x in enumerate(svartime):
                ord[ind] = np.where(sciencetime == x)[0][0]
            exec(f"{svar} = np.ones(({nTmach},))*np.nan")
            exec(f"{svar}[ord] = svarvals")
            del svartime, svarvals, ord
        # Loaded all science variables, create Xarray and save to intermediate
        # netCDF file...
        datavardict = ','.join([f'{x}=(["time"],{x})' for x in scivarnames])
        exec(f"datavar = dict({datavardict})")
        sciencexr = xr.Dataset(data_vars=datavar,
                               coords=dict(time=sciencetime),
                               attrs=dict(description="Intermediate file " +
                                          "storing machine variables.",
                                          timeunits="seconds since 1970-01-" +
                                          "01T00:00:00Z"))
        sciencexr.to_netcdf(os.path.join(rootdir, "Kiwi", "temp_Science.nc"))
    else:
        print("Reading ebd files using pyglider, will take some time.")
        nfiles = len(elist)
        for ind, efile in enumerate(elist):
            temdat = slocum.dbd_to_dict(efile, cachedir=cachedir)
            if ind == 0:
                sciencetime = temdat[0]['sci_m_present_time'][:]
                for svar in scivarnames:
                    if svar not in vardict.keys():
                        raise Exception("Did not find machine " +
                                        f"variable {svar}...")
                    exec(f"{svar} = temdat[0]['{svar}'][:]")
            else:
                sciencetime = np.concatenate((sciencetime,
                                              temdat[0]['sci_m_present_time'][:]))
                for svar in scivarnames:
                    exec(f"{svar} = np.concatenate(({svar}, " +
                         f"temdat[0]['{svar}'][:]))")
            print(f"Done with file #{ind+1:02d} out of {nfiles}...")
        # Sort arrays, then create xarray to save netCDF file...
        indsort = np.argsort(sciencetime)
        sciencetime = sciencetime[indsort]
        for svar in scivarnames:
            exec(f"{svar} = {svar}[indsort]")
        datavardict = ','.join([f'{x}=(["time"],{x})' for x in scivarnames])
        exec(f"datavar = dict({datavardict})")
        machinexr = xr.Dataset(data_vars=datavar,
                               coords=dict(time=sciencetime),
                               attrs=dict(description="Intermediate file " +
                                          "storing machine variables.",
                                          timeunits="seconds since 1970-01-" +
                                          "01Z00:00:00"))
        machinexr.to_netcdf(os.path.join(rootdir, "Kiwi", "temp_Science.nc"))


def step02telemetry(verbose: bool = True):
    """
    function telemetry(): -> None

    Input:
        verbose - Logical switch to print detailed status
    Output:


    Description:
        Function to do QC and merging of GPS lon/lat fixes with dead-reckoned
        lon/lat timeseries.
    """


def step03defineCast(verbose: bool = True):
    """
    function step03_defineCast(verbose): -> None

    Input:
        verbose - Logical switch
    Output:

    Description:
        Function to go through pressure timeseries and determine where casts
        begin/end.

    """


def step04salinityQC(verbose: bool = True):
    """
    function step04_"""
