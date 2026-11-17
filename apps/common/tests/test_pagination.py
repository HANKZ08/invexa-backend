from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.common.pagination import StandardPagination


def request_with(query: str) -> Request:
    return Request(APIRequestFactory().get(f"/api/x/?{query}"))


def test_client_can_choose_25_50_or_100_rows():
    paginator = StandardPagination()
    assert paginator.get_page_size(request_with("page_size=25")) == 25
    assert paginator.get_page_size(request_with("page_size=50")) == 50
    assert paginator.get_page_size(request_with("page_size=100")) == 100


def test_page_size_is_capped_at_100():
    assert StandardPagination().get_page_size(request_with("page_size=500")) == 100


def test_default_page_size_is_20_without_the_parameter():
    assert StandardPagination().get_page_size(request_with("")) == 20
