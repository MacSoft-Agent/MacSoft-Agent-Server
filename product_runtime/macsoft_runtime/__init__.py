"""Production runtime support for MacSoft Agent."""

from .metadata import ProductMetadata, load_product_metadata
from .paths import ProductPaths, resolve_development_paths, resolve_packaged_paths

__all__ = [
    "ProductMetadata",
    "ProductPaths",
    "load_product_metadata",
    "resolve_development_paths",
    "resolve_packaged_paths",
]
