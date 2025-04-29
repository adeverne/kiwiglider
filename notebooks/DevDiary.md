# Diary of KiwiGlider package development

## August 2024

This document is meant to provide future users a window into the thinking that went into the creation of any code existing in this kiwiglider repository. Initial work for this package was done by Cassandra Elmer and Alain de Verneil.

The intended structure of this package was brainstormed on a whiteboard and shown below:

![test](Whiteboard_Outline.jpg)

So, there are two main use functions for this code during Glider deployments:
1. Near-real-time. Much of the near-real-time functionality is inherited from the PyGlider package, and ameliorated to be compliant with external standards.
2. Delayed-time mode. We hope to make a one-stop shop for the post-processing of SLOCUM glider data as used at NIWA (and hopefully elsewhere, too 😃).

We're setting up this package to initially work with an assumed directory structure, hinted by the whiteboard but is as follows:

- 📁Deployment Directory
    - 📁Raw
        - *.[E/D]BD files
        - 📁Cache
            - CAC files
    - 📁Working
        - *.nc (Xarray output)
        - *.zarr (possibly)
        - *.npy files
        - *.mat files^
    - 📁Final
        - 📁netCDF
        - 📁mat^
        - 📁zarr^

^ File outputs to be generated will be specificed by user flag.

This structure reflects earlier packages, such as the SOCIB and GEOMAR toolboxes that already exist. The main reasons for creating this package are:
1. Use open-source python instead of matlab.
2. Leverage faster load times of raw data using DBDreader.
3. Combine approaches of multiple packages to (inshallah) provide more robust post-processing. In particular, we want to replicate the oxygen processing and flight model functionality provided by the GEOMAR toolbox.
4. Intermediate data will be in an xarray object that maintains metadata, allows for easy export to netCDF/Zarr, and can dovetail into the glidertools package.

#### April 10, 2025

Note: added jupyter notebook with post-processing journal.


