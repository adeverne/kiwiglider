
---
# title: 'KiwiGlider: A Python package for post-processing Slocum Glider Data'

## tags:
  - Python
  - oceanography
  - gliders
  - autonomous science

## authors:
  - name: Alain de Verneil
    orcid: 0000-0002-8344-7953
    equal-contrib: true
    affiliation: 1 <!-- # (Multiple affiliations must be quoted) -->
    corresponding: true
  - name: Cassandra Elmer
    orcid: 0009-0006-3619-3571
    equal-contrib: true <!-- > (This is how you can denote equal contributions between multiple authors) -->
    affiliation: 1
affiliations:
 - name: National Institute of Water and Atmospheric research (NIWA), New Zealand
   index: 1

date: 30 May 2025
bibliography: paper.bib

## Summary

The ocean is the most undersampled domain of the Earth's surface for several
reasons, primarily due to its relative remoteness for humans and the attendant
expense for utilizing research vessels, but also due to its opaqueness to
electromagnetic radiation precluding satellite remote sensing from observing
deeper than the near-surface. Autonomous sampling platforms promise to increase
the total amount of in situ data substantially for lesser cost. Ocean gliders
are such a platform, with the ability to conduct surveys while periodically
receiving directives and sending data via satellite in near real time. Among
the most popular glider platforms is the Slocum glider produced by Teledyne
Webb Research. While tools exist for the retrieval of raw data from gliders,
many of the desired scientific oceanographic outputs from gliders require
post-processing before being considered acceptable for scientific publication
in the wider community, creating a demand among end users for open-source
software to reliably conduct this processing.

## Statement of need

`KiwiGlider` is a Python package for post-processing Slocum glider data. It
bridges a gap in the data processing pipeline that currently exists in the
Python ecosystem. At one end packages exist for reliable and fast
reading of raw data (e.g. `PyGlider` and `dbdreader`), while on the other end
there are solutions for more final processing of quality controlled data (e.g.
optimal interpolation, or Krigging, of transects by `GliderTools`). In between
is the necessary post-processing of scientific variables (e.g. lag corrections
for salinity, oxygen optodes), which `KiwiGlider` is meant to address. By
leveraging the existing Python ecosystem in this space, `KiwiGlider` also hopes
to provide an end-to-end solution, from reading raw data in near real time
during deployment in the field up through the delayed post-processing of an
entire dataset in preparation for scientific publication.

# Capabilities

At its heart, `KiwiGlider` is meant to add certain post-processing to Slocum
glider data that does not currently exist in Python. However, post-processing
routines do exist out in the community more generally, and where possible we
have ported this functionality to the Python code to `KiwiGlider`.

For example, using Matlab code from the GEOMAR glider toolbox, we have adapted
routines to:
  - Run quality control on glider telemetry (e.g. GPS longitude/latitude).
  - Calculate best temperature lag for salinity calculations, following
    [Garau et al. 2011](https://doi.org/10.1175/JTECH-D-10-05030.1).
  - Calculate optode delays in oxygen sensors.

In addition to the usual post-processing, we also make use of existing packages
necessary for extended applications. One example of this is the use of the
`gliderflight` package which optimizes parameters around flight models of the
glider to produce accurate flow speeds for microstructure turbulence
measurements.

# Citations

Citations to entries in paper.bib should be in
[rMarkdown](http://rmarkdown.rstudio.com/authoring_bibliographies_and_citations.html)
format.

If you want to cite a software repository URL (e.g. something on GitHub without a preferred
citation) then you can do it with the example BibTeX entry below for @fidgit.

For a quick reference, the following citation commands can be used:
- `@author:2001`  ->  "Author et al. (2001)"
- `[@author:2001]` -> "(Author et al., 2001)"
- `[@author1:2001; @author2:2001]` -> "(Author1 et al., 2001; Author2 et al., 2002)"

# Figures

Figures can be included like this:
![Caption for example figure.\label{fig:example}](figure.png)
and referenced from text using \autoref{fig:example}.

Figure sizes can be customized by adding an optional second parameter:
![Caption for example figure.](figure.png){ width=20% }

# Acknowledgements

We acknowledge support from the New Zealand MBIE Strategic Scientific Investment
Fund (SSIF), and the contributions from J. O'Callaghan, J. McInerney,
C. Stevens, and C. Collins.

# References
