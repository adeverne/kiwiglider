""""
Module containing functions for generating the processing environment for
kiwiglider package. We follow this up with either reading in the YAML file
for the deployment, or autogenerating one from metadata.
"""

# Import necessary packages
import os
from glob import glob
import shutil
import sys
from datetime import datetime, UTC
import logging
from pyglider import slocum

_log = logging.getLogger(__name__)


def setup(rootdir: str, outdir: str = None, startdate: float = None,
          enddate: float = None) -> None:
    """ Master function that creates processing directory with copied and
        renamed raw data files and cache files.

    setup(rootDir: str, outDir: str = None, startDate: float = None,
          endDate: float = None, verbose: bool = True) -> None

    Parameters
    -----------
        rootDir : string
            Directory with raw EBD/DBD/SBD/TBD/CAC files for processing.
        outDir  : string
            Directory to which the subdirectory "Kiwi/Raw" will be created and
            copies of raw data and cache files to be sent.
        startDate : float, default = None
            POSIX timestamp (i.e. seconds since 1970-01-01Z00:00:00) indicating
            start of deployment.
        endDate : float, default = None
            POSIX timestamp (i.e. seconds since 1970-01-01Z00:00:00) indicating
            end of glider deployment.
    """
    _log.info("Initiated setup of Kiwiglider at %s",
              datetime.strftime(datetime.now(tz=UTC),
                                "%Y-5m-%d %H:%M:%S"))

    # INITIAL CHECKS
    # Check to see if provided rootdir argument exists and not "."
    if os.path.exists(rootdir) & (rootdir != "."):
        _log.info("Path {rootdir} passes initial test...")
    else:
        raise ValueError("This path either does not exist, or it is '.'," +
                         " which cannot be used. Please write full path.")

    # Make outdir rootdir by default
    if not outdir:
        outdir = rootdir

    kiwidir = os.path.join(outdir, "Kiwi")
    rawdir = os.path.join(kiwidir, "Raw")
    cachedir = os.path.join(rawdir, "Cache")

    # Check to see if Kiwi directory exists, if not create it.
    if os.path.exists(kiwidir):
        _log.info("Kiwi directory already exists.")
    else:
        _log.info("Creating Kiwi directory in rootdir")
        print("Creating directory for kiwiglider at: ")
        print(f"{kiwidir}")
        os.makedirs(kiwidir)

    # Check to see if Raw directory already exists, if not create it.
    if os.path.exists(rawdir):
        _log.info("Raw directory already exists.")
        if os.path.exists(cachedir):
            _log.info("Raw AND Cache directories exist.")
        else:
            _log.info("Creating Cache directory.")
            print("Creating cache directory at: ")
            print(f"{cachedir}")
            os.makedirs(cachedir)
    else:
        _log.info("Making Raw directory for *bd and cache files.")
        print("Creating Raw directory at:")
        print(f"{rawdir}")
        os.makedirs(rawdir)
        print("Creating cache dir at: ")
        print(f"{cachedir}")
        os.makedirs(cachedir)

    # SEARCH FOR RAW DATA AND CACHE FILES
    # Walk through rootDir, search for where EBD, DBD, CAC files are stored...
    _log.info("About to navigate through rootdir.")
    _, dbddirs = _get_dirs(rootdir, ext="DBD")
    _, ebddirs = _get_dirs(rootdir, ext="EBD")
    _, sbddirs = _get_dirs(rootdir, ext="SBD")
    _, tbddirs = _get_dirs(rootdir, ext="TBD")
    n_cac, cacdirs = _get_dirs(rootdir, ext="CAC")

    # COPY ALL CACHE FILES to outdir/Kiwi/Raw/Cache/
    # get pre-existing list of cache files in cacdir, copy new ones.
    cnames = []
    [cnames.append(x) for x in
        set.union(set([x.split('/')[-1] for x in
                       glob(os.path.join(cachedir, "*.CAC"))]),
                  set([x.split('/')[-1] for x in
                       glob(os.path.join(cachedir, "*.cac"))]))]
    n_cac_exist = len(cnames)

    if ~(n_cac_exist == n_cac):
        for cacd in cacdirs:
            cfiles = []
            [cfiles.append(x) for x in
                set.union(set([x.split('/')[-1] for x in
                               glob(os.path.join(cacd, "*.CAC"))]),
                          set([x.split('/')[-1] for x in
                               glob(os.path.join(cacd, "*.cac"))]))]
            for cf in cfiles:
                if cf not in cnames:
                    _log.info(f"Copying cache file {cf}")
                    shutil.copyfile(os.path.join(cacd, cf),
                                    os.path.join(cachedir, cf))
    else:
        _log.info("Cache files already copied (or right number of files, " +
                  " at least)")

    # RENAME, COPY *BD files to outdir
    # Walk through data dirs, get list of filenames...
    ext = ['e', 'd', 's', 't']
    extdirs = [ebddirs, dbddirs, sbddirs, tbddirs]
    for e, temdirs in zip(ext, extdirs):
        for bdd in temdirs:
            oldnames = []
            [oldnames.append(x) for x in
                set.union(set([x.split('/')[-1] for x in
                               glob(os.path.join(bdd, "*." + e.upper() +
                                                 "BD"))]),
                          set([x.split('/')[-1] for x in
                               glob(os.path.join(bdd, "*." + e.lower() +
                                                 "bd"))]))]
            # Load metadata, get converted name, copy file to rawdir
            for name in oldnames:
                try:
                    meta = slocum.dbd_get_meta(
                        os.path.join(bdd, name), cachedir=cachedir)
                    newname = meta[0]['full_filename'] + "." + e + "bd"
                    print(f"New name for {name}: {newname}. Copying...")
                    shutil.copyfile(os.path.join(bdd, name),
                                    os.path.join(rawdir, newname))
                except Exception:
                    err = sys.exc_info()[0]
                    print(f"Error: {err}")
                    print(f"Cannot load metadata for file {name}")
                    print("Not copying to kiwi/raw/")


def _get_dirs(rootdir: str, ext: str) -> tuple:
    """Function to recursive search if directory has files with extension.

    _get_dirs(rootdir: str, ext: str) -> list

    Parameters
    -----------
        rootdir : string
            Directory which contains raw *.BD files within it. Removes "Raw"
            dir from the list at the end, since this should indicate outdir ==
            rootdir
        ext     : string
            File extension to search for, slocum glider use case is for *BD"

    Returns a tuple containing the number of files found and the list of
    directories that have files with given extension.
    """
    out = []
    nfiles = 0
    upp = ext.upper()
    low = ext.lower()
    for root, _, files in os.walk(rootdir):
        for filename in files:
            if os.path.splitext(filename)[1] in ["." + upp, "." + low]:
                nfiles += 1
                if root not in out:
                    out.append(root)
    # Check to see if "Raw and Raw/Cache/ are in the list..."
    removelist = [os.path.join(rootdir, "Kiwi", "Raw"),
                  os.path.join(rootdir, "Kiwi", "Raw", "Cache")]
    for dname in removelist:
        if dname in out:
            out.remove(dname)

    return (nfiles, out)


def _setupcheck(rootdir: str) -> tuple:
    """
    function setupcheck(rootDir, verbose)
    Double-checks that user-provided directory is a valid setup
    for kiwiglider package. Returns tuple with raw and cache paths.

    Parameters
    ----------
    rootdir     : str
        String that has path of kiwiglider directory.

    Output:
    tuple with rawdir and cachedir directories for use in further processing

    """
    import os
    if not os.path.exists(os.path.join(rootdir, "Kiwi", "Raw")):
        raise Exception(f"No Kiwi/Raw/ directory in {rootdir}, either " +
                        "correct directory or run setup() first.")
    else:
        rawdir = os.path.join(rootdir, "Raw")
    if not os.path.exists(os.path.join(rawdir, "Cache")):
        raise Exception("Kiwi/Raw/ directory found, but not Cache. " +
                        "Please re-run setup()")
    else:
        cachedir = os.path.join(rawdir, "Cache")
    return (rawdir, cachedir)
