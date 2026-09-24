from rest_framework.pagination import PageNumberPagination as _PageNumberPagination


class PageNumberPagination(_PageNumberPagination):
    """Project-wide default: page-numbered, client-adjustable page size.

    Wired in as ``REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"]`` so every list
    endpoint returns ``{count, next, previous, results}`` consistently.
    """

    page_size = 20
    max_page_size = 100
    page_size_query_param = "page_size"
