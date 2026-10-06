"""Pagination shape matching API Specification §1."""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class ProperticaPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "per_page"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(
            {
                "data": data,
                "pagination": {
                    "page": self.page.number,
                    "per_page": self.get_page_size(self.request),
                    "total": self.page.paginator.count,
                },
            }
        )
