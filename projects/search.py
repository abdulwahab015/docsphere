"""Where a document search matched inside a document's content, as a short
excerpt the documents list can show under the title."""

import re

# Characters of context kept before the first match, and the excerpt's
# overall length - about a line in the documents list.
EXCERPT_CONTEXT_BEFORE = 60
EXCERPT_MAX_LENGTH = 200
ELLIPSIS = "…"


def content_excerpt(content, terms):
    """About a line of ``content`` around the earliest place any of the search
    ``terms`` occurs, on one line, as ``(text, is_match)`` segments - every
    occurrence of a term within it marked - with "…" where it was cut. ``None``
    when no term occurs in the content (the document matched by its title) or
    there's no content at all.

    Matches case-insensitively, like the search itself."""
    if not terms or not content:
        return None

    pattern = re.compile(
        "|".join(re.escape(term) for term in terms), flags=re.IGNORECASE
    )
    flat = " ".join(content.split())
    first_match = pattern.search(flat)
    if not first_match:
        return None

    start = max(first_match.start() - EXCERPT_CONTEXT_BEFORE, 0)
    end = min(start + EXCERPT_MAX_LENGTH, len(flat))
    # Cut between words, never through one - or through the first match.
    if start:
        start = flat.rfind(" ", 0, start) + 1
    if end < len(flat):
        end = max(flat.rfind(" ", first_match.end(), end), first_match.end())
    excerpt = (
        (ELLIPSIS if start else "")
        + flat[start:end]
        + (ELLIPSIS if end < len(flat) else "")
    )

    segments = []
    position = 0
    for match in pattern.finditer(excerpt):
        if match.start() > position:
            segments.append((excerpt[position : match.start()], False))
        segments.append((match.group(), True))
        position = match.end()
    if position < len(excerpt):
        segments.append((excerpt[position:], False))
    return segments
