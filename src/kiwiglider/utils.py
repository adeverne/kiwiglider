"""
Utilities for processing Slocum glider files the Kiwi way
"""
from importlib import import_module  # used to import from palettable
import numpy as np
from distinctipy import get_colors, get_colormap
from kiwiglider.colormap import MPLWrapperColormap


def dd2dm(decimal_degrees: float) -> tuple[float, float]:
    """Convert decimal degrees to degree minute notation

    Note
    ----
    adapted from MATLAB's degrees2dm function

    Paramters
    ---------
    decimal_degrees : float
        Coordinate, either longitude or latitude, in decimal degrees

    Returns
    -------
    float
        Degree portion of input coordinate
    float
        Minute portion of input coordinate

    """
    degrees = np.fix(decimal_degrees)
    minutes = 60*np.remainder(np.abs(decimal_degrees), 1)
    return degrees, minutes


def dm2dd(degrees: float, minutes: float) -> float:
    """Convert degree minute to decimal degrees notation

    Note
    ----
    adapted from MATLAB's dm2degrees function

    Paramters
    ---------
    degrees : float
        Degree portion of input coordinate, either latitude or longitude
    minutes : float
        Minute portion of input coordinate, either latitude or longitude

    Returns
    -------
    float
        Coordinate in decimal degrees

    """
    decimal_degrees = np.abs(degrees) + np.abs(minutes)/60
    decimal_degrees = np.where(degrees < 0 or minutes < 0, decimal_degrees*-1,
                               decimal_degrees)
    return decimal_degrees


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
    ---------
    palette : str or None, optional
        Path for palettable class
        (ex colorbrewer.sequential.Blues_9)
    num_colors : int or None, optional
        Number of distinguishable colors in palette
    seed : int, optional
        Random seed
    background : list[float] | str, optional
        list of RGB (in 0-1) or palattable class path
        to exclude from distinct colors

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


def first_nonnan(numpy_array: np.array) -> float:
    """Get the first non-nan value in a numpy array.

    Parameters
    ----------
    numpy_array : numpy array
        Numpy array to search

    Returns
    -------
    float
        First non-nan value in array

    """
    return numpy_array[np.isfinite(numpy_array)][0]


def last_nonnan(numpy_array: np.array) -> float:
    """Get the last non-nan value in a numpy array.

    Parameters
    ----------
    numpy_array : numpy array
        Numpy array to search

    Returns
    -------
    float
        Last non-nan value in array

    """
    return numpy_array[np.isfinite(numpy_array)][-1]
