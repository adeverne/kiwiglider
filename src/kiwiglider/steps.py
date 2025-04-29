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
    e2 = glob(os.path.join(rootDir, "Raw", "*.ebd"))
    if len(e1) + len(e2) != nEBD:
        if verbose:
            print(f"Found {len(e1) + len(e2)} files in Raw, but detected " +
                  f"{nEBD} files in total... will copy new files.")
        for edir in ebdDirs:
            for root, _, files in os.walk(edir):
                for filename in files:
                    if os.path.splitext(filename)[1] in [".EBD", ".ebd"]:
                        if (filename not in e1) & (filename not in e2):
                            shutil.copyfile(os.path.join(root, filename),
                                            os.path.join(rootDir, "Raw",
                                                         filename))
    d1 = glob(os.path.join(rootDir, "Raw", "*.DBD"))
    d2 = glob(os.path.join(rootDir, "Raw", "*.dbd"))
    if len(d1)+len(d2) != nDBD:
        if verbose:
            print(f"Found {len(d1) + len(d2)} files in Raw, but detected " +
                  f"{nDBD} files in total... will copy new files.")
        for ddir in dbdDirs:
            for root, _, files in os.walk(ddir):
                for filename in files:
                    if os.path.splitext(filename)[1] in [".DBD", ".dbd"]:
                        if (filename not in d1) & (filename not in d2):
                            shutil.copyfile(os.path.join(root, filename),
                                            os.path.join(rootDir, "Raw",
                                                         filename))
    c1 = glob(os.path.join(rootDir, "Raw", "Cache", "*.CAC"))
    c2 = glob(os.path.join(rootDir, "Raw", "Cache", "*.cac"))
    if len(c1)+len(c2) != nCAC:
        if verbose:
            print(f"Found {len(c1) + len(c2)} cache files in Raw, but " +
                  f"detected {nCAC} files in total... will copy new files.")
        for cdir in cacDirs:
            for root, _, files in os.walk(cdir):
                for filename in files:
                    if os.path.splitext(filename)[1] in [".CAC", ".cac"]:
                        if (filename not in c1) & (filename not in c1):
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


def step01(rootDir: str = ".", verbose: bool = True):
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


def step02telemetry(verbose: bool = True):
    """
    function telemetry(): -> None

    Input:
        verbose - Logical switch to print detailed status
    Output:


    Description:
    """
