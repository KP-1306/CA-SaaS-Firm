"""Development-grade media/upload settings for document attachments.

Imported at the end of ``base.py`` (see the appended import). Kept in a separate
module so the workflow patch never rewrites the whole settings file.
"""

from __future__ import annotations

from .base import BASE_DIR

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024
