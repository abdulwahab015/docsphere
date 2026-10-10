from rest_framework.exceptions import APIException

EDIT_CONFLICT_MESSAGE = (
    "Someone else saved this document after you opened it. Your changes "
    "haven't been saved."
)


class EditConflict(APIException):
    """A save based on an older revision of a document than the stored one.
    The body carries the current document, so the client can show what
    changed and offer to keep its own version or take the newer one."""

    status_code = 409
    default_code = "edit_conflict"

    def __init__(self, current_document):
        super().__init__()
        # Set as is: passed to the constructor, every value in the document
        # would be turned into a string (revision 2 into "2").
        self.detail = {
            "detail": EDIT_CONFLICT_MESSAGE,
            "code": self.default_code,
            "document": current_document,
        }
