"""Lookup tables for the projects app."""

from projects.choices import AccessLevel, Action

ALLOWED_ACTIONS = {
    AccessLevel.VIEWER: {Action.READ},
    AccessLevel.EDITOR: {Action.READ, Action.WRITE},
    AccessLevel.OWNER: {Action.READ, Action.WRITE, Action.DELETE, Action.RESHARE},
}

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

# The files that may be attached, by name ending, and the type each must turn
# out to be once its content is checked.
ATTACHMENT_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".docx": DOCX,
    ".xlsx": XLSX,
    ".pptx": PPTX,
}

# The part every Word, Excel or PowerPoint file (a zip archive) contains.
OFFICE_MAIN_PARTS = {
    DOCX: "word/document.xml",
    XLSX: "xl/workbook.xml",
    PPTX: "ppt/presentation.xml",
}

# The bytes each binary attachment type starts with (WebP is checked apart:
# "RIFF", four bytes of length, then "WEBP").
FILE_SIGNATURES = {
    "application/pdf": b"%PDF-",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
    # GIF87a or GIF89a.
    "image/gif": b"GIF8",
}
