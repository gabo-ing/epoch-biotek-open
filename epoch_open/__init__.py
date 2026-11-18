"""Free software for the BioTek Epoch with a Take3 micro-volume plate.

Only third-party dependency: pyserial. Everything else is the standard library,
including the xlsx writer, so the program bundles into one small executable.
"""

__version__ = "1.2"

# Two parts, matching the release tags: 1.0 the original release, 1.1 the
# bilingual interface, 1.2 the blanking fixes. Bump the minor part for a
# behaviour change a user would notice. The version is written into every
# result file, so a number can always be traced back to the build that
# produced it.
