"""Independent cover generator. Contracts and library only.

This package does not generate images, DOCX, or PDF, and it does not
replace the existing workshop cover engines.
"""

from app.cover.constants import COVER_MODE, PACKAGE

__all__ = ["COVER_MODE", "PACKAGE"]
