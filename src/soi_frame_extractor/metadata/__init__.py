"""Metadata writers for EXIF, IPTC, XMP, iFDO, and BIIGLE formats."""

from .apply_metadata import _build_exif, _build_iptc, _build_xmp
from .assemble import assemble_biigle_records
from .biigle import write_biigle_manifest
from .ifdo import write_ifdo_manifest

__all__ = [
    "_build_exif",
    "_build_iptc",
    "_build_xmp",
    "assemble_biigle_records",
    "write_biigle_manifest",
    "write_ifdo_manifest",
]
