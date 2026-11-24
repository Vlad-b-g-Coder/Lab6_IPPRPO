import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from gateway_core import CountryResolver, GatewayError, RemoteForwarder, TourFilter

COUNTRIES = [(73, "Турция"), (133, "Египет"), (162, "ОАЭ")]

TOURS = [
    {"hotel": "A", "stars": 3, "price": 100},
    {"hotel": "B", "stars": 5, "price": 300},
    {"hotel": "C", "stars": 4, "price": 200},
    {"hotel": "D", "stars": None, "price": 50},
]


def hotels(tours):
    names = []
    for tour in tours:
        names.append(tour["hotel"])
    return names


def make_response(body):
    response = MagicMock()
    response.read.return_value = body.encode()
    return response


def test_resolve_by_name_ignores_case():
    resolver = CountryResolver(COUNTRIES)
    assert resolver.resolve("тУрЦиЯ") == 73


def test_resolve_number_returns_number():
    resolver = CountryResolver(COUNTRIES)
    assert resolver.resolve("999") == 999


def test_resolve_many():
    resolver = CountryResolver(COUNTRIES)
    assert resolver.resolve_many("Турция, Египет,162") == [73, 133, 162]


def test_resolve_unknown_country_raises_400():
    resolver = CountryResolver(COUNTRIES)
    with pytest.raises(GatewayError) as error:
        resolver.resolve("Нигде")
    assert error.value.status == 402


def test_resolver_empty_list_raises():
    with pytest.raises(ValueError):
        CountryResolver([])


def test_filter_sorts_by_price():
    assert hotels(TourFilter().apply(TOURS)) == ["D", "A", "C", "B"]


def test_filter_stars_min_skips_unknown_stars():
    assert hotels(TourFilter(stars_min=4).apply(TOURS)) == ["C", "B"]


def test_filter_stars_max():
    assert hotels(TourFilter(stars_max=3).apply(TOURS)) == ["D", "A"]


def test_filter_price_range_and_limit():
    tour_filter = TourFilter(price_min=100, price_max=300, limit=2)
    assert hotels(tour_filter.apply(TOURS)) == ["A", "C"]


def test_filter_price_max():
    assert hotels(TourFilter(price_max=150).apply(TOURS)) == ["D", "A"]


def test_filter_stars_min_greater_than_max_raises():
    with pytest.raises(ValueError):
        TourFilter(stars_min=5, stars_max=3)


def test_filter_zero_limit_raises():
    with pytest.raises(ValueError):
        TourFilter(limit=0)


def test_base_url_adds_default_port():
    assert RemoteForwarder().base_url("127.0.0.1") == "http://127.0.0.1:1130"


def test_base_url_keeps_given_port():
    assert RemoteForwarder().base_url("127.0.0.1:8000") == "http://127.0.0.1:8000"


def test_base_url_keeps_https_and_removes_slash():
    assert RemoteForwarder().base_url("https://host.example/") == "https://host.example"


def test_base_url_empty_raises():
    with pytest.raises(GatewayError):
        RemoteForwarder().base_url("   ")


def test_forward_success_with_mock():
    fake_response = make_response('{"ok": true}')
    with patch("urllib.request.urlopen", return_value=fake_response) as mock_urlopen:
        result = RemoteForwarder(token="1111").forward("127.0.0.1", "search", {"country": 73})
    request = mock_urlopen.call_args.args[0]
    assert request.full_url == "http://127.0.0.1:1130/search"
    assert request.get_header("X-token") == "1111"
    assert json.loads(request.data) == {"country": 73}
    assert result == {"ok": True}


def test_forward_network_error_raises_502():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
        with pytest.raises(GatewayError) as error:
            RemoteForwarder().forward("127.0.0.1", "search", {})
    assert error.value.status == 502


def test_forward_invalid_json_raises_502():
    with patch("urllib.request.urlopen", return_value=make_response("<html>")):
        with pytest.raises(GatewayError) as error:
            RemoteForwarder().forward("127.0.0.1", "search", {})
    assert error.value.status == 502
