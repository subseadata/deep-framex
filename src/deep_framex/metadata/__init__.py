"""Metadata writers for EXIF, IPTC, XMP, iFDO, and BIIGLE formats."""

from .assemble import assemble_biigle_records
from .biigle import write_biigle_manifest
from .ifdo import write_ifdo_manifest

__all__ = [
    "assemble_biigle_records",
    "write_biigle_manifest",
    "write_ifdo_manifest",
]
