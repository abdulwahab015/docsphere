"""Recognising what kind of file an upload is from its content - never just
its name - so a document's attachments are only ever the allowed kinds."""

import codecs
import zipfile
from pathlib import Path

from projects.constants import FILE_SIGNATURE_BYTES
from projects.mappings import ATTACHMENT_TYPES, FILE_SIGNATURES, OFFICE_MAIN_PARTS

UNSUPPORTED_FILE_MESSAGE = (
    "Attach a PDF, an image (PNG, JPEG, GIF or WebP), a text or CSV file, or a "
    "Word, Excel or PowerPoint file."
)
TEXT_CHUNK_BYTES = 64 * 1024


class UnsupportedFileError(Exception):
    """The upload isn't one of the allowed kinds, or isn't what its name says."""


def attachment_content_type(upload):
    """The MIME type of ``upload`` (a Django ``UploadedFile``), from its
    content: its name must end in an allowed type, and its content must
    really be that type - a renamed program is refused. Leaves the file at its
    start."""
    extension = Path(upload.name).suffix.lower()
    content_type = ATTACHMENT_TYPES.get(extension)
    if not content_type:
        raise UnsupportedFileError(UNSUPPORTED_FILE_MESSAGE)

    try:
        matches = _content_is(content_type, upload)
    finally:
        upload.seek(0)
    if not matches:
        raise UnsupportedFileError(
            f"This file's content doesn't match its {extension} name."
        )
    return content_type


def _content_is(content_type, upload):
    if content_type in OFFICE_MAIN_PARTS:
        return _is_office_file(upload, OFFICE_MAIN_PARTS[content_type])
    if content_type.startswith("text/"):
        return _is_text(upload)

    upload.seek(0)
    start = upload.read(FILE_SIGNATURE_BYTES)
    if content_type == "image/webp":
        return start[:4] == b"RIFF" and start[8:12] == b"WEBP"
    return start.startswith(FILE_SIGNATURES[content_type])


def _is_office_file(upload, main_part):
    """A zip archive with Office's content-types list and the part that makes
    it this kind of document. Only the archive's directory is read, never its
    contents, so a zip bomb costs nothing."""
    upload.seek(0)
    try:
        with zipfile.ZipFile(upload) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in names and main_part in names


def _is_text(upload):
    """UTF-8 text throughout (a byte-order mark is fine), with no NUL bytes."""
    upload.seek(0)
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        for chunk in iter(lambda: upload.read(TEXT_CHUNK_BYTES), b""):
            if b"\x00" in chunk:
                return False
            decoder.decode(chunk)
        decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        return False
    return True
