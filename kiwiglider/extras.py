#!/usr/bin/env python3
"""
KIWIGLIDER
Processing Slocum glider files the Kiwi way
Extra snippets of code useful for post-processing, plotting, etc.

Some packages that might need to be installed:
    - compliance_checker
    - pocean
    - pygmt
    - utm
    - distinctipy
"""

from importlib import import_module  # used to import from palettable
from distinctipy import get_colors, get_colormap
from colormap import MPLWrapperColormap


def temporary_cpt(palette=None, num_colors=None, seed=1, background=None):
    """
    Create a temporary .cpt for use with PyGMT.
    Input either a palettable palette name or an integer of distinguishable
    colors (with optional seed and background color list)

    Inputs:
    palette     :  str, palettable class path (ex
                                            colorbrewer.sequential.Blues_9)
    num_colors  :  int, number of distinguishable colors
    seed        :  int, random seed
    background  :  list, RGB (in 0-1) to exclude from distinct colors
                   str, palettable class path to exclude from distinct colors

    Outputs:
    temporary file to use as cmap in PyGMT
    """
    if palette:
        if not type(palette) is str:
            raise TypeError('Input "palette" must be a string')

        palette = palette.split('.')
        cpt = getattr(import_module('.'.join(['palettable']+palette[:-1])),
                      palette[-1]).mpl_colormap
    elif num_colors:
        if not type(num_colors) is int:
            raise TypeError('Input "num_colors" must be an integer')
        if not type(seed) is int:
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

        cpt = get_colormap(get_colors(num_colors, rng=seed,
                                      exclude_colors=background))
    else:
        raise ValueError('Must input either "palette" or "num_colors"')

    return MPLWrapperColormap(cpt)
