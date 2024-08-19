"""
Utilities for processing Slocum glider files the Kiwi way
"""
from os.path import join as join_path
from os.path import basename, exists
from os import makedirs, listdir
from tempfile import NamedTemporaryFile
from itertools import groupby
import yaml
import logging
from openpyxl import load_workbook
from pyglider import slocum
from pyglider import ncprocess
from ioos_qc.config import Config
from ioos_qc.streams import XarrayStream
from ioos_qc.results import collect_results, ContextResult, CallResult
from ioos_qc.qartod import aggregate
from ioos_qc.stores import CFNetCDFStore
from compliance_checker.runner import ComplianceChecker, CheckSuite
from pocean.dsg import OrthogonalMultidimensionalTimeseries
import xarray as xr
import numpy as np
from datetime import datetime
import pygmt
from utm import from_latlon


_log = logging.getLogger(__name__)


def dd2dm(decimal_degrees):
    """
    convert decimal degrees to degree minute notation

    adapted from MATLAB's degrees2dm function
    """
    degrees = np.fix(decimal_degrees)
    minutes = 60*np.remainder(np.abs(decimal_degrees), 1)
    return degrees, minutes


def dm2dd(degrees, minutes):
    """
    convert degree minute notation to decimal degrees

    adapted from MATLAB's degrees2dm function
    """
    decimal_degrees = np.abs(degrees) + np.abs(minutes)/60
    decimal_degrees = np.where(degrees < 0 or minutes < 0, decimal_degrees*-1,
                               decimal_degrees)
    return decimal_degrees


def first_nonnan(numpy_array):
    """
    Get the first non-nan value in a numpy array
    """
    return numpy_array[np.isfinite(numpy_array)][0]


def last_nonnan(numpy_array):
    """
    Get the last non-nan value in a numpy array
    """
    return numpy_array[np.isfinite(numpy_array)][-1]


def do_step(step=0, **kwargs):
    """
    do specified step of kiwiglider
    step can be int or str (to allow for 1a, 1b, etc.)
    also include required arguments for step to run [or should we make a
    mechanism to ask?]
    """
    match str(step):
        case '0':
            # make deployment YAML
            pass
        case '1':
            # do L0
            pass
        case '2':
            # do L1
            pass


def collect_excelsheet_metadata(excelsheet, ID=1):
    """
    extract Excel sheet metadata for given deployment ID

    First row of Excel sheet must contain descriptive column headers.
    First column of Excel sheet must contain deployment ID numbers.
    """
    _log.info(f'Getting metadata from {excelsheet}')

    # load the Excel sheet
    worksheet = load_workbook(excelsheet).active
    # get header names (must be present in first row)
    headers = [worksheet.cell(row=1, column=idx).value
               for idx in range(2, worksheet.max_column+1)]
    # get deployment numbers (must be present in first column)
    deployments = [worksheet.cell(row=idx, column=1).value
                   for idx in range(2, worksheet.max_row+1)]

    # return metadata from input deployment ID
    return {headers[idx-2]: worksheet.cell(
        row=deployments.index(ID)+2, column=idx).value
        for idx in range(2, worksheet.max_column+1)}


class DeploymentYAML():
    """
    class with methods to add metadata and write out deployment-specific YAML
    for pyglider
    """
    def __init__(self, ID=1):
        """
        initialize the YAML with the deployment ID
        """
        self.ID = ID

    def add_excel_metadata(self, excelsheet, ID=None):
        """
        add DeploymentYAML.excel_metadata: Excel sheet metadata for given
        deployment ID

        supplying ID here will overwrite what was given during initialization

        First row of Excel sheet must contain descriptive column headers.
        First column of Excel sheet must contain deployment ID numbers.
        """

        # assign input Excel sheet
        self.excelsheet = excelsheet
        # if gave input, overwrite existing
        if ID is not None:
            self.ID = ID

        # get metadata from input deployment ID
        self.excel_metadata = collect_excelsheet_metadata(self.excelsheet,
                                                          self.ID)

    def add_metadata(self, metadata=None):
        """
        add DeploymentYAML.metadata: global variables for NetCDF
        """
        _log.info('Adding global metadata to deployment YAML')

        # make sure already have Excel sheet metadata
        self._check_for_excel_meta()

        # initialize with static metadata
        self.metadata = {
            'Conventions': 'CF-1.11',
            'Metadata_Conventions': 'CF-1.11, Unidata Dataset Discovery v1.0',
            'contributor_role_vocabulary': (
                'http://vocab.nerc.ac.uk/search_nvs/W08/'),
            'comment': '" "',
            'creator_url': '" "',
            'format_version': 'IOOS_Glider_NetCDF_v2.0.nc',
            'keywords':
                ('Water-based Platforms > Uncrewed Vehicles >' +
                 ' Subsurface > Seaglider, ') +
                'Oceans > Marine Sediments > Turbidity, ' +
                'Oceans > Ocean Chemistry > Oxygen, ' +
                'Oceans > Ocean Circulation > Turbulence, ' +
                'Oceans > Ocean Pressure > Water Pressure, ' +
                'Oceans > Ocean Temperature > Water Temperature, ' +
                'Oceans > Salinity/Density > Conductivity, ' +
                'Oceans > Salinity/Density > Density, ' +
                'Oceans > Salinity/Density > Salinity',
            'keywords_vocabulary': 'GCMD Science Keywords',
            'license': ('This data may be redistributed and used without' +
                        ' restriction'),
            'metadata_link': '" "',
            'processing_level': 'Data are provided as-is',
            'publisher_url': '" "',
            'references': '" "',
            'source': 'Observational data from a profiling glider',
            'standard_name_vocabulary': ('Standard Name Table (v85, ' +
                                         '21 May 2024)'),
            'summary': ('This dataset contains physical oceanographic ' +
                        'measurements of temperature, conductivity, ' +
                        'salinity, density and estimates of depth-averaged ' +
                        'currents.'),
        }

        # add from Excel sheet
        acknowledge = ('This work supported by funding from ' +
                       self.excel_metadata['owner'])
        self._add_meta('acknowledgement', acknowledge)
        pilot = self.excel_metadata['pilot']
        contributor_name = ','.join(
            [self.excel_metadata['principal_investigator'],
             self.excel_metadata['data_manager'], pilot])
        self._add_meta('contributor_name', contributor_name)
        contributor_role = ','.join(
            ['Principal Investigator'] + ['Data Manager'] +
            ['Operator']*int(pilot.count(',')+1))
        self._add_meta('contributor_role', contributor_role)
        self._add_meta('creator_email',
                       self.excel_metadata['data_manager_email'])
        self._add_meta('creator_name', self.excel_metadata['data_manager'])
        self._add_meta('deployment_name', 'GLD{:04d}'.format(self.ID))
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

    def add_glider_devices(self, glider_devices=None):
        """
        add DeploymentYAML.glider_devices: metadata for installed instruments
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
                'make': 'Seabird',
                'model': self.excel_metadata['ctd_type'],
                'serial': f'{self.excel_metadata['ctd_sn']}',
                'long_name': 'Seabird SlocumCTD',
                'make_model': 'Seabird SlocumCTD',
                'factory_calibrated': '" "',
                'calibration_date':
                self.excel_metadata['ctd_cal'].strftime('%Y-%m-%d'),
                'calibration_report': '" "',
                'comment': '" "'
            }
        }

        # add based on devices present in Excel worksheet metadata
        if self.excel_metadata['wetlabs_installed']:
            self._add_glider_device('optics', {
                'make': 'Wetlabs',
                'model': self.excel_metadata['wetlabs_type'],
                'serial': f'{self.excel_metadata['wetlabs_sn']}',
                'factory_calibrated':
                self.excel_metadata['wetlabs_cal'].strftime('%Y-%m-%d'),
                'calibration_date':
                self.excel_metadata['wetlabs_cal'].strftime('%Y-%m-%d'),
                'calibration_report': '" "',
                'comment': '" "'
            })
        if self.excel_metadata['oxy_installed']:
            self._add_glider_device('oxygen', {
                'make': 'AADI',
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
                'make': 'Biospherical',
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
                'make': 'SeaBird',
                'model': self.excel_metadata['bb3_type'],
                'serial': f'{self.excel_metadata['bb3_sn']}',
                'factory_calibrated':
                self.excel_metadata['bb3_cal'].strftime('%Y-%m-%d'),
                'calibration_date':
                self.excel_metadata['bb3_cal'].strftime('%Y-%m-%d'),
                'calibration_report': '" "',
                'comment': '" "'
            })
        if self.excel_metadata['lisst_installed']:
            self._add_glider_device('lisst', {
                'make': 'Sequoia',
                'model': self.excel_metadata['lisst_type'],
                'serial': f'{self.excel_metadata['lisst_sn']}',
                'factory_calibrated':
                self.excel_metadata['lisst_cal'].strftime('%Y-%m-%d'),
                'calibration_date':
                self.excel_metadata['lisst_cal'].strftime('%Y-%m-%d'),
                'calibration_report': '" "',
                'comment': '" "'
            })
        if self.excel_metadata['microrider_installed']:
            self._add_glider_device('microrider', {
                'make': 'Rockland',
                'model': self.excel_metadata['microrider_type'],
                'serial': f'{self.excel_metadata['microrider_sn']}',
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

    def add_netcdf_variables(self, netcdf_variables=None):
        """
        add DeploymentYAML.netcdf_variables: metadata for translating glider
        variables to NetCDF variables

        supplying metadata here will overwrite what was given during
        initialization
        """
        _log.info('Adding variable metadata to deployment YAML')

        # make sure already have Excel sheet metadata
        self._check_for_excel_meta()

        # initialize common variables
        self.netcdf_variables = {
            'time': {
                'source':   'sci_m_present_time',
                'long_name':     'Time',
                'standard_name': 'time',
                'calendar':      'gregorian',
                'units':         'seconds since 1970-01-01T00:00:00Z',
                'observation_type': 'measured'
            },
            'latitude': {
                'source':  'm_gps_lat',
                'long_name':    'Latitude',
                'standard_name': 'latitude',
                'units':        'degrees_north',
                'comment':     'Estimated between surface fixes',
                'observation_type': 'measured',
                'platform':     'platform',
                'reference':    'WGS84',
                'valid_max':  90.0,
                'valid_min': -90.0,
                'coordinate_reference_frame':  'urn:ogc:crs:EPSG::4326'
            },
            'longitude': {
                'source':  'm_gps_lon',
                'long_name':    'Longitude',
                'standard_name': 'longitude',
                'units':        'degrees_east',
                'comment':     'Estimated between surface fixes',
                'observation_type': 'measured',
                'platform':     'platform',
                'reference':    'WGS84',
                'valid_max':  180.0,
                'valid_min': -180.0,
                'coordinate_reference_frame':  'urn:ogc:crs:EPSG::4326'
            },
            'heading': {
                'source':  'm_heading',
                'long_name':    'Glider Heading Angle',
                'standard_name': 'platform_orientation',
                'units':        'rad'
            },
            'pitch': {
                'source':  'm_pitch',
                'long_name':    'Glider Pitch Angle',
                'standard_name': 'platform_pitch_angle',
                'units':        'rad'
            },
            'roll': {
                'source':  'm_roll',
                'long_name':    'Glider Roll Angle',
                'standard_name': 'platform_roll_angle',
                'units':        'rad'
            },
            'conductivity': {
                'source':  'sci_water_cond',
                'long_name':    'Conductivity',
                'standard_name': 'sea_water_electrical_conductivity',
                'units':        'S m-1',
                'instrument':    'instrument_ctd',
                'valid_min':    0.0,
                'valid_max':    10.0,
                'observation_type': 'measured',
                'accuracy':      0.0003,
                'precision':     0.0001,
                'resolution':    0.00002
            },
            'temperature': {
                'source':  'sci_water_temp',
                'long_name':    'Temperature',
                'standard_name': 'sea_water_temperature',
                'units':        'Celsius',
                'instrument':   'instrument_ctd',
                'valid_min': -5.0,
                'valid_max':  50.0,
                'observation_type': 'measured',
                'accuracy':      0.002,
                'precision':     0.001,
                'resolution':    0.0002
            },
            'pressure': {
                'source':  'sci_water_pressure',
                'long_name':    'Pressure',
                'standard_name':  'sea_water_pressure',
                'units':        'dbar',
                'conversion':   'bar2dbar',
                'valid_min':    0.0,
                'valid_max':    2000.0,
                'positive':      'down',
                'reference_datum':  'sea-surface',
                'instrument':     'instrument_ctd',
                'observation_type': 'measured',
                'accuracy':         1.0,
                'precision':        2.0,
                'resolution':       0.02,
                'comment':          'ctd pressure sensor'
            },
            'water_velocity_eastward': {
                'source':    'm_water_vx',
                'long_name':      'Depth-Averaged Eastward Sea Water Velocity',
                'standard_name':  'barotropic_eastward_sea_water_velocity',
                'units':          'm s-1'
            },
            'water_velocity_northward': {
                'source':    'm_water_vy',
                'long_name':     'Depth-Averaged Northward Sea Water Velocity',
                'standard_name':  'barotropic_northward_sea_water_velocity',
                'units':          'm s-1'
            }
        }

        # add based on devices present in Excel worksheet metadata
        if self.excel_metadata['wetlabs_installed']:
            self._add_netcdf_variable('chlorophyll', {
                'source':  'sci_flbbcd_chlor_units',
                'long_name':    'Chlorophyll',
                'standard_name': 'concentration_of_chlorophyll_in_sea_water',
                'units':        'mg m-3',
                'valid_min':    0.0,
                'valid_max':    50.0,
                'resolution':   0.025
            })
            self._add_netcdf_variable('cdom', {
                'source':  'sci_flbbcd_cdom_units',
                'long_name':    'Colored Dissolved Organic Matter',
                'units':        'ppb',
                'valid_min':    0.0,
                'valid_max':    375.0,
                'resolution':   0.184
            })
            self._add_netcdf_variable('backscatter_700', {
                'source':  'sci_flbbcd_bb_units',
                'long_name':    '700 nm Wavelength Backscatter',
                'units':         "1",
                'valid_min':    0.0,
                'valid_max':    5.0,
                'resolution':   0.003
            })
        if self.excel_metadata['oxy_installed']:
            self._add_netcdf_variable('oxygen_concentration', {
                'source':  'sci_oxy4_oxygen',
                'long_name':    'Oxygen Concentration',
                'standard_name':
                ('mole_concentration_of_dissolved_' +
                 'molecular_oxygen_in_sea_water'),
                'units':        'umol l-1',
                'valid_min':    0.0,
                'valid_max':    500.0,
                'accuracy':     8.0,
                'resolution':   1.0
            })
        if self.excel_metadata['par_installed']:
            self._add_netcdf_variable('par', {
                'source':  'sci_bsipar_par',
                'long_name':    'Photosynthetically Active Radiation',
                'standard_name':
                ('downwelling_photosynthetic_photon_' +
                 'spherical_irradiance_in_sea_water'),
                'units':        'umol m-2 s-1',
                'valid_min':     0.0000000014,
                'valid_max':     0.00005
            })
        if self.excel_metadata['bb3_installed']:
            self._add_netcdf_variable('backscatter_470', {
                'source':  'sci_bb3slo_b470_scaled',
                'long_name':    '470 nm Wavelength Backscatter',
                'units':         "1",
                'valid_min':    0.0,
                'valid_max':    5.0,
                'resolution':   0.003
            })
            self._add_netcdf_variable('backscatter_532', {
                'source':  'sci_bb3slo_b532_scaled',
                'long_name':    '532 nm Wavelength Backscatter',
                'units':         "1",
                'valid_min':    0.0,
                'valid_max':    5.0,
                'resolution':   0.003
            })
            self._add_netcdf_variable('backscatter_660', {
                'source':  'sci_bb3slo_b660_scaled',
                'long_name':    '660 nm Wavelength Backscatter',
                'units':         "1",
                'valid_min':    0.0,
                'valid_max':    5.0,
                'resolution':   0.003
            })
        if self.excel_metadata['lisst_installed']:
            self._add_netcdf_variable('total_volume_concentration', {
                'source':  'sci_lisst_totvol',
                'long_name':    'Total Volume Concentration of Particles',
                'units':         'uL L-1',
                'valid_min':    0.5,
                'valid_max':    700,
                'resolution':   0.1
            })
            self._add_netcdf_variable('mean_size', {
                'source':  'sci_lisst_meansize',
                'long_name':    'Mean Particle Size',
                'units':         'um',
                'valid_min':    1.0,
                'valid_max':    500
            })
            self._add_netcdf_variable('beam_attenuation', {
                'source':  'sci_lisst_beamc',
                'long_name':    'Beam Attenuation',
                'units':         'm-1',
                'valid_min':    0.3,
                'valid_max':    0.99,
                'resolution':   0.1
            })

        # add from user input (overwrite as necessary)
        if netcdf_variables is not None:
            for name, value in netcdf_variables.items():
                self._add_netcdf_variable(name, value)

    def add_profile_variables(self, profile_variables=None):
        """
        add DeploymentYAML.profile_variables: metadata for profile-averaged
        variables
        """
        _log.info('Adding profile variable metadata to deployment YAML')

        # make sure already have Excel sheet metadata
        self._check_for_excel_meta()

        # initialize
        self.profile_variables = {
            'profile_id': {
                'comment':
                ('Sequential profile number within the trajectory.' +
                 ' This value is unique in each file that is part of' +
                 ' a single trajectory/deployment.'),
                'long_name': 'Profile ID',
                'valid_max': 2147483647,
                'valid_min': 1
            },
            'profile_time': {
                'comment':
                'Timestamp corresponding to the mid-point of the profile',
                'long_name':         'Profile Center Time',
                'observation_type':  'calculated',
                'platform':          'platform',
                'standard_name':     'time'
            },
            'profile_time_start': {
                'comment':
                'Timestamp corresponding to the start of the profile',
                'long_name':         'Profile Start Time',
                'observation_type':  'calculated',
                'platform':          'platform',
                'standard_name':     'time'
            },
            'profile_time_end': {
                'comment':
                'Timestamp corresponding to the end of the profile',
                'long_name':         'Profile End Time',
                'observation_type':  'calculated',
                'platform':          'platform',
                'standard_name':     'time'
            },
            'profile_lat': {
                'comment':
                ('Value is interpolated to provide an estimate of ' +
                 'the latitude at the mid-point of the profile'),
                'long_name':         'Profile Center Latitude',
                'observation_type':  'calculated',
                'platform':          'platform',
                'standard_name':     'latitude',
                'units':             'degrees_north',
                'valid_max':  90.0,
                'valid_min': -90.0
            },
            'profile_lon': {
                'comment':
                ('Value is interpolated to provide an estimate of ' +
                 'the longitude at the mid-point of the profile'),
                'long_name':         'Profile Center Longitude',
                'observation_type':  'calculated',
                'platform':          'platform',
                'standard_name':     'longitude',
                'units':             'degrees_east',
                'valid_max':  180.0,
                'valid_min': -180.0
            },
            'u': {
                'comment':
                ('The depth-averaged current is an estimate of the net ' +
                 'current measured while the glider is underwater.  The' +
                 ' value is calculated over the entire underwater segment,' +
                 ' which may consist of 1 or more dives.'),
                'long_name':
                'Depth-Averaged Eastward Sea Water Velocity',
                'observation_type':  'calculated',
                'platform':          'platform',
                'standard_name':     'eastward_sea_water_velocity',
                'units':             'm s-1',
                'valid_max':  10.0,
                'valid_min': -10.0
            },
            'v': {
                'comment':
                ('The depth-averaged current is an estimate of the net ' +
                 'current measured while the glider is underwater.  The' +
                 ' value is calculated over the entire underwater segment,' +
                 ' which may consist of 1 or more dives.'),
                'long_name':
                'Depth-Averaged Northward Sea Water Velocity',
                'observation_type':  'calculated',
                'platform':          'platform',
                'standard_name':     'northward_sea_water_velocity',
                'units':             'm s-1',
                'valid_max':  10.0,
                'valid_min': -10.0
            },
            'lon_uv': {
                'comment':
                ('The depth-averaged current is an estimate of the net ' +
                 'current measured while the glider is underwater.  The' +
                 ' value is calculated over the entire underwater segment,' +
                 ' which may consist of 1 or more dives.'),
                'long_name':         'Depth-Averaged Longitude',
                'observation_type':  'calculated',
                'platform':          'platform',
                'standard_name':     'longitude',
                'units':             'degrees_east',
                'valid_max':  180.0,
                'valid_min': -180.0
            },
            'lat_uv': {
                'comment':
                ('The depth-averaged current is an estimate of the net ' +
                 'current measured while the glider is underwater.  The' +
                 ' value is calculated over the entire underwater segment,' +
                 ' which may consist of 1 or more dives.'),
                'long_name':         'Depth-Averaged Latitude',
                'observation_type':  'calculated',
                'platform':          'platform',
                'standard_name':     'latitude',
                'units':             'degrees_north',
                'valid_max':  90.0,
                'valid_min': -90.0
            },
            'time_uv': {
                'comment':
                ('The depth-averaged current is an estimate of the net ' +
                 'current measured while the glider is underwater.  The' +
                 ' value is calculated over the entire underwater segment,' +
                 ' which may consist of 1 or more dives.'),
                'long_name':        'Depth-Averaged Time',
                'standard_name':    'time',
                'calendar':         'gregorian',
                'units':            'seconds since 1970-01-01T00:00:00Z',
                'observation_type': 'calculated'
            },
            'instrument_ctd': {
                'comment':    'pumped CTD',
                'calibration_date':
                self.excel_metadata['ctd_cal'].strftime('%Y-%m-%dT%H:%M:%SZ'),
                'calibration_report':   '" "',
                'factory_calibrated':
                self.excel_metadata['ctd_cal'].strftime('%Y-%m-%dT%H:%M:%SZ'),
                'long_name':           'Seabird Glider Payload CTD',
                'make_model':
                'Seabird ' + self.excel_metadata['ctd_type'],
                'platform':            'platform',
                'serial_number':       f'{self.excel_metadata['ctd_sn']}',
                'type':                'platform'
            },
        }

        # add from user input (overwrite as necessary)
        if profile_variables is not None:
            for name, value in profile_variables.items():
                self._add_profile_variable(name, value)

    def add_qartod_tests(self, qartod_tests=None):
        """
        add DeploymentYAML.qartod_tests: metadata for QARTOD tests to perform
            gross range tests to variables with valid_min, valid_max in
            netcdf_variables spike, rate of change, and flat line tests
            to variables with resolution in netcdf_variables
        """
        _log.info('Adding QARTOD test metadata to deployment YAML')

        # if don't have NetCDF variable metadata already
        if not hasattr(self, 'netcdf_variables'):
            raise AttributeError('Must have NetCDF variable metadata to' +
                                 ' construct YAML. See method' +
                                 ' add_netcdf_variables')

        # initialize with instrument limits
        for variable in self.netcdf_variables:
            if ('valid_min' in self.netcdf_variables[variable] and
               'valid_max' in self.netcdf_variables[variable]):
                self._add_qartod_test(variable=variable,
                                      test='gross_range_test', parameters={
                                       'fail_span':
                                       [self.netcdf_variables[variable]
                                        ['valid_min'],
                                        self.netcdf_variables[variable]
                                        ['valid_max']]})

                if 'resolution' in self.netcdf_variables[variable]:
                    res = self.netcdf_variables[variable]['resolution']
                    self._add_qartod_test(variable=variable,
                                          test='spike_test', parameters={
                                              'suspect_threshold': res * 100.0,
                                              'fail_threshold': res * 200.0})

                    self._add_qartod_test(variable=variable,
                                          test='rate_of_change_test',
                                          parameters={'threshold': res * 2.5})

                    self._add_qartod_test(variable=variable,
                                          test='flat_line_test',
                                          parameters={'suspect_threshold': 150,
                                                      'fail_threshold': 300,
                                                      'tolerance': res})

        # add from user input (overwrite as necessary)
        if qartod_tests is not None and type(qartod_tests) is not bool:
            for variable, test_parameters in qartod_tests.items():
                for test, parameters in test_parameters.items():
                    self._add_qartod_test(variable, test, parameters)

    def construct_yaml(self, excelsheet=None, ID=None, qartod_tests=None,
                       metadata=None, glider_devices=None,
                       netcdf_variables=None, profile_variables=None):
        """
        use Excel sheet output to build YAML output

        provide deployment ID during initialization of DeploymentYAML class or
        provide it here additionally provide metadata, glider_devices,
        netcdf_variables,profile_variables in form {'name':value} to overwrite
        or add to default values qartod_tests=False will skip adding tests
        additionally provide qartod_tests in form
        {'variable':{'test':parameters}} to add additional tests

        supplying inputs here will overwrite what was given during
        initialization or during any previous individually called steps
        """
        # if gave inputs, overwrite any previous/assign
        if excelsheet is not None:
            self.excelsheet = excelsheet
            if hasattr(self, 'excel_metadata'):
                delattr(self, 'excel_metadata')
        if ID is not None:
            self.ID = ID
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
                self.add_excel_metadata(self.excelsheet, self.ID)
            # no sheet to read
            else:
                # stop running
                raise AttributeError('Must have Excel worksheet metadata ' +
                                     'to construct YAML. See method ' +
                                     'collect_excelsheet_metadata or provide' +
                                     ' key "excelsheet"')

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

    def write_yaml(self, outname='deployment_metadata.yml'):
        """
        write yaml dictionary to YAML file
        """
        # assign input
        self.outname = outname

        # make sure have necessary variables
        if not hasattr(self, 'yaml'):
            raise AttributeError('Must have constructed an output yaml ' +
                                 'dictionary. See method construct_yaml')

        # write out
        _log.info(f'Wrting deployment YAML for {self.ID} as {self.outname}')
        with open(self.outname, 'w') as outfile:
            yaml.dump(self.yaml, outfile, default_flow_style=False)

    def _check_for_excel_meta(self):
        """
        check to make sure there is Excel metadata already loaded
        internal; used by many steps
        """
        _log.debug('Checking for existing Excel worksheet metadata')
        # if don't have Excel sheet metadata already
        if not hasattr(self, 'excel_metadata'):
            raise AttributeError('Must have Excel worksheet metadata to ' +
                                 'construct YAML. See method ' +
                                 'collect_excelsheet_metadata')

    def _add_meta(self, name, value):
        """
        add to dictionary of metadata in DeploymentYAML
        internal; DeploymentYAML.metadata fills after getting metadata from
        Excel sheet or inputing additional 'metadata'
        """
        _log.debug(f'Adding {name} to metadata')
        self.metadata[name] = value

    def _add_glider_device(self, name, value):
        """
        add to dictionary of device metadata in DeploymentYAML
        internal; DeploymentYAML.glider_devices fills after getting metadata
        from Excel sheet or inputing additional 'glider_devices'
        """
        _log.debug(f'Adding {name} to device metadata')
        self.glider_devices[name] = value

    def _add_netcdf_variable(self, name, value):
        """
        add to dictionary of variable mapping metadata in DeploymentYAML
        internal; DeploymentYAML.netcdf_variables fills after getting metadata
        from Excel sheet or inputing additional 'netcdf_variables'
        """
        _log.debug(f'Adding {name} to variable mapping metadata')
        self.netcdf_variables[name] = value

    def _add_profile_variable(self, name, value):
        """
        add to dictionary of profile variable mapping metadata in
        DeploymentYAML internal; DeploymentYAML.profile_variables fills after
        getting metadata from Excel sheet or inputing additional
        'profile_variables'
        """
        _log.debug(f'Adding {name} to profile variable mapping metadata')
        self.profile_variables[name] = value

    def _add_qartod_test(self, variable, test, parameters):
        """
        add to dictionary of QARTOD tests to perform in DeploymentYAML
        internal; DeploymentYAML.qartod_tests fills if given input
        'qartod_tests' (or if 'qartod_tests' is True)
        """
        _log.debug(f'Adding {variable} to QARTOD test metadata')
        try:
            self.qartod_tests['streams'][variable]['qartod'][test] = parameters
        except:
            try:
                self.qartod_tests['streams'][variable] = (
                    {'qartod': {test: parameters}})
            except:
                self.qartod_tests = (
                    {'streams': {variable: {'qartod': {test: parameters}}}})
        # this part will only be necessary/useful if pyglider and
        # ioos_qc cooperate
        try:
            self.netcdf_variables[variable]['ancillary_variables'] += (
                f'{variable}_qartod_{test} ')
        except:
            self.netcdf_variables[variable]['ancillary_variables'] = (
                f' {variable}_qartod_{test} ')


class DeploymentNetCDF():
    """
    class with methods for making and reading NetCDFs in IOOS Glider DAC form
    """

    def __init__(self, main_directory, binary_directory='raw',
                 cache_directory='cache',
                 deployment_yaml='deployment_metadata.yml'):
        """
        initialize class with directory and file pathnames
        all are relative to main_directory
        """
        # assign inputs
        self.main_directory = main_directory
        self.binary_directory = join_path(main_directory, binary_directory)
        self.cache_directory = join_path(main_directory, cache_directory)
        self.deployment_yaml = join_path(main_directory, deployment_yaml)

    def read_timeseries(self, timeseries_file):
        """
        read a timeseries NetCDF created by L0 or L1
        filename is relative to main_directory
        """
        timeseries_file = join_path(self.main_directory, timeseries_file)
        _log.info(f'Reading {timeseries_file} into memory')
        with xr.open_dataset(timeseries_file) as ds:
            return ds

    def read_profiles(self, profile_directory):
        """
        read a directory of profile NetCDFs as a single dataset
        directory name is relative to main_directory
        """
        profile_directory = join_path(self.main_directory, profile_directory,
                                      '*.nc')
        _log.info(f'Reading all files in {profile_directory} into memory')
        with xr.open_mfdataset(profile_directory) as ds:
            return ds

    def L0(self, style=None, search=None, profile_filt_time=None,
           profile_min_time=None, l0timeseries_directory='L0-timeseries',
           l0profile_directory='L0-profiles'):
        """
        create the L0 timeseries and profile NetCDFs
        give l0profile_directory None or False to skip writing profile NetCDFs
        """
        # assign inputs
        self.l0timeseries_directory = join_path(self.main_directory,
                                                l0timeseries_directory)
        if l0profile_directory:
            self.l0profile_directory = join_path(self.main_directory,
                                                 l0profile_directory)
        else:
            self.l0profile_directory = l0profile_directory
        match style:
            case 'realtime':
                self.search = '*.[s|t]bd'
                self.profile_filt_time = 20
                self.profile_min_time = 60
            case 'delayed':
                self.search = '*.[d|e]bd'
                self.profile_filt_time = 100
                self.profile_min_time = 300
            case None:
                if search is not None:
                    self.search = search
                else:
                    raise KeyError('Must provide either "style" or "search",' +
                                   '"profile_filt_time","profile_min_time"')
                if profile_filt_time is not None:
                    self.profile_filt_time = profile_filt_time
                else:
                    raise KeyError('Must provide either "style" or "search",' +
                                   '"profile_filt_time","profile_min_time"')
                if profile_min_time is not None:
                    self.profile_min_time = profile_min_time
                else:
                    raise KeyError('Must provide either "style" or "search",' +
                                   '"profile_filt_time","profile_min_time"')
            case _:
                raise ValueError('Input "style" must be "realtime", ' +
                                 '"delayed", or None')

        # turn binary *.*bd (file extension based on search) into a single
        # timeseries netcdf file
        self.l0timeseries_outname = slocum.binary_to_timeseries(
            self.binary_directory, self.cache_directory,
            self.l0timeseries_directory, self.deployment_yaml,
            search=self.search, profile_filt_time=self.profile_filt_time,
            profile_min_time=self.profile_min_time)
        _log.info('Created L0 single timeseries NetCDF ' +
                  f'{self.l0timeseries_outname}')

        # make profile netcdf files
        if self.l0profile_directory:
            _log.info('Creating L0 profile NetCDFs in ' +
                      f'{self.l0profile_directory}')
            ncprocess.extract_timeseries_profiles(
                self.l0timeseries_outname, self.l0profile_directory,
                self.deployment_yaml)

    def L1(self, l1timeseries_directory='L1-timeseries',
           l1profile_directory='L1-profiles'):
        """
        create the L1 timeseries and profile NetCDFs
        give l1profile_directory None or False to skip writing profile NetCDFs
        """
        # assign inputs
        self.l1timeseries_directory = join_path(self.main_directory,
                                                l1timeseries_directory)
        if l1profile_directory:
            self.l1profile_directory = join_path(self.main_directory,
                                                 l1profile_directory)
        else:
            self.l1profile_directory = l1profile_directory

        # make sure output directory exists
        if not exists(self.l1timeseries_directory):
            makedirs(self.l1timeseries_directory)

        # make sure already have an L0
        if not hasattr(self, 'l0timeseries_outname'):
            raise AttributeError('No L0 timeseries file exists. Must ' +
                                 'run DeploymentNetCDF.L0 before ' +
                                 'DeploymentNetCDF.L1')

        # create output name based on L0 name
        self.l1timeseries_outname = join_path(self.l1timeseries_directory,
                                              basename(
                                                  self.l0timeseries_outname))
        _log.info('Creating L1 single timeseries NetCDF ' +
                  f'{self.l1timeseries_outname}')

        # get configuration
        # output progress
        _log.info('Extracting QARTOD test parameters from' +
                  f' {self.deployment_yaml}')
        # get metadata from yaml
        with open(self.deployment_yaml) as fin:
            metadata = yaml.safe_load(fin)
        # use yaml configuration for ioos_qc configuration
        config = metadata['qartod_tests']
        c = Config(config)

        # perform qartod tests on L0 timeseries netcdf file to create L1
        # timeseries netcdf file
        # open dataset
        with xr.open_dataset(self.l0timeseries_outname) as inds:
            # output progress
            _log.info(f'Running QARTOD tests on {self.l0timeseries_outname}')
            # run initial tests
            xs = XarrayStream(inds, time='time', z='depth', lat='latitude',
                              lon='longitude')
            runner = list(xs.run(c))
            # group initial results by stream_id (variable)
            grouped_runner = ({k: list(g) for k, g
                               in groupby(runner, lambda r: r.stream_id)})
            # run aggregate tests and add to initial results
            for variable, run in grouped_runner.items():
                result = collect_results(run)
                agg = ContextResult(
                    stream_id=variable,
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
            # export
            CFNetCDFStore(runner).save(
                # The netCDF file to export
                self.l1timeseries_outname,
                # The DSG class to save the results as
                OrthogonalMultidimensionalTimeseries,
                # The QC config that was run
                c,
                # Should we write the data or just metadata? Defaults to false
                write_data=False,
                # Compute a total aggregate?
                compute_aggregate=False,
                # Any kwargs to pass to the DSG class
                dsg_kwargs=dict(
                    reduce_dims=True,  # Remove dimensions of size 1
                    unlimited=False,  # Don't make the record dimension
                                      # unlimited
                    unique_dims=True,  # Support loading into xarray
                ),
            )
            # output progress
            _log.info('Saving QARTOD test results as ' +
                      f'{self.l1timeseries_outname}')
            # merge with original, adjusting things that ioos_qc changed
            with xr.open_dataset(self.l1timeseries_outname) as ds:
                ds = ds.swap_dims(
                    {'time_dim': 'time'}).drop_vars([('z', 'lon', 'lat',
                                                     'crs', 'station')])
                outds = inds.reset_coords().combine_first(ds)
            # rearrange to be like expected Glider DAC
            for variable in outds.data_vars:
                if '_qc' in variable or '_qartod' in variable:
                    outds[variable] = outds[variable].astype('byte')
                    if '_qc' in variable:
                        attrs = outds[variable].attrs
                        if 'ioos_qc_module' in attrs:
                            del attrs['ioos_qc_module']
                        if 'ioos_qc_test' in attrs:
                            del attrs['ioos_qc_test']
                        if 'ioos_qc_target' in attrs:
                            del attrs['ioos_qc_target']
                        outds[variable] = outds[variable].assign_attrs(
                            _FillValue=int(-127),
                            flag_meanings=('no_qc_performed good_data ' +
                                           'probably_good_data ' +
                                           'bad_data_that_are_' +
                                           'potentially_correctable' +
                                           ' bad_data value_changed not_used' +
                                           ' not_used interpolated_value ' +
                                           'missing_value'),
                            flag_values=[int(x) for x in range(0, 10)],
                            long_name='Quality Flag',
                            standard_name='status_flag',
                            valid_max=int(9),
                            valid_min=int(0)
                        )
                    else:
                        outds[variable] = outds[variable].assign_attrs(
                            _FillValue=int(-127),
                            flag_values=([int(x) for x in range(1, 5)] +
                                         [int(9)]),
                            valid_max=int(9),
                            valid_min=int(0)
                        )
                else:
                    outds[variable] = (
                        outds[variable].astype('double').assign_attrs(
                                        _FillValue=-999.0
                                        ))
                outds[variable] = (
                    outds[variable].fillna(
                        outds[variable].attrs['_FillValue']))
        # output new L1 NetCDF
        outds.to_netcdf(self.l1timeseries_outname)

        # make L1 profile NetCDF files for IOOS GliderDAC
        if self.l1profile_directory:
            _log.info('Creating L1 profile NetCDFs in' +
                      f' {self.l1profile_directory}')
            ncprocess.extract_timeseries_profiles(self.l1timeseries_outname,
                                                  self.l1profile_directory,
                                                  self.deployment_yaml)

    def check_profiles(self, profile_directory):
        """
        use the IOOS compliance checker on profile files produced in L0 or L1
        filenames are relative to main_directory
        only do ones that haven't been checked
        outputs passing state of each file checked
        """
        profile_directory = join_path(self.main_directory, profile_directory)
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

        # initialize compliance checker
        check_suite = CheckSuite()
        check_suite.load_all_available_checkers()
        checker = ComplianceChecker()

        # run compliance checker for each file
        passed = [False] * len(file_names)
        for f in file_names:
            # make true file name
            f = f.split('.')[0]
            f = join_path(profile_directory, f)
            # if report doesn't already exist
            if not exists(f+'_report.txt'):
                _log.debug(f'Checking {f}.nc')
                # check
                passed, _ = checker.run_checker(
                    ds_loc=f+'.nc',
                    output_filename=f+'_report.txt',
                    checker_names=['gliderdac'],
                    verbose=log_level,
                    criteria='normal'
                )
                # output
                if passed:
                    isnot = 'is'
                else:
                    isnot = 'is not'
                _log.info(f'{f}.nc {isnot} IOOS GliderDAC compliant.' +
                          f' See {f}_report.txt for details.')

        # output
        return passed, file_names

    def create_summary(self, timeseries_file, output_file, author='Anonymous',
                       extra_text=None, map_bounds=None,
                       plots=({'source': 'temperature',
                               'cmap': 'cmocean.sequential.Thermal_20'},
                              {'source': 'salinity',
                               'cmap': 'cmocean.sequential.Haline_20'},
                              {'source': 'density',
                               'cmap': 'cmocean.sequential.Dense_20'})):
        """
        output a summary page from a timeseries NetCDF file
        filenames are relative to main_directory
        map_bounds in [minimum latitude, maximum latitude, minimum longitude,
        maximum longitude] form map_bounds=None will define based on data
        specify 3 subplots, in order of top to bottom, with palettable
        colortables
        """
        timeseries_file = join_path(self.main_directory, timeseries_file)
        output_file = join_path(self.main_directory, output_file)
        _log.info(f'Creating {output_file}')

        # get metadata from deployment YAML
        with open(self.deployment_yaml) as fin:
            metadata = yaml.safe_load(fin)
            metadata = metadata['metadata']
        # get data from timeseries NetCDF
        data = self.read_timeseries(timeseries_file)

        # create additional header info
        title = ('Ocean Glider Deployment Summary: ' +
                 f'{metadata['deployment_name']} - {metadata['project']}')
        date = datetime.today().strftime('%d %B, %Y')

        # #create "snapshot": text table of select metadata
        # start/end location
        loc = []
        lat = data['latitude'].values
        lon = data['longitude'].values
        for lat, lon in zip([first_nonnan(lat), last_nonnan(lat)],
                            [first_nonnan(lon), last_nonnan(lon)]):
            lat_deg, lat_min = dd2dm(lat)
            if lat_deg < 0:
                ns = 'S'
                lat_deg *= -1
            else:
                ns = 'N'
            lon_deg, lon_min = dd2dm(lon)
            if lon_deg < 0:
                ew = 'W'
                lon_deg *= -1
            else:
                ew = 'E'
            loc.append(f"{lat_deg:.0f}\xb0{lat_min:.02f}'{ns}," +
                       f"{lon_deg:.0f}\xb0{lon_min:.02f}'{ew}")
        # deployment duration
        duration = data['time'].values[-1]-data['time'].values[0]
        dys = duration.astype('timedelta64[D]').astype(np.int32)
        hrs = duration.astype('timedelta64[h]').astype(np.int32) % 24
        duration = f'{dys} days, {hrs} hours'
        # science sensors output
        sci_vars = list(data.data_vars)
        [sci_vars.remove(v) for v in ['heading', 'pitch', 'roll', 'pressure',
                                      'water_velocity_eastward',
                                      'water_velocity_northward',
                                      'distance_over_ground', 'profile_index',
                                      'profile_direction']]
        sci_vars = [data[v].attrs['long_name'] for v in sci_vars]
        # construct
        snapshot = (
            [
                'Deployment date',
                'Deployment location',
                'Retrieval date',
                'Retrieval location',
                'Deployment duration',
                'Science sensors'
            ] +
            [' ' for _ in range(len(sci_vars)-1)] +
            ['Number of profiles',
                'Glider name',
                'Profiling range',
                'Max depth reached',
                'Distance covered'
             ],
            [
                np.datetime_as_string(data['time'].values[0], unit='s',
                                      timezone='UTC'),
                loc[0],
                np.datetime_as_string(data['time'].values[-1], unit='s',
                                      timezone='UTC'),
                loc[1],
                duration] +
            sci_vars +
            [f'{max(data['profile_index'].values):.0f}',
                metadata['glider_name'],
                f'0-{metadata['glider_pump']}',
                f'{np.nanmax(data['depth'].values):.02f}m',
                f'{data['distance_over_ground'].values[-1]:.02f}km'
             ]
        )

        # #define map limits
        if map_bounds is not None:
            min_lat = map_bounds[0]
            max_lat = map_bounds[1]
            min_lon = map_bounds[2]
            max_lon = map_bounds[3]
        else:
            min_lat = np.nanmin(data['latitude'].values) - 1
            max_lat = np.nanmax(data['latitude'].values) + 1
            min_lon = np.nanmin(data['longitude'].values) - 2
            max_lon = np.nanmax(data['longitude'].values) + 2

        # #create summary page
        # initialize
        fig = pygmt.Figure()
        # define gmt processing debug output level based on user's selected log
        # level
        match _log.root.level:
            case 10:
                # DEBUG
                log_level = 'd'
            case 20:
                # INFO
                log_level = 'i'
            case 30:
                # WARNING
                log_level = 'w'
            case 40:
                # ERROR
                log_level = 'e'
            case _:
                # everything else
                log_level = 'w'
        # define gmt setup
        pygmt.config(
            PS_MEDIA='a4', FONT_ANNOT_PRIMARY=8, FONT_LABEL=8,
            PROJ_LENGTH_UNIT='c', MAP_FRAME_TYPE='plain',
            MAP_TICK_PEN='black', MAP_FRAME_PEN='thinnest,black',
            GMT_VERBOSE=log_level
        )
        # define map common paramters
        avg_lat = np.mean([min_lat, max_lat])
        avg_lon = np.mean([min_lon, max_lon])
        z_levels = ','.join([str(num) for num in
                             [*range(0, 901, 100)]+[*range(1000, 6001, 1000)]])
        zone = from_latlon(avg_lat, avg_lon)
        zone = f'{zone[2]}{zone[3]}'
        # define Hovmoller diagram common parameters
        min_time = np.nanmin(data['time'].values)
        max_time = np.nanmax(data['time'].values)
        min_depth = 0
        max_depth = np.nanmax(data['depth'].values)
        region = [min_time, max_time, min_depth, max_depth]
        height = 5.5
        projection = f'X18/-{height}'
        frame = ['af', 'x+lTime', 'y+lDepth (m)']
        yshifts = [1, 6.75, 12.5]
        xaxis = ['S', 's', 's']
        _log.debug('Using map and plot boundaries\n' +
                   '\tminimum\n' +
                   f'\t\tlatitude {min_lat}\n' +
                   f'\t\tlongitude {min_lon}\n' +
                   f'\t\ttime {min_time}\n' +
                   f'\t\tdepth {min_depth}\n' +
                   '\tmaximum\n' +
                   f'\t\tlatitude {max_lat}\n' +
                   f'\t\tlongitude {max_lon}\n' +
                   f'\t\ttime {max_time}\n' +
                   f'\t\tdepth {max_depth}\n' +
                   '\taverage\n' +
                   f'\t\tlatitude {avg_lat}\n' +
                   f'\t\tlongitude {avg_lon}'
                   )
        # Hovmoller diagrams
        fig.shift_origin(xshift='f1.25')
        for dy, var, s in zip(yshifts, plots[::-1], xaxis):
            z = data[var['source']].values
            lbl = (f'{data[var['source']].attrs['long_name']}' +
                   f'({data[var['source']].attrs['units']})')
            _log.info(f'Adding {lbl} plot to summary page')
            pygmt.makecpt(cmap=temporary_cpt(palette=var['cmap']),
                          series=[np.nanmin(z), np.nanmax(z)])
            fig.shift_origin(yshift=f'f{dy}')
            fig.basemap(region=region, projection=projection,
                        frame=frame+[f'We{s}n+ggray90'])
            fig.plot(
                x=data['time'].values,
                y=data['depth'].values,
                fill=z,
                cmap=True,
                style='c0.5p'
            )
            fig.colorbar(cmap=True, frame=['af', f'x+l{lbl}'],
                         position=f'jBR+w{height}+o-0.5/0')
        # main map
        _log.info('Adding map to summary page')
        fig.shift_origin(xshift='f0.25', yshift='f18.325')
        pygmt.makecpt(cmap=temporary_cpt(palette=('colorbrewer.sequential.' +
                                                  'Blues_9')), series=z_levels)
        fig.grdimage(
            region=f'{min_lon}/{min_lat}/{max_lon}/{max_lat}+r',
            projection=f'U{zone}/10.25',
            frame=['wEsN', 'af'],
            grid='GB_bathy5m.nc', cmap=True
        )
        fig.coast(land='white', shorelines=True)
        pygmt.makecpt(cmap=temporary_cpt(palette='cmocean.sequential.Amp_20'),
                      series=[min_time, max_time])
        fig.plot(
            x=data['longitude'].values,
            y=data['latitude'].values,
            fill=data['time'].values, cmap=True,
            style='c2p'
        )
        fig.basemap(frame='lrbt')
        # inset map
        fig.shift_origin(xshift='f0.5', yshift='f18.75')
        pygmt.makecpt(cmap=temporary_cpt(palette=('colorbrewer.sequential' +
                                                  '.Blues_9'),
                      series=z_levels))
        fig.grdimage(
            region='g', projection=f'G{avg_lon}/{avg_lat}/10/3', frame='g10',
            grid='GB_bathy10m.nc', cmap=True
        )
        fig.coast(land='white', shorelines=True)
        fig.plot(
            x=[max_lon, max_lon, min_lon],
            y=[min_lat, max_lat, max_lat],
            close=f'+x{min_lon}+y{min_lat}+pthin,red'
        )
        # metadata text box
        _log.info('Adding metadata snapshot to summary page')
        _log.debug(f'Using text\n{snapshot}')
        fig.shift_origin(xshift='f13.75', yshift='f18.325')
        fig.basemap(region=[0, 1, 0, len(snapshot[0])+1], projection='X7/-9.5',
                    frame='lbtr+ggray95')
        for col, text in enumerate(snapshot):
            fig.text(x=np.ones(len(text))*0.325*col, y=range(1, len(text)+1),
                     text=text, justify='LM', offset='0.25/0', font=6)
        pygmt.makecpt(cmap=temporary_cpt(palette='cmocean.sequential.Amp_20'),
                      series=[min_time, max_time])
        fig.colorbar(cmap=True, frame=['af', 'x+lTime'],
                     position='jBL+w9.5+o-1/0+ma')
        # title, author, date, extra text
        _log.info('Adding header information to summary page')
        debug_text = 'Using\n' +\
            f'\ttitle {title}\n' +\
            f'\tauthor {author}\n' +\
            f'\tdate {date}'
        if extra_text is not None:
            debug_text += f'\n\ttext {extra_text}'
        _log.debug(debug_text)
        fig.shift_origin(xshift='f0', yshift='f28')
        fig.basemap(region=[-1, 1, -1.5, 1.5], projection='X21/1.75',
                    frame='b')
        fig.text(x=0, y=0.5, text=title, font=12, justify='BC')
        fig.text(x=0, y=0, text=f'Prepared by {author} on {date}',
                 justify='MC')
        if extra_text is not None:
            with NamedTemporaryFile(mode='w', suffix='.txt',
                                    delete_on_close=False) as f:
                f.write(f'> 0 -0.5 8p 18 c\n{extra_text}')
                f.close()
                fig.text(textfiles=f.name, font=8, justify='TC', M=True)
        # save
        _log.info(f'Saving summary page as {output_file}')
        fig.savefig(output_file, crop=False)
