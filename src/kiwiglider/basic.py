"""Classes to process Slocum glider files the (basic) Kiwi way"""
from os.path import join as join_path
from os.path import basename, exists
from os import makedirs, listdir
import re
from itertools import groupby
import yaml
import logging
from typing import Any
from pyglider import slocum
from pyglider.ncprocess import extract_timeseries_profiles
from ioos_qc.config import Config
from ioos_qc.streams import XarrayStream
from ioos_qc.results import collect_results, ContextResult, CallResult
from ioos_qc.qartod import aggregate
from ioos_qc.stores import PandasStore, column_from_collected_result
from compliance_checker.runner import ComplianceChecker, CheckSuite
import xarray as xr
import numpy as np
from inspect import getmodule
from kiwiglider.utils import collect_excelsheet_metadata


_log = logging.getLogger(__name__)


class DeploymentYAML():
    """Contains deployment-specific metadata.

    Parameters
    ----------
    ID : int, default = 1
        Deployment number/ID to focus on
    style : str, default = 'Realtime'
        Deployment processing type, either 'Realtime' or 'Delayed'

    Attributes
    ----------
    ID : int
        Deployment number/ID to focus on
    style : str
        Deployment processing type
    excelsheet : str
        Path to Excel sheet with metadata
    excel_metadata : dict[str, list[str | int | float]]
        Excel sheet metadata from specified deployment
    metadata : dict
        Global deployment metadata
    glider_devices : dict
        Installed instrument metadata
    netcdf_variables : dict
        NetCDF variable name mapping and metadata
    profile_variables : dict
        Profile-averaged variable metadata
    qartod_tests : dict
        QARTOD test parameters
    yaml : dict
        All metadata to go in YAML file
    outname : str
        Path to output YAML file

    """

    def __init__(self, ID: int = 1, style: str = 'Realtime'):
        self.ID = ID
        self.style = style

    def add_excel_metadata(self, excelsheet: str) -> None:
        """Add Excel sheet metadata for given deployment ID.

        Note
        ----
        First row of Excel sheet must contain descriptive column headers.
        First column of Excel sheet must contain deployment ID numbers.

        Parameters
        ----------
        excelsheet : str
            Path to Excel sheet with metadata

        """

        # assign input Excel sheet
        self.excelsheet = excelsheet

        # get metadata from input deployment ID
        self.excel_metadata = collect_excelsheet_metadata(
            self.excelsheet, self.ID
        )

    def add_metadata(self, metadata: dict[str, Any] = None) -> None:
        """Add global deployment metadata.

        Parameters
        ----------
        metadata : dict[str, Any], optional
            Global attributes to overwrite default
            in form {'attribute':value}

        """
        _log.info('Adding global metadata to deployment YAML')

        # make sure already have Excel sheet metadata
        self._check_for_excel_meta()

        # initialize with static metadata
        self.metadata = {
            'Conventions': 'CF-1.11',
            'Metadata_Conventions': 'CF-1.11, Unidata Dataset Discovery v1.0',
            'contributor_role_vocabulary': 'http://vocab.nerc.ac.uk' +
            '/search_nvs/W08/',
            'comment': '" "',
            'creator_url': '" "',
            'format_version': 'IOOS_Glider_NetCDF_v2.0.nc',
            'keywords':
                'Water-based Platforms > Uncrewed Vehicles > Subsurface > ' +
                'Seaglider, Oceans > Marine Sediments > Turbidity, ' +
                'Oceans > Ocean Chemistry > Oxygen, ' +
                'Oceans > Ocean Circulation > Turbulence, ' +
                'Oceans > Ocean Pressure > Water Pressure, ' +
                'Oceans > Ocean Temperature > Water Temperature, ' +
                'Oceans > Salinity/Density > Conductivity, ' +
                'Oceans > Salinity/Density > Density, ' +
                'Oceans > Salinity/Density > Salinity',
            'keywords_vocabulary': 'GCMD Science Keywords',
            'license': 'This data may be redistributed and used without ' +
            'restriction',
            'metadata_link': '" "',
            'processing_level': 'Data are provided as-is',
            'publisher_url': '" "',
            'references': '" "',
            'source': 'Observational data from a profiling glider',
            'standard_name_vocabulary': 'Standard Name Table (v85, 21 May ' +
            '2024)',
            'summary': 'This dataset contains physical oceanographic ' +
            'measurements of temperature, conductivity, salinity, density ' +
            'and estimates of depth-average currents.',
        }

        # add from Excel sheet
        acknowledge = ('This work supported by funding from ' +
                       self.excel_metadata['funding'])
        self._add_meta('acknowledgement', acknowledge)
        pi = self.excel_metadata['principal_investigator']
        dm = self.excel_metadata['data_manager']
        pilot = self.excel_metadata['pilot']
        contributor_name = ','.join([pi, dm, pilot])
        self._add_meta('contributor_name', contributor_name)
        contributor_role = ','.join(
            ['Principal Investigator']*int(pi.count(',')+1) +
            ['Data Manager']*int(dm.count(',')+1) +
            ['Operator']*int(pilot.count(',')+1)
        )
        self._add_meta('contributor_role', contributor_role)
        self._add_meta('creator_email',
                       self.excel_metadata['data_manager_email'])
        self._add_meta('creator_name', self.excel_metadata['data_manager'])
        self._add_meta('deployment_name', 'GLD{:04d}'.format(self.ID))
        self._add_meta('deployment_start',
                       self.excel_metadata['deploy_date'].strftime('%Y-%m-%d'))
        # note: will be overwritten in nc by pyglider
        self._add_meta('deployment_end',
                       self.excel_metadata['end_date'].strftime('%Y-%m-%d'))
        # note: will be overwritten in nc by pyglider
        self._add_meta('glider_name', self.excel_metadata['platform_id'])
        self._add_meta('glider_serial',
                       f'{self.excel_metadata['platform_sn']}')
        self._add_meta('glider_model', self.excel_metadata['glidertype'])
        self._add_meta('glider_pump', f'{self.excel_metadata['pump_type']}m')
        self._add_meta('institution', self.excel_metadata['owner'])
        backwards_email = self.excel_metadata['data_manager_email']
        backwards_email = backwards_email.split('@')[-1]
        backwards_email = backwards_email.split('.')[-1::-1]
        backwards_email = '.'.join(backwards_email)
        self._add_meta('naming_authority', backwards_email)
        self._add_meta('platform_type', self.excel_metadata['platform_type'])
        self._add_meta('project', self.excel_metadata['project_name'])
        self._add_meta('publisher_email',
                       self.excel_metadata['data_manager_email'])
        self._add_meta('publisher_name', self.excel_metadata['data_manager'])
        self._add_meta('sea_name', self.excel_metadata['sea'])
        self._add_meta('wmo_id', f'{self.excel_metadata['wmo_id']}')

        # add from user input (overwrite above as necessary)
        if metadata is not None:
            for name, value in metadata.items():
                self._add_meta(name, value)

    def add_glider_devices(
            self,
            glider_devices: dict[str, dict[str, Any]] = None
    ) -> None:
        """Add installed instrument metadata.

        Parameters
        ----------
        glider_devices : dict[str, dict[str, Any]], optional
            Glider device metadata to overwrite default
            in form {'device_name': {'attribute': value}}

        """
        _log.info('Adding glider device metadata to deployment YAML')

        # make sure already have Excel sheet metadata
        self._check_for_excel_meta()

        # initialize common instruments
        self.glider_devices = {
            'pressure': {
                'make': 'Micron',
                'model': 'Pressure',
                'serial': f'{self.excel_metadata['pres_sn']}'
            },
            'ctd': {
                'make': self.excel_metadata['ctd_make'],
                'model': self.excel_metadata['ctd_type'],
                'serial': f'{self.excel_metadata['ctd_sn']}',
                'long_name': 'Seabird SlocumCTD',
                'make_model': self.excel_metadata['ctd_make'] + ' ' 
                + self.excel_metadata['ctd_type'],
                'factory_calibrated': '" "',
                'calibration_date':
                self.excel_metadata['ctd_cal'].strftime('%Y-%m-%d'),
                'calibration_report': '" "',
                'comment': '" "'
            }
        }

        # add based on devices present in Excel worksheet metadata
        if self.excel_metadata['puck_installed']:
            self._add_glider_device('optics', {
                'make': self.excel_metadata['puck_make'],
                'model': self.excel_metadata['puck_type'],
                'serial': f'{self.excel_metadata['puck_sn']}',
                'factory_calibrated':
                self.excel_metadata['puck_cal'].strftime('%Y-%m-%d'),
                'calibration_date':
                self.excel_metadata['puck_cal'].strftime('%Y-%m-%d'),
                'calibration_report': '" "',
                'comment': '" "'
            })
        if self.excel_metadata['oxy_installed']:
            self._add_glider_device('oxygen', {
                'make': self.excel_metadata['oxy_make'],
                'model': self.excel_metadata['oxy_type'],
                'serial': f'{self.excel_metadata['oxy_sn']}',
                'factory_calibrated':
                self.excel_metadata['oxy_cal'].strftime('%Y-%m-%d'),
                'calibration_date':
                self.excel_metadata['oxy_cal'].strftime('%Y-%m-%d'),
                'calibration_report': '" "',
                'comment': '" "'
            })
        if self.excel_metadata['par_installed']:
            self._add_glider_device('par', {
                'make': self.excel_metadata['par_make'],
                'model': self.excel_metadata['par_type'],
                'serial': f'{self.excel_metadata['par_sn']}',
                'factory_calibrated':
                self.excel_metadata['par_cal'].strftime('%Y-%m-%d'),
                'calibration_date':
                self.excel_metadata['par_cal'].strftime('%Y-%m-%d'),
                'calibration_report': '" "',
                'comment': '" "'
            })
        if self.excel_metadata['bb3_installed']:
            self._add_glider_device('optics2', {
                'make': self.excel_metadata['bb3_make'],
                'model': self.excel_metadata['bb3_type'],
                'serial': f"{self.excel_metadata['bb3_sn']}",
                'factory_calibrated':
                self.excel_metadata['bb3_cal'].strftime('%Y-%m-%d'),
                'calibration_date':
                self.excel_metadata['bb3_cal'].strftime('%Y-%m-%d'),
                'calibration_report': '" "',
                'comment': '" "'
            })
        if self.excel_metadata['lisst_installed']:
            self._add_glider_device('lisst', {
                'make': self.excel_metadata['lisst_make'],
                'model': self.excel_metadata['lisst_type'],
                'serial': f"{self.excel_metadata['lisst_sn']}",
                'factory_calibrated':
                self.excel_metadata['lisst_cal'].strftime('%Y-%m-%d'),
                'calibration_date':
                self.excel_metadata['lisst_cal'].strftime('%Y-%m-%d'),
                'calibration_report': '" "',
                'comment': '" "'
            })
        if self.excel_metadata['microrider_installed']:
            self._add_glider_device('microrider', {
                'make': self.excel_metadata['microrider_make'],
                'model': self.excel_metadata['microrider_type'],
                'serial': f"{self.excel_metadata['microrider_sn']}",
                'factory_calibrated':
                self.excel_metadata['microrider_cal'].strftime('%Y-%m-%d'),
                'calibration_date':
                self.excel_metadata['microrider_cal'].strftime('%Y-%m-%d'),
                'calibration_report': '" "',
                'comment': '" "'
            })

        # add from user input (overwrite as necessary)
        if glider_devices is not None:
            for name, value in glider_devices.items():
                self._add_glider_device(name, value)

    def add_netcdf_variables(
            self,
            netcdf_variables: dict[str, dict[str, Any]] = None
    ) -> None:
        """Add NetCDF variable translations and metadata.

        Parameters
        ----------
        netcdf_variables : dict[str, dict[str, Any]], optional
            NetCDF variable name mapping and metadata to overwrite default
            in form {'variable_name': {'attribute': value}

        """
        _log.info('Adding variable metadata to deployment YAML')

        # make sure already have Excel sheet metadata
        self._check_for_excel_meta()

        # initialize common variables
        self.netcdf_variables = {
            'time': {
                'source': 'sci_m_present_time',
                'long_name': 'Time',
                'standard_name': 'time',
                'calendar': 'gregorian',
                'units': 'seconds since 1970-01-01T00:00:00Z',
                'observation_type': 'measured'
            },
            'latitude': {
                'source': 'm_gps_lat',
                'long_name': 'Latitude',
                'standard_name': 'latitude',
                'units': 'degrees_north',
                'comment': 'Estimated between surface fixes',
                'observation_type': 'measured',
                'platform': 'platform',
                'reference': 'WGS84',
                'valid_max': 90.0,
                'valid_min': -90.0,
                '_FillValue': -999.0,
                'coordinate_reference_frame': 'urn:ogc:crs:EPSG::4326'
            },
            'longitude': {
                'source': 'm_gps_lon',
                'long_name': 'Longitude',
                'standard_name': 'longitude',
                'units': 'degrees_east',
                'comment': 'Estimated between surface fixes',
                'observation_type': 'measured',
                'platform': 'platform',
                'reference': 'WGS84',
                'valid_max': 180.0,
                'valid_min': -180.0,
                '_FillValue': -999.0,
                'coordinate_reference_frame': 'urn:ogc:crs:EPSG::4326'
            },
            'heading': {
                'source': 'm_heading',
                'long_name': 'Glider Heading Angle',
                'standard_name': 'platform_orientation',
                'units': 'rad',
                '_FillValue': -999.0
            },
            'pitch': {
                'source': 'm_pitch',
                'long_name': 'Glider Pitch Angle',
                'standard_name': 'platform_pitch_angle',
                'units': 'rad',
                '_FillValue': -999.0
            },
            'roll': {
                'source': 'm_roll',
                'long_name': 'Glider Roll Angle',
                'standard_name': 'platform_roll_angle',
                'units': 'rad',
                '_FillValue': -999.0
            },
            'conductivity': {
                'source': 'sci_water_cond',
                'long_name': 'Conductivity',
                'standard_name': 'sea_water_electrical_conductivity',
                'units': 'S m-1',
                'instrument': 'instrument_ctd',
                'valid_min': self.excel_metadata['ctd_c_minimum'],
                'valid_max': self.excel_metadata['ctd_c_maximum'],
                '_FillValue': -999.0,
                'observation_type': 'measured',
                'accuracy': self.excel_metadata['ctd_c_accuracy'],
                'precision': self.excel_metadata['ctd_c_precision'],
                'resolution': self.excel_metadata['ctd_c_resolution']
            },
            'temperature': {
                'source': 'sci_water_temp',
                'long_name': 'Temperature',
                'standard_name': 'sea_water_temperature',
                'units': 'Celsius',
                'instrument': 'instrument_ctd',
                'valid_min': self.excel_metadata['ctd_t_minimum'],
                'valid_max': self.excel_metadata['ctd_t_maximum'],
                '_FillValue': -999.0,
                'observation_type': 'measured',
                'accuracy': self.excel_metadata['ctd_t_accuracy'],
                'precision': self.excel_metadata['ctd_t_precision'],
                'resolution': self.excel_metadata['ctd_t_resolution']
            },
            'pressure': {
                'source': 'sci_water_pressure',
                'long_name': 'Pressure',
                'standard_name': 'sea_water_pressure',
                'units': 'dbar',
                'conversion': 'bar2dbar',
                'positive': 'down',
                'reference_datum': 'sea-surface',
                'instrument': 'instrument_ctd',
                'valid_min': self.excel_metadata['ctd_p_minimum'],
                'valid_max': self.excel_metadata['ctd_p_maximum'],
                '_FillValue': -999.0,
                'observation_type': 'measured',
                'accuracy': self.excel_metadata['ctd_p_accuracy'],
                'precision': self.excel_metadata['ctd_p_precision'],
                'resolution': self.excel_metadata['ctd_p_resolution'],
                'comment': 'ctd pressure sensor'
            },
            'water_velocity_eastward': {
                'source': 'm_water_vx',
                'long_name': 'Depth-Averaged Eastward Sea Water Velocity',
                'standard_name': 'barotropic_eastward_sea_water_velocity',
                'units': 'm s-1',
                '_FillValue': -999.0
            },
            'water_velocity_northward': {
                'source': 'm_water_vy',
                'long_name': 'Depth-Averaged Northward Sea Water Velocity',
                'standard_name': 'barotropic_northward_sea_water_velocity',
                'units': 'm s-1',
                '_FillValue': -999.0
            }
        }

        # add based on devices present in Excel worksheet metadata
        if self.excel_metadata['puck_installed']:
            self._add_netcdf_variable('chlorophyll', {
                'source': 'sci_flbbcd_chlor_units',
                'long_name': 'Chlorophyll',
                'standard_name': 'concentration_of_chlorophyll_in_sea_water',
                'units': 'mg m-3',
                'valid_min': self.excel_metadata['puck_chlor_minimum'],
                'valid_max': self.excel_metadata['puck_chlor_maximum'],
                '_FillValue': -999.0,
                'resolution': self.excel_metadata['puck_chlor_resolution']
            })
            self._add_netcdf_variable('cdom', {
                'source': 'sci_flbbcd_cdom_units',
                'long_name': 'Colored Dissolved Organic Matter',
                'units': 'ppb',
                'valid_min': self.excel_metadata['puck_cdom_minimum'],
                'valid_max': self.excel_metadata['puck_cdom_maximum'],
                '_FillValue': -999.0,
                'resolution': self.excel_metadata['puck_cdom_resolution']
            })
            self._add_netcdf_variable('backscatter_700', {
                'source': 'sci_flbbcd_bb_units',
                'long_name': '700 nm Wavelength Backscatter',
                'units': "1",
                'valid_min': self.excel_metadata['puck_back_minimum'],
                'valid_max': self.excel_metadata['puck_back_maximum'],
                '_FillValue': -999.0,
                'resolution': self.excel_metadata['puck_back_resolution']
            })
        if self.excel_metadata['oxy_installed']:
            self._add_netcdf_variable('oxygen_concentration', {
                'source': 'sci_oxy4_oxygen',
                'long_name': 'Oxygen Concentration',
                'standard_name': 'mole_concentration_of_dissolved_' +
                                 'molecular_oxygen_in_sea_water',
                'units': 'umol l-1',
                'valid_min': self.excel_metadata['oxy_minimum'],
                'valid_max': self.excel_metadata['oxy_maximum'],
                '_FillValue': -999.0,
                'accuracy': self.excel_metadata['oxy_accuracy'],
                'resolution': self.excel_metadata['oxy_resolution']
            })
        if self.excel_metadata['par_installed']:
            self._add_netcdf_variable('par', {
                'source': 'sci_bsipar_par',
                'long_name': 'Photosynthetically Active Radiation',
                'standard_name': 'downwelling_photosynthetic_photon_' +
                                 'spherical_irradiance_in_sea_water',
                'units': 'umol m-2 s-1',
                'valid_min': self.excel_metadata['par_minimum'],
                'valid_max': self.excel_metadata['par_maximum'],
                '_FillValue': -999.0
            })
        if self.excel_metadata['bb3_installed']:
            self._add_netcdf_variable('backscatter_470', {
                'source': 'sci_bb3slo_b470_scaled',
                'long_name': '470 nm Wavelength Backscatter',
                'units': "1",
                'valid_min': self.excel_metadata['bb3_470_minimum'],
                'valid_max': self.excel_metadata['bb3_470_maximum'],
                '_FillValue': -999.0,
                'resolution': self.excel_metadata['bb3_470_resolution']
            })
            self._add_netcdf_variable('backscatter_532', {
                'source': 'sci_bb3slo_b532_scaled',
                'long_name': '532 nm Wavelength Backscatter',
                'units': "1",
                'valid_min': self.excel_metadata['bb3_532_minimum'],
                'valid_max': self.excel_metadata['bb3_532_maximum'],
                '_FillValue': -999.0,
                'resolution': self.excel_metadata['bb3_532_resolution']
            })
            self._add_netcdf_variable('backscatter_660', {
                'source': 'sci_bb3slo_b660_scaled',
                'long_name': '660 nm Wavelength Backscatter',
                'units': "1",
                'valid_min': self.excel_metadata['bb3_660_minimum'],
                'valid_max': self.excel_metadata['bb3_660_maximum'],
                '_FillValue': -999.0,
                'resolution': self.excel_metadata['bb3_660_resolution']
            })
        if self.excel_metadata['lisst_installed']:
            self._add_netcdf_variable('total_volume_concentration', {
                'source': 'sci_lisst_totvol',
                'long_name': 'Total Volume Concentration of Particles',
                'units': 'uL L-1',
                'valid_min': self.excel_metadata['lisst_vol_minimum'],
                'valid_max': self.excel_metadata['lisst_vol_maximum'],
                '_FillValue': -999.0,
                'resolution': self.excel_metadata['lisst_vol_resolution']
            })
            self._add_netcdf_variable('mean_size', {
                'source': 'sci_lisst_meansize',
                'long_name': 'Mean Particle Size',
                'units': 'um',
                'valid_min': self.excel_metadata['lisst_sz_minimum'],
                'valid_max': self.excel_metadata['lisst_sz_maximum'],
                '_FillValue': -999.0
            })
            self._add_netcdf_variable('beam_attenuation', {
                'source': 'sci_lisst_beamc',
                'long_name': 'Beam Attenuation',
                'units': 'm-1',
                'valid_min': self.excel_metadata['lisst_beam_minimum'],
                'valid_max': self.excel_metadata['lisst_beam_maximum'],
                '_FillValue': -999.0,
                'resolution': self.excel_metadata['lisst_beam_resolution']
            })

        # add from user input (overwrite as necessary)
        if netcdf_variables is not None:
            for name, value in netcdf_variables.items():
                self._add_netcdf_variable(name, value)

    def add_profile_variables(
            self,
            profile_variables: dict[str, dict[str, Any]] = None
    ):
        """Add profile-averaged variable metadata

        Parameters
        ----------
        profile_variables : dict[str, dict[str, Any]], optional
            Profile-averaged variable metadata to overwrite default
            in form {'variable_name': {'attribute': value}}

        """
        _log.info('Adding profile variable metadata to deployment YAML')

        # make sure already have Excel sheet metadata
        self._check_for_excel_meta()

        # initialize
        self.profile_variables = {
            'profile_id': {
                'comment': 'Sequential profile number within the ' +
                           'trajectory.  This value is unique in ' +
                           'each file that is part of a single ' +
                           'trajectory/deployment.',
                'long_name': 'Profile ID',
                'valid_max': 2147483647,
                'valid_min': 1,
                '_FillValue': -999.0
            },
            'profile_time': {
                'comment': 'Timestamp corresponding to the mid-' +
                           'point of the profile',
                'long_name': 'Profile Center Time',
                'observation_type': 'calculated',
                'platform': 'platform',
                'standard_name': 'time',
                '_FillValue': -999.0
            },
            'profile_time_start': {
                'comment': 'Timestamp corresponding to the start ' +
                           'of the profile',
                'long_name': 'Profile Start Time',
                'observation_type': 'calculated',
                'platform': 'platform',
                'standard_name': 'time',
                '_FillValue': -999.0
            },
            'profile_time_end': {
                'comment': 'Timestamp corresponding to the end of ' +
                           'the profile',
                'long_name': 'Profile End Time',
                'observation_type': 'calculated',
                'platform': 'platform',
                'standard_name': 'time',
                '_FillValue': -999.0
            },
            'profile_lat': {
                'comment': 'Value is interpolated to provide an ' +
                           'estimate of the latitude at the ' +
                           'mid-point of the profile',
                'long_name': 'Profile Center Latitude',
                'observation_type': 'calculated',
                'platform': 'platform',
                'standard_name': 'latitude',
                'units': 'degrees_north',
                'valid_max': 90.0,
                'valid_min': -90.0,
                '_FillValue': -999.0
            },
            'profile_lon': {
                'comment': 'Value is interpolated to provide an ' +
                           'estimate of the longitude at the ' +
                           'mid-point of the profile',
                'long_name': 'Profile Center Longitude',
                'observation_type': 'calculated',
                'platform': 'platform',
                'standard_name': 'longitude',
                'units': 'degrees_east',
                'valid_max': 180.0,
                'valid_min': -180.0,
                '_FillValue': -999.0
            },
            'u': {
                'comment': 'The depth-averaged current is an ' +
                           'estimate of the net current measured ' +
                           'while the glider is underwater. The ' +
                           'value is calculated over the entire ' +
                           'underwater segment, which may ' +
                           'consist of 1 or more dives.',
                'long_name': 'Depth-Averaged Eastward Sea Water Velocity',
                'observation_type': 'calculated',
                'platform': 'platform',
                'standard_name': 'eastward_sea_water_velocity',
                'units': 'm s-1',
                'valid_max': 10.0,
                'valid_min': -10.0,
                '_FillValue': -999.0
            },
            'v': {
                'comment': 'The depth-averaged current is an ' +
                           'estimate of the net current measured ' +
                           'while the glider is underwater. The ' +
                           'value is calculated over the entire ' +
                           'underwater segment, which may ' +
                           'consist of 1 or more dives.',
                'long_name': 'Depth-Averaged Northward Sea Water Velocity',
                'observation_type': 'calculated',
                'platform': 'platform',
                'standard_name': 'northward_sea_water_velocity',
                'units': 'm s-1',
                'valid_max': 10.0,
                'valid_min': -10.0,
                '_FillValue': -999.0
            },
            'lon_uv': {
                'comment': 'The depth-averaged current is an ' +
                           'estimate of the net current measured ' +
                           'while the glider is underwater. The ' +
                           'value is calculated over the entire ' +
                           'underwater segment, which may ' +
                           'consist of 1 or more dives.',
                'long_name': 'Depth-Averaged Longitude',
                'observation_type': 'calculated',
                'platform': 'platform',
                'standard_name': 'longitude',
                'units': 'degrees_east',
                'valid_max': 180.0,
                'valid_min': -180.0,
                '_FillValue': -999.0
            },
            'lat_uv': {
                'comment': 'The depth-averaged current is an ' +
                           'estimate of the net current measured ' +
                           'while the glider is underwater.  The ' +
                           'value is calculated over the entire ' +
                           'underwater segment, which may ' +
                           'consist of 1 or more dives.',
                'long_name': 'Depth-Averaged Latitude',
                'observation_type': 'calculated',
                'platform': 'platform',
                'standard_name': 'latitude',
                'units': 'degrees_north',
                'valid_max': 90.0,
                'valid_min': -90.0,
                '_FillValue': -999.0
            },
            'time_uv': {
                'comment': 'The depth-averaged current is an ' +
                           'estimate of the net current measured ' +
                           'while the glider is underwater.  The ' +
                           'value is calculated over the entire ' +
                           'underwater segment, which may ' +
                           'consist of 1 or more dives.',
                'long_name': 'Depth-Averaged Time',
                'standard_name': 'time',
                'calendar': 'gregorian',
                'units': 'seconds since 1970-01-01T00:00:00Z',
                'observation_type': 'calculated',
                '_FillValue': -999.0
            },
            'instrument_ctd': {
                'comment': 'pumped CTD',
                'calibration_date':
                self.excel_metadata['ctd_cal'].strftime('%Y-%m-%dT%H:%M:%SZ'),
                'calibration_report': '" "',
                'factory_calibrated':
                self.excel_metadata['ctd_cal'].strftime('%Y-%m-%dT%H:%M:%SZ'),
                'long_name': self.excel_metadata['ctd_make'] + 
                ' Glider Payload CTD',
                'make_model':
                self.excel_metadata['ctd_make'] + ' ' +
                self.excel_metadata['ctd_type'],
                'platform': 'platform',
                'serial_number': f"{self.excel_metadata['ctd_sn']}",
                'type': 'platform',
                '_FillValue': -999.0
            },
        }

        # add from user input (overwrite as necessary)
        if profile_variables is not None:
            for name, value in profile_variables.items():
                self._add_profile_variable(name, value)

    def add_qartod_tests(
            self,
            qartod_tests:
            dict[str, dict[str, dict[str, Any]]] = None,
            tbdlist: str = None
    ) -> None:
        """Add QARTOD test parameters

        Note
        ----
        Gross Range and Rate of Change Tests use NetCDF variable valid_min, valid_max.

        Spike and Flat Line Tests use NetCDF variable resolution and class style.

        Parameters
        ----------
        qartod_tests : dict[str, dict[str, dict[str, Any]]], optional
            QARTOD test parameters to overwrite default in form
            {'variable_name': {'test_name': {'parameter_name': value}}}
        tbdlist : str, optional
            Path to tbdlist.dat

        """
        _log.info('Adding QARTOD test metadata to deployment YAML')

        # if don't have NetCDF variable metadata already
        if not hasattr(self, 'netcdf_variables'):
            raise AttributeError(
                'Must have NetCDF variable metadata to construct YAML. ' +
                'See method add_netcdf_variables'
            )

        # initialize with instrument limits
        for variable in self.netcdf_variables:
            if (('valid_min' in self.netcdf_variables[variable]) and
               ('valid_max' in self.netcdf_variables[variable])):
                # gross range test fails if outside specified manufacturer limits
                self._add_qartod_test(
                    variable=variable,
                    test='gross_range_test',
                    parameters={
                        'fail_span': [
                            self.netcdf_variables[variable]['valid_min'],
                            self.netcdf_variables[variable]['valid_max']
                        ]
                    }
                )
                # rate of change test suspect if values per second change
                # more than 100th of the total range
                self._add_qartod_test(
                    variable=variable,
                    test='rate_of_change_test',
                    parameters={
                        'threshold': (
                            self.netcdf_variables[variable]['valid_min'],
                            self.netcdf_variables[variable]['valid_max']
                        ) / 100.0
                    }
                )
            if 'resolution' in self.netcdf_variables[variable]:
                res = self.netcdf_variables[variable]['resolution']
                # flat line test is suspect[failed] if difference in a 15sec[30sec]
                # window is less than manufacturer resolution
                self._add_qartod_test(
                    variable=variable,
                    test='flat_line_test',
                    parameters={
                        'suspect_threshold': 15.0,
                        'fail_threshold': 30.0,
                        'tolerance': res
                    }
                )
                # realtime values are a variable distance apart temporally,
                # so spike test will often fail even for good values unless buffered
                # for which we use the interval specified by the user
                if self.style == 'Realtime':
                    if tbdlist is not None:
                        with open(tbdlist,'r') as f:
                            content = f.read()
                            deltat = float(re.findall(
                                self.netcdf_variables[variable]['source'] + r'\s+(\d+)',
                                content,re.IGNORECASE
                            )[0])
                    res *= 2 * deltat
                # spike test is suspect[failed] if average of surrounding values is more
                # than 10[20] times the manufacturer resolution (with buffer in Realtime mode)
                # different than the actual value
                self._add_qartod_test(
                    variable=variable,
                    test='spike_test',
                    parameters={
                        'suspect_threshold': res * 10.0,
                        'fail_threshold': res * 20.0
                    }
                )

        # add from user input (overwrite as necessary)
        if qartod_tests is not None and type(qartod_tests) is not bool:
            for variable, test_parameters in qartod_tests.items():
                for test, parameters in test_parameters.items():
                    self._add_qartod_test(variable, test, parameters)

    def construct_yaml(
            self,
            excelsheet: str = None,
            metadata: dict[str, dict[str, Any]] = None,
            glider_devices: dict[str, dict[str, Any]] = None,
            netcdf_variables: dict[str, dict[str, Any]] = None,
            profile_variables: dict[str, dict[str, Any]] = None,
            qartod_tests: dict[str, dict[str, dict[str, Any]]] | bool = None
    ) -> None:
        """Use Excel sheet output to build YAML output.

        Note
        ----
        Method is intended to replace calling other methods individually: if
        other methods called previously, inputs here will overwrite the results

        Paramters
        ---------
        excelsheet : str, optional
            Path to Excel sheet with metadata
        metadata : dict[str, dict[str, Any]], optional
            Global attributes to overwrite default
            in form {'attribute':value}
        glider_devices : dict[str, dict[str, Any]], optional
            Glider device metadata to overwrite default
            in form {'device_name': {'attribute': value}}
        netcdf_variables : dict[str, dict[str, Any]], optional
            NetCDF variable name mapping and metadata to overwrite default
            in form {'variable_name': {'attribute': value}
        profile_variables : dict[str, dict[str, Any]], optional
            Profile-averaged variable metadata to overwrite default
            in form {'variable_name': {'attribute': value}}
        qartod_tests : dict[str, dict[str, dict[str, Any]]] | bool, optional
            QARTOD test parameters to overwrite default in form
            {'variable_name': {'test_name': {'parameter_name': value}}}
            or specify False to skip adding QARTOD tests

        """
        # if gave inputs, overwrite any previous/assign
        if excelsheet is not None:
            self.excelsheet = excelsheet
            if hasattr(self, 'excel_metadata'):
                delattr(self, 'excel_metadata')
        if qartod_tests is not None:
            if hasattr(self, 'qartod_tests'):
                delattr(self, 'qartod_tests')
        else:
            qartod_tests = True
        if metadata is not None:
            if hasattr(self, 'metadata'):
                delattr(self, 'metadata')
        if glider_devices is not None:
            if hasattr(self, 'glider_devices'):
                delattr(self, 'glider_devices')
        if netcdf_variables is not None:
            if hasattr(self, 'netcdf_variables'):
                delattr(self, 'netcdf_variables')
        if profile_variables is not None:
            if hasattr(self, 'profile_variables'):
                delattr(self, 'profile_variables')

        _log.info(f'Creating deployment YAML for {self.ID}')

        # if don't have Excel sheet metadata already
        if not hasattr(self, 'excel_metadata'):
            # if given a sheet to read
            if self.excelsheet is not None:
                # get metadata
                self.add_excel_metadata(self.excelsheet)
            # no sheet to read
            else:
                # stop running
                raise AttributeError('Must have Excel worksheet metadata to ' +
                                     'construct YAML. See method collect_' +
                                     'excelsheet_metadata or provide key ' +
                                     '"excelsheet"')

        # if don't already have "metadata": global variables for NetCDF
        if not hasattr(self, 'metadata'):
            self.add_metadata(metadata)

        # if don't have "glider_devices": metadata for installed instruments
        # already
        if not hasattr(self, 'glider_devices'):
            self.add_glider_devices(glider_devices)

        # if don't have "netcdf_variables": metadata for translating glider
        # variables to NetCDF variables already
        if not hasattr(self, 'netcdf_variables'):
            self.add_netcdf_variables(netcdf_variables)

        # if don't have "profile_variables": metadata for profile-averaged
        # variables already
        if not hasattr(self, 'profile_variables'):
            self.add_profile_variables(profile_variables)

        # if don't have qartod tests, if desired, already
        if not hasattr(self, 'qartod_tests'):
            if qartod_tests:
                self.add_qartod_tests(qartod_tests)

        # add everything together
        self.yaml = {
            'metadata': self.metadata,
            'glider_devices': self.glider_devices,
            'netcdf_variables': self.netcdf_variables,
            'profile_variables': self.profile_variables
        }
        if hasattr(self, 'qartod_tests'):
            self.yaml['qartod_tests'] = self.qartod_tests

    def write_yaml(self, outname: str = 'deployment_metadata.yml') -> None:
        """Write yaml dictionary to YAML file.

        Parameters
        ----------
        outname : str, optional
            Full path to YAML file to write

        """
        # assign input
        self.outname = outname

        # make sure have necessary variables
        if not hasattr(self, 'yaml'):
            raise AttributeError('Must have constructed an output yaml ' +
                                 'dictionary. See method `construct_yaml`')

        # write out
        _log.info(f'Wrting deployment YAML for {self.ID} as {self.outname}')
        with open(self.outname, 'w') as outfile:
            yaml.dump(self.yaml, outfile, default_flow_style=False)

    def _check_for_excel_meta(self):
        """Check for Excel metadata already loaded.

        Note
        ----
        Internal; used by many steps

        """
        _log.debug('Checking for existing Excel worksheet metadata')
        # if don't have Excel sheet metadata already
        if not hasattr(self, 'excel_metadata'):
            raise AttributeError('Must have Excel worksheet metadata ' +
                                 'to construct YAML. See method ' +
                                 'collect_excelsheet_metadata')

    def _add_meta(self, name: str, value: Any):
        """Add to dictionary of metadata.

        Note
        ----
        Internal; `metadata` attribute fills in public methods

        Parameters
        ----------
        name : str
            Attribute name
        value : Any
            Attribute value

        """
        _log.debug(f'Adding {name} to metadata')
        self.metadata[name] = value

    def _add_glider_device(self, name: str, value: Any):
        """Add to dictionary of device metadata.

        Note
        ----
        Internal; `glider_devices` attribute fills in public methods

        Parameters
        ----------
        name : str
            Attribute name
        value : Any
            Attribute value

        """
        _log.debug(f'Adding {name} to device metadata')
        self.glider_devices[name] = value

    def _add_netcdf_variable(self, name: str, value: Any):
        """Add to dictionary of variable mapping metadata.

        Note
        ----
        Internal; `netcdf_variables` attribute fills in public methods

        Parameters
        ----------
        name : str
            Attribute name
        value : Any
            Attribute value

        """
        _log.debug(f'Adding {name} to variable mapping metadata')
        self.netcdf_variables[name] = value

    def _add_profile_variable(self, name: str, value: Any):
        """Add to dictionary of profile variable mapping metadata.

        Note
        ----
        Internal; `profile_variables` attribute fills in public methods

        Parameters
        ----------
        name : str
            Attribute name
        value : Any
            Attribute value

        """
        _log.debug(f'Adding {name} to profile variable mapping metadata')
        self.profile_variables[name] = value

    def _add_qartod_test(self, variable: str, test: str, parameters: Any):
        """Add to dictionary of QARTOD tests to perform.

        Note
        ----
        Internal; `qartod_tests` attribute fills in public methods

        Parameters
        ----------
        variable : str
            Variable name
        test : str
            Test name for variable
        parameters : Any
            Test parameters for variable

        """
        _log.debug(f'Adding {variable} to QARTOD test metadata')
        try:
            self.qartod_tests['streams'][variable]['qartod'][test] = parameters
        except Exception:
            try:
                self.qartod_tests['streams'][variable] = {
                    'qartod': {test: parameters}
                }
            except Exception:
                self.qartod_tests = {'streams': {variable: {
                    'qartod': {test: parameters}
                }}}
        # #this part will only be necessary/useful if pyglider and
        # ioos_qc cooperate
        # try:
        #     self.netcdf_variables[variable]['ancillary_variables'] +=
        # f'{variable}_qartod_{test} '
        # except:
        #     self.netcdf_variables[variable]['ancillary_variables'] =
        # f' {variable}_qartod_{test} '


class DeploymentNetCDF():
    """Contains deployment-specific data and metadata in IOOS Glider DAC form

    Parameters
    ----------
    main_directory : str
        Path to directory with raw file directory and cache file
        directory that will also hold the processed file directory
    binary_directory : str, default = 'Raw'
        Path, relative to main_directory, that holds raw files
    cache_directory : str, default = join_path('Raw', 'Cache')
        Path, relative to main_directory, that holds cache files
    deployment_yaml : str, default = 'deployment_metadata.yml'
        Path, relative to main_directory, for the YAML with the
        deployment-specific metadata
    style : str, default = 'Realtime'
        Deployment processing type, either 'Realtime' or 'Delayed'

    Attributes
    ----------
    main_directory : str
        Full path to raw, cache, and processed directories
    binary_directory : str
        Full path to directory with raw files
    cache_directory : str
        Full path to directory with cache files
    deployment_yaml : str
        Full path to deployment-specific YAML file
    style : str
        Deployment processing type
    l0timeseries_directory : str
        Full path to the directory with the L0 timeseries NetCDFs
    l0profile_directory : str
        Full path to the directory with the L0 profile NetCDFs
    l0timeseries_outname : str
        Full path to the L0 timeseries NetCDF
    l1timeseries_directory : str
        Full path to the directory with the L1 timeseries NetCDFs
    l1profile_directory : str
        Full path to the directory with the L1 profile NetCDFs
    l1timeseries_outname : str
        Full path to the L1 timeseries NetCDF
    passing_state : dict
        Full path of each file checked and its passing state,
        which is False if not passed or already evaluated

    """

    def __init__(
            self,
            main_directory: str,
            binary_directory: str = 'Raw',
            cache_directory: str = join_path('Raw', 'Cache'),
            deployment_yaml: str = 'deployment_metadata.yml',
            style: str = 'Realtime'
    ) -> None:
        self.main_directory = main_directory
        self.binary_directory = join_path(main_directory, binary_directory)
        self.cache_directory = join_path(main_directory, cache_directory)
        self.deployment_yaml = join_path(
            main_directory, style, deployment_yaml
        )
        self.style = style

    def read_timeseries(self, timeseries_file: str) -> xr.Dataset:
        """Read a timeseries NetCDF as a Dataset

        Parameters
        ----------
        timeseries_file : str
            Path, relative to the class's main_directory and style,
            to a timeseries NetCDF file

        Returns
        -------
        xarray Dataset
            Dataset from file

        """
        timeseries_file = join_path(
            self.main_directory, self.style, timeseries_file
        )
        _log.info(f'Reading {timeseries_file} into memory')
        with xr.open_dataset(timeseries_file) as ds:
            return ds

    def read_profiles(self, profile_directory: str) -> xr.Dataset:
        """Read a directory of profile NetCDFs as a single Dataset

        Parameters
        ----------
        profile_directory : str
            Path, relative to the class's main_directory and style,
            to a directory of profile NetCDF files

        Returns
        -------
        xarray Dataset
            Combined Dataset from files

        """
        profile_directory = join_path(
            self.main_directory, self.style, profile_directory, '*.nc'
        )
        _log.info(f'Reading all files in {profile_directory} into memory')
        with xr.open_mfdataset(profile_directory) as ds:
            return ds

    def make_L0(
            self,
            timeseries_directory: str = 'L0-timeseries',
            profile_directory: str | bool | None = 'L0-profiles'
    ) -> None:
        """Create L0 (read and interpolated) timeseries and profile NetCDFs.

        Note
        ----
        Reading and interpolating occur according to `pyglider`

        Parameters
        ----------
        timeseries_directory : str, optional
            Path, relative to class's main_directory and style,
            to the directory to put the L0 timeseries NetCDFs
        profile_directory : str, optional
            Path, relative to class's main_directory and style,
            to the directory to put the L0 profile NetCDFs.
            Specify None or False to skip writing profile NetCDFs

        """
        # assign inputs
        match self.style:
            case 'Realtime':
                self.search = '*.[s|t]bd'
                self.profile_filt_time = 20
                self.profile_min_time = 60
            case 'Delayed':
                self.search = '*.[d|e]bd'
                self.profile_filt_time = 100
                self.profile_min_time = 300
            case _:
                raise ValueError('Input "style" must be "realtime", ' +
                                 '"delayed", or None')
        self.l0timeseries_directory = join_path(
            self.main_directory, self.style, timeseries_directory
        )
        if profile_directory:
            self.l0profile_directory = join_path(
                self.main_directory, self.style, profile_directory
            )
        else:
            self.l0profile_directory = profile_directory

        # turn binary *.*bd (file extension based on search) into a single
        # timeseries netcdf file
        self.l0timeseries_outname = slocum.binary_to_timeseries(
            self.binary_directory, self.cache_directory,
            self.l0timeseries_directory, self.deployment_yaml,
            search=self.search, profile_filt_time=self.profile_filt_time,
            profile_min_time=self.profile_min_time
        )
        _log.info('Created L0 single timeseries NetCDF' +
                  f' {self.l0timeseries_outname}')

        # make profile netcdf files
        if self.l0profile_directory:
            _log.info('Creating L0 profile NetCDFs in ' +
                      f'{self.l0profile_directory}')
            extract_timeseries_profiles(
                self.l0timeseries_outname,
                self.l0profile_directory,
                self.deployment_yaml
            )

    def make_L1(
            self,
            timeseries_directory: str = 'L1-timeseries',
            profile_directory: str | bool | None = 'L1-profiles'
    ) -> None:
        """Create the L1 (QARTOD tested) timeseries and profile NetCDFs.

        Note
        ----
        Tests performed according to `ioos_qc`

        Parameters
        ----------
        timeseries_directory : str, optional
            Path, relative to class's main_directory and style,
            to the directory to put the L1 timeseries NetCDFs
        profile_directory : str, optional
            Path, relative to class's main_directory and style,
            to the directory to put the L1 profile NetCDFs.
            Specify None or False to skip writing profile NetCDFs

        """
        # make sure already have an L0
        if not hasattr(self, 'l0timeseries_outname'):
            raise AttributeError(
                'No L0 timeseries file path exists. ' +
                'Must run make_L0 before make_L1'
            )

        # assign inputs
        self.l1timeseries_directory = join_path(
            self.main_directory, self.style, timeseries_directory
        )
        if profile_directory:
            self.l1profile_directory = join_path(
                self.main_directory, self.style, profile_directory
            )
        else:
            self.l1profile_directory = profile_directory

        # make sure output directory exists
        if not exists(self.l1timeseries_directory):
            makedirs(self.l1timeseries_directory)

        # create output name based on L0 name
        self.l1timeseries_outname = join_path(
            self.l1timeseries_directory,
            basename(self.l0timeseries_outname)
        )
        _log.info('Creating L1 single timeseries ' +
                  f'NetCDF {self.l1timeseries_outname}')

        # use yaml configuration for ioos_qc configuration
        _log.info('Extracting QARTOD test parameters from ' +
                  f'{self.deployment_yaml}')
        with open(self.deployment_yaml) as fin:
            metadata = yaml.safe_load(fin)
        config = Config(metadata['qartod_tests'])

        # perform qartod tests on L0 to create L1
        _log.info(f'Running QARTOD tests on {self.l0timeseries_outname}')
        with xr.open_dataset(self.l0timeseries_outname) as ds:
            # run initial tests
            stream = XarrayStream(ds, time='time', z='depth',
                                  lat='latitude', lon='longitude')
            runner = list(stream.run(config))
            # group initial results by stream_id (source variable)
            grouped_runner = (
                {k: list(g) for k, g in groupby(runner, lambda r: r.stream_id)}
            )
            # run aggregate tests and add to initial results
            for source, run in grouped_runner.items():
                result = collect_results(run)
                agg = ContextResult(
                    stream_id=source,
                    results=[CallResult(
                        package='',
                        test='qc',
                        function=aggregate,
                        results=aggregate(result)
                    )],
                    subset_indexes=run[0].subset_indexes,
                    data=run[0].data,
                    tinp=run[0].tinp,
                    zinp=run[0].zinp,
                    lat=run[0].lat,
                    lon=run[0].lon
                )
                runner.append(agg)
            # store results
            store = PandasStore(runner)
            # append results to existing Dataset
            ds = xr.merge([
                ds,
                # store results as Pandas DataFrame
                store.save()
                # set the index (xarray coordinate) to time
                .set_index('time')
                # remove redundant columns added by ioos_qc
                .drop(columns=['z', 'lat', 'lon'])
                # make all bytes as required by GDAC
                .astype('int8')
                # convert results to Dataset
                .to_xarray()
            ])
        # redefine some aggregate results how GDAC wants
        for name, da in ds.data_vars.items():
            if '_qc' in name:
                da[da == 2] = 0
        # add metadata (loosely based on ioos_qc CFNetCDFStore)
        for result in store.collected_results:
            # get variable name of focus test result
            name = column_from_collected_result(result)
            _log.debug(f'Adding {name} to dataset')
            # get test function of focus test result
            func = result.function
            # get name of source variable
            source = result.stream_id
            # get existing ancillary variables for source
            ancillary = getattr(ds[source], 'ancillary_variables', '')
            # add this one
            ancillary += f' {name}'
            # if aggregate test result
            if '_qc' in name:
                # define flags
                flag_values = [x for x in range(0, 10)]
                flag_names = (
                    'no_qc_performed good_data probably_good_data' +
                    'bad_data_that_are_potentially_correctable ' +
                    'bad_data value_changed not_used not_used ' +
                    'interpolated_value missing_value'
                )
                # define "input" for focus test result
                call = 'various'
            else:
                # separate flag details
                flags = getmodule(func).FLAGS
                flag_names = [d for d in flags.__dict__ if not
                              d.startswith("__")]
                flag_values = [getattr(flags, d) for d in flag_names]
                # get qartod input for focus test result
                call = config.calls_by_stream_id(source)
                call = [c for c in call if c.module == result.package
                        and c.method == result.test]
                call = str(call[0].kwargs)
            # update Dataset
            ds[source] = ds[source].assign_attrs(ancillary_variables=ancillary)
            ds[name] = ds[name].assign_attrs(
                standard_name=getattr(func, 'standard_name', 'quality_flag'),
                long_name=getattr(func, 'long_name', 'Quality Flag'),
                flag_values=np.byte(flag_values),
                flag_meanings=" ".join(flag_names),
                valid_min=np.byte(min(flag_values)),
                valid_max=np.byte(max(flag_values)),
                ioos_qc_module=result.package,
                ioos_qc_test=result.test,
                ioos_qc_target=source,
                ioos_qc_config=call,
                _FillValue=np.byte(-127)
            )
        # export L1 timeseries netcdf file
        _log.info(f'Saving QARTOD test results as {self.l1timeseries_outname}')
        ds.to_netcdf(self.l1timeseries_outname)

        # make L1 profile NetCDF files for IOOS GliderDAC
        if self.l1profile_directory:
            _log.info('Creating L1 profile NetCDFs in' +
                      f' {self.l1profile_directory}')
            extract_timeseries_profiles(self.l1timeseries_outname,
                                        self.l1profile_directory,
                                        self.deployment_yaml)

    def check_compliance(self, profile_directory: str = 'L1-profiles') -> None:
        """Use the IOOS compliance checker on profile files.

        Parameters
        ----------
        profile_directory : str, optional
            Path, relative to class's main_directory and style,
            to the directory with the target profile NetCDFs

        """
        profile_directory = join_path(self.main_directory, self.style,
                                      profile_directory)
        _log.info(f'Checking profile NetCDFs in {profile_directory}')

        # define log level for checker verbosity
        match _log.root.level:
            case 10:
                # DEBUG
                log_level = 2
            case 20:
                # INFO
                log_level = 1
            case _:
                # everything else
                log_level = 0

        # get file names to check
        file_names = listdir(profile_directory)
        file_names = [file for file in file_names if '.nc' in file]

        # initialize compliance checker
        check_suite = CheckSuite()
        check_suite.load_all_available_checkers()
        checker = ComplianceChecker()

        # run compliance checker for each file
        passed = [False] * len(file_names)
        for idx, file in enumerate(file_names):
            file = file.split('.')[0]
            file = join_path(profile_directory, file)
            _log.info(f'Checking {file}_report.txt')
            if not exists(file+'_report.txt'):
                passed[idx], _ = checker.run_checker(
                    ds_loc=file+'.nc',
                    output_filename=file+'_report.txt',
                    checker_names=['gliderdac'],
                    verbose=log_level,
                    criteria='normal'
                )
                if passed[idx]:
                    isnot = 'is'
                else:
                    isnot = 'is not'
                _log.info(f'{file}.nc {isnot} IOOS GliderDAC compliant.' +
                          f'See {file}_report.txt for details.')

        # output
        self.passing_state = {
            join_path(profile_directory, file):
            state for file, state in zip(file_names, passed)
        }
