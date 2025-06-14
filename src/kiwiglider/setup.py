#!/usr/bin/python3
# setup.py in kiwiglider package
# Here we contain the function to generate the processing environment for
# KiwiGlider.
# We follow this up with either reading in the YAML file for the deployment,
# or autogenerating one from the metadata.

def setup(rootDir: str, outDir: str = None, startDate: float = None,
          endDate: float = None, verbose: bool = True) -> None:
    """
    setup(rootDir: str, outDir: str = None, startDate: float = None,
          endDate: float = None, verbose: bool = True) -> None
    Parameters
    -----------
        rootDir : string
            Directory with raw EBD/DBD/SBD/TBD/CAC files for processing.
        outDir  : string
            Directory to which the subdirectory "Raw" will be created and
            copies of raw data and cache files to be sent.
        startDate : float, default = None
        startDate (float) = None  POSIX timestamp (i.e. seconds since
            1970-01-01Z00:00:00) indicating start of deployment.
        endDate (float) = None POSIX timestamp (i.e. seconds since
            1970-01-01Z00:00:00) indicating end of glider deployment.
        verbose (bool)
    """
    # Import needed packages
    import os
    from glob import glob
    import shutil
    import sys
    from datetime import datetime, UTC
    from pyglider import slocum

    if verbose:
        print("Initiated setup of Kiwiglider at " +
              datetime.strftime(datetime.now(tz=UTC),
                                "%Y-%m-%d %H:%M:%S"))

    # Test to see if rootDir exists and is not just "."
    if os.path.exists(rootDir) & (rootDir != "."):
        print(f"Path {rootDir} passes initial test...")
    else:
        raise ValueError("This path either does not exist, or it is '.'," +
                         " which cannot be used. Please write full path.")
    # Default value of outDir is rootDir
    if not outDir:
        outDir = rootDir

    # Check to see if Raw directory already exists
    if os.path.exists(os.path.join(outDir, "Raw")):
        if verbose:
            print("Raw directory already exists...")
        if os.path.exists(os.path.join(outDir, "Raw", "Cache")):
            if verbose:
                print("Raw AND Cache directories exist.")
        else:
            if verbose:
                print("Creating Cache directory")
            os.makedirs(os.path.join(outDir, "Raw", "Cache"))
    else:
        if verbose:
            print("Making Raw directory for dbd/ebd and cache files.")
        os.makedirs(os.path.join(outDir, "Raw"))
        os.makedirs(os.path.join(outDir, "Raw", "Cache"))

    # Walk through rootDir, search for where EBD, DBD, CAC files are stored...
    dbdDirs = []
    nDBD = 0
    ebdDirs = []
    nEBD = 0
    sbdDirs = []
    nSBD = 0
    tbdDirs = []
    nTBD = 0
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
                # Check for sbd...
                if os.path.splitext(filename)[1] in [".SBD", ".sbd"]:
                    nSBD += 1
                    if root not in sbdDirs:
                        sbdDirs.append(root)
                # Check for tbd...
                if os.path.splitext(filename)[1] in [".TBD", ".tbd"]:
                    nTBD += 1
                    if root not in tbdDirs:
                        tbdDirs.append(root)
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
        print(f"Found {len(sbdDirs):02d} directories with a " +
              f"total of {nSBD} sbd files ...")
        [print(f"{x}") for x in sbdDirs]
        print(f"Found {len(tbdDirs):02d} directories with a " +
              f"total of {nTBD} tbd files ...")
        [print(f"{x}") for x in tbdDirs]
        print(f"Found {len(cacDirs):02d} directories with a " +
              f"total of {nCAC} cac files:")
        [print(f"{x}") for x in cacDirs]

    # For simplicity, but also because dbdreader uses glob to list all the
    # DBD/EBD/SBD/TBD files, re-locate all DBD/EBD files to single "raw"
    # directory with CAC files in sub-directory Cache/. Read metadata and
    # re-name the files.
    # Check to see if copies already exist....
    e1 = glob(os.path.join(outDir, "Raw", "*.EBD"))
    e1name = [x.split('/')[-1] for x in e1]
    e2 = glob(os.path.join(outDir, "Raw", "*.ebd"))
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
                                            os.path.join(outDir, "Raw",
                                                         filename))
    d1 = glob(os.path.join(outDir, "Raw", "*.DBD"))
    d1name = [x.split('/')[-1] for x in d1]
    d2 = glob(os.path.join(outDir, "Raw", "*.dbd"))
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
                                            os.path.join(outDir, "Raw",
                                                         filename))
    s1 = glob(os.path.join(outDir, "Raw", "*.SBD"))
    s1name = [x.split('/')[-1] for x in s1]
    s2 = glob(os.path.join(outDir, "Raw", "*.sbd"))
    s2name = [x.split('/')[-1] for x in s2]
    if len(s1) + len(s2) != nSBD:
        if verbose:
            print(f"Found {len(s1) + len(s2)} sbd files in Raw, but " +
                  f"detected {nSBD} files in total... will copy new files.")
        for sdir in sbdDirs:
            for root, _, files in os.walk(sdir):
                for filename in files:
                    if os.path.splitext(filename)[1] in [".SBD", ".sbd"]:
                        if (filename not in s1name) & (filename not in s2name):
                            shutil.copyfile(os.path.join(root, filename),
                                            os.path.join(outDir, "Raw",
                                                         filename))

    t1 = glob(os.path.join(outDir, "Raw", "*.TBD"))
    t1name = [x.split('/')[-1] for x in s1]
    t2 = glob(os.path.join(outDir, "Raw", "*.tbd"))
    t2name = [x.split('/')[-1] for x in s2]
    if len(t1) + len(t2) != nTBD:
        if verbose:
            print(f"Found {len(t1) + len(t2)} tbd files in Raw, but " +
                  f"detected {nSBD} files in total... will copy new files.")
        for sdir in sbdDirs:
            for root, _, files in os.walk(sdir):
                for filename in files:
                    if os.path.splitext(filename)[1] in [".TBD", ".tbd"]:
                        if (filename not in t1name) & (filename not in t2name):
                            shutil.copyfile(os.path.join(root, filename),
                                            os.path.join(outDir, "Raw",
                                                         filename))

    c1 = glob(os.path.join(outDir, "Raw", "Cache", "*.CAC"))
    c1name = [x.split('/')[-1] for x in c1]
    c2 = glob(os.path.join(outDir, "Raw", "Cache", "*.cac"))
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
                                            os.path.join(outDir, "Raw",
                                                         "Cache", filename))
    # Rename all files to have full filenames from metadata...
    for root, _, files in os.walk(os.path.join(outDir, "Raw")):
        for filename in files:
            path, ext = os.path.splitext(filename)
            if ext in [".ebd", ".dbd", ".EBD", ".DBD", ".sbd", ".SBD",
                       ".tbd", ".TBD"]:
                try:
                    meta = slocum.dbd_get_meta(os.path.join(root, filename),
                                               cachedir=os.path.join(root,
                                                                     "Cache"))
                    print("Meta got loaded...")
                    newname = meta[0]['full_filename']
                    shutil.copyfile(os.path.join(root, filename),
                                    os.path.join(root, newname + ext.lower()))
                    print(f"Removing {filename}...")
                    os.remove(os.path.join(root, filename))
                except Exception:
                    e = sys.exc_info()[0]
                    print(f"Error: {e}")
                    print(f"Cannot load metadata for file {filename}")
                    print("Moving on to next file...")

    if verbose:
        print("Raw directory exists, and any new EBD/DBD/SBD/TBD/cache files" +
              " have been copied over and re-named.")


def _setupcheck(rootDir: str, verbose: bool = True) -> tuple:
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
