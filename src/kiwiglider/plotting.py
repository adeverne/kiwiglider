"""Utilities for plotting Slocum glider data the Kiwi way"""
import logging
from tempfile import NamedTemporaryFile
from datetime import datetime
import xarray as xr
import numpy as np
import pygmt
from utm import from_latlon
from distinctipy import get_colors, get_colormap
from importlib import import_module  # used to import from palettable
from kiwiglider.colormap import MPLWrapperColormap
from kiwiglider.utils import dd2dm, first_nonnan, last_nonnan


_log = logging.getLogger(__name__)


def temporary_cpt(
        palette: str = None,
        num_colors: int = None,
        seed: int = 1,
        background: list[float] | str = None
) -> MPLWrapperColormap:
    """Create a temporary .cpt for use with PyGMT.

    Note
    ----
    Must specify either
        palette
            or
        num_colors (with optional seed and background)

    Parameters
    ----------
    palette : str, optional
        Path for palettable class
        (ex. colorbrewer.sequential.Blues_9).
    num_colors : int, optional
        Number of distinguishable colors in palette.
    seed : int, optional
        Random seed.
    background : list[float] | str, optional
        List of RGB (in 0-1) or palattable class path
        to exclude from distinct colors.

    Returns
    -------
    MPLWrapperColormap
        Color palette to use as cmap in PyGMT

    """
    if palette:
        if type(palette) is not str:
            raise TypeError('Input "palette" must be a string')

        palette = palette.split('.')
        cpt = getattr(import_module('.'.join(['palettable']+palette[:-1])),
                      palette[-1]).mpl_colormap
    elif num_colors:
        if type(num_colors) is not int:
            raise TypeError('Input "num_colors" must be an integer')
        if type(seed) is not int:
            raise TypeError('Input "seed" must be an integer')
        if type(background) is str:
            background = background.split('.')
            background = getattr(import_module(
                '.'.join(['palettable'] + background[:-1])),
                background[-1]).mpl_colors
        elif type(background) is list or background is None:
            pass
        else:
            raise TypeError('Input "background" must be a list or string')

        cpt = get_colormap(
            get_colors(num_colors, rng=seed, exclude_colors=background)
        )
    else:
        raise ValueError('Must input either "palette" or "num_colors"')

    return MPLWrapperColormap(cpt)


def create_deployment_summary(
        data: xr.Dataset,
        output_file: str = False,
        display: bool = True,
        author: str = 'Anonymous',
        extra_text: str = '',
        map_bounds: list[float] = None,
        time_bounds: list[str] = None,
        globe_position: str = 'BL',
        plots: tuple[dict[str, str]] = (
            {'source': 'temperature',
                'cmap': 'cmocean.sequential.Thermal_20'},
            {'source': 'salinity',
                'cmap': 'cmocean.sequential.Haline_20'},
            {'source': 'density',
                'cmap': 'cmocean.sequential.Dense_20'}
        )
):
    """Output a summary page from a timeseries NetCDF file.

    Parameters
    ----------
    data : xr.Dataset
        Dataset loaded from `kiwiglider` timeseries NetCDF file.
    output_file : str, optional
        Full path for output PNG file.
        If False, will not write a file.
    display : bool, optional
        Whether to display the summary in default viewer.
    author : str, optional
        Name of the person creating the summary page.
    extra_text : str, optional
        Any text to add on the same line as funding acknowledgement
        (ex. glider faults during the mission).
    map_bounds : list[float], optional
        Map bounds in form
        [minimum latitude, maximum latitude,
        minimum longitude, maximum longitude].
        Specify None (default) to define based on data.
    time_bounds : list[str], optional
        Time bounds in form [minimum time, maximum time]
        Specify None (default) to define based on data.
    globe_position : str, optional
        Position on map for overview globe. Use codes in terms of
        (T)op, (M)iddle, (B)ottom and
        (L)eft, (C)enter, (R)ight.
    plots : tuple[dict[str, str]], optional
        Three subplots, in order of top to bottom,
        with palettable colortables in form
        {'source': 'variable_name',
        'cmap': 'path.to.colortable'}.

    """

    _log.info('Creating summary page')

    # extract metadata
    metadata = data.attrs

    # create additional header info
    title = ('Ocean Glider Deployment Summary: ' +
             f'{metadata['deployment_name']} - {metadata['project']}')
    date = datetime.today().strftime('%d %B, %Y')
    extra_text = f'{metadata['acknowledgement']}. {extra_text}'

    # trim time if requested
    if time_bounds is not None:
        data = data.sel(
            time=slice(np.datetime64(time_bounds[0]),np.datetime64(time_bounds[1]))
        )

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
        loc.append(f"{lat_deg:.0f}\xb0{lat_min:.02f}'" +
                   f"{ns},{lon_deg:.0f}\xb0{lon_min:.02f}'{ew}")
    # deployment duration
    duration = data['time'].values[-1]-data['time'].values[0]
    dys = duration.astype('timedelta64[D]').astype(np.int32)
    hrs = duration.astype('timedelta64[h]').astype(np.int32) % 24
    duration = f'{dys} days, {hrs} hours'
    # science sensors output
    sci_vars = list(data.data_vars)
    [sci_vars.remove(v) for v in [
        'latitude', 'longitude', 'heading', 'pitch', 'roll', 'pressure',
        'depth', 'water_velocity_eastward', 'water_velocity_northward',
        'distance_over_ground', 'profile_index', 'profile_direction'
    ]]
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
        [
            'Number of profiles',
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
            duration
        ] +
        sci_vars +
        [
            f'{np.nanmax(data['profile_index'].values):.0f}',
            metadata['glider_name'],
            f'0-{metadata['glider_pump']}',
            f'{np.nanmax(data['depth'].values):.02f}m',
            f'{data['distance_over_ground'].values[-1]:.02f}km'
        ]
    )

    # define map limits
    if map_bounds is not None:
        min_lat = map_bounds[0]
        max_lat = map_bounds[1]
        min_lon = map_bounds[2]
        max_lon = map_bounds[3]
    else:
        min_lat = np.floor(
            (np.nanmin(data['latitude'].values) - 0.5) * 10
        ) / 10
        max_lat = np.ceil(
            (np.nanmax(data['latitude'].values) + 0.5) * 10
        ) / 10
        min_lon = np.floor(
            (np.nanmin(data['longitude'].values) - 1) * 10
        ) / 10
        max_lon = np.ceil(
            (np.nanmax(data['longitude'].values) + 1) * 10
        ) / 10

    # initialize summary page
    fig = pygmt.Figure()
    # define gmt processing debug output level based on
    # user's selected log level
    match _log.root.level:
        # DEBUG
        case 10:
            # Debugging
            log_level = 'd'
        # everything else
        case _:
            # Warnings (GMT default)
            log_level = 'w'
    # define gmt setup
    pygmt.config(
        PS_MEDIA='a4', FONT_ANNOT_PRIMARY=8, FONT_LABEL=8,
        PROJ_LENGTH_UNIT='c', MAP_FRAME_TYPE='plain', MAP_TICK_PEN='black',
        MAP_FRAME_PEN='thinnest,black', GMT_VERBOSE=log_level
    )
    # define map common paramters
    avg_lat = np.mean([min_lat, max_lat])
    avg_lon = np.mean([min_lon, max_lon])
    z_levels = ','.join(
        [str(num) for num in [*range(0, 901, 100)] +
            [*range(1000, 6001, 1000)]]
    )
    zone = from_latlon(avg_lat, avg_lon)
    zone = f'{zone[2]}{zone[3]}'
    # define Hovmoller diagram common parameters
    min_time = np.nanmin(data['time'].values)
    max_time = np.nanmax(data['time'].values)
    min_depth = 0
    max_depth = np.nanmax(data['depth'].values)
    region = [min_time, max_time, min_depth, max_depth]
    height = 5.25
    projection = f'X18/-{height}'
    yshifts = [0.5, 6, 11.5]
    xaxis = ['S', 's', 's']
    _log.debug(
        'Using map and plot boundaries\n' +
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
    fig.shift_origin(xshift='f1')
    for dy, var, s in zip(yshifts, plots[::-1], xaxis):
        z = data[var['source']].values
        lbl = (f'{data[var['source']].attrs['long_name']} ' +
               f'({data[var['source']].attrs['units']})')
        _log.info(f'Adding {lbl} plot to summary page')
        pygmt.makecpt(
            cmap=temporary_cpt(palette=var['cmap']),
            background='o',
            series=[np.nanmean(z)-3*np.nanstd(z),
                    np.nanmean(z)+3*np.nanstd(z)]
        )
        fig.shift_origin(yshift=f'f{dy}')
        with pygmt.config(FONT_ANNOT_PRIMARY=6):
            fig.basemap(region=region, projection=projection,
                        frame=['af', 'y+lDepth (m)', 'We+ggray90'])
        fig.basemap(frame=['af', f'{s}n'])
        fig.plot(
            x=data['time'].values,
            y=data['depth'].values,
            fill=z, cmap=True,
            style='c0.5p'
        )
        with pygmt.config(FONT_ANNOT_PRIMARY=10, FONT_LABEL=12):
            fig.colorbar(cmap=True, frame=['af', f'x+l{lbl}'],
                         position=f'jBR+w{height}+o-0.5/0')
    # main map
    _log.info('Adding map to summary page')
    grid = pygmt.datasets.load_earth_relief(
        region=[min_lon-1, max_lon+1, min_lat-1, max_lat+1],
        resolution='15s', data_source='gebcosi'
    ) * -1
    fig.shift_origin(xshift='f0.5', yshift='f17.25')
    pygmt.makecpt(cmap=temporary_cpt(
        palette='colorbrewer.sequential.Blues_9'), background='o',
        series=z_levels)
    fig.grdimage(
        region=f'{min_lon}/{min_lat}/{max_lon}/{max_lat}+r',
        projection=f'U{zone}/10.25+du', frame=['wEsN', 'af'],
        grid=grid, cmap=True
    )
    fig.coast(land='white', shorelines=True)
    pygmt.makecpt(
        cmap=temporary_cpt(palette='cmocean.sequential.Amp_20'),
        background='o',
        series=[min_time, max_time]
    )
    fig.plot(
        x=data['longitude'].values,
        y=data['latitude'].values,
        fill=data['time'].values, cmap=True,
        style='c2p'
    )
    fig.basemap(frame='lrbt')
    # inset map
    grid = pygmt.datasets.load_earth_relief(
        resolution='10m', data_source='gebcosi'
    ) * -1
    with fig.inset(position=f'j{globe_position}+w2.75+o0.25'):
        pygmt.makecpt(
            cmap=temporary_cpt(palette='colorbrewer.sequential.Blues_9'),
            background='o',
            series=z_levels
        )
        fig.grdimage(
            region='g', projection=f'G{avg_lon}/{avg_lat}/10/?',
            frame='g10', grid=grid, cmap=True
        )
        fig.coast(land='white', shorelines=True)
        fig.plot(
            x=[max_lon, max_lon, min_lon],
            y=[min_lat, max_lat, max_lat],
            close=f'+x{min_lon}+y{min_lat}+pthin,red',
            straight_line='x'
        )
    # metadata text box
    _log.info('Adding metadata snapshot to summary page')
    _log.debug(f'Using text\n{snapshot}')
    fig.shift_origin(xshift='f13.75', yshift='f17.25')
    fig.basemap(
        region=[0, 1, 0, len(snapshot[0])+1],
        projection='X7/-10.5', frame='lbtr+ggray95'
    )
    for col, text in enumerate(snapshot):
        fig.text(
            x=np.ones(len(text))*0.375*col, y=range(1, len(text)+1),
            text=text, justify='LM', offset='0.25/0', font=7
        )
    # main map colorbar ("attached" to metadata text box for easier
    # position and sizing)
    pygmt.makecpt(
        cmap=temporary_cpt(palette='cmocean.sequential.Amp_20'),
        background='o', series=[min_time, max_time]
    )
    fig.colorbar(cmap=True, frame='af', position='jBL+w10.5+o-0.6/0+ma')
    # title, author, date, extra text
    _log.info('Adding header information to summary page')
    debug_text = 'Using\n' +\
        f'\ttitle {title}\n' +\
        f'\tauthor {author}\n' +\
        f'\tdate {date}\n' +\
        f'\ttext {extra_text}'
    _log.debug(debug_text)
    fig.shift_origin(xshift='f0', yshift='f28')
    fig.text(
        region=[-1, 1, -1.5, 1.5],
        projection='X21/1.75',
        x=0, y=0.5,
        text=title, font=12, justify='BC'
    )
    fig.text(
        x=0, y=0,
        text=(
            f'Deployed from {(data['time'].values[0]
                              .astype('datetime64[s]').item()
                              .strftime('%d %B, %Y'))} ' +
            (f'to {(data['time'].values[-1]
                    .astype('datetime64[s]').item()
                    .strftime('%d %B, %Y'))} ' +
             f'*** Prepared by {author} on {date}')
        ),
        justify='MC'
    )
    with NamedTemporaryFile(mode='w', suffix='.txt',
                            delete_on_close=False) as f:
        f.write(f'> 0 -0.5 8p 18 c\n{extra_text}')
        f.close()
        fig.text(textfiles=f.name, font=8, justify='TC', M=True)

    # save
    if output_file:
        _log.info(f'Saving summary page as {output_file}')
        fig.savefig(output_file, crop=False)
    # display
    if display:
        _log.info('Displaying summary page')
        fig.show(crop=False)
