import pytest
from unittest.mock import patch, MagicMock


def _mock_response(data: dict, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    return resp


def _make_client():
    from ti.remote import RemoteClient

    client = RemoteClient(
        "https://ti.example.com", "sk-test1234567890abcdef1234567890ab"
    )
    return client


def test_remote_search():
    client = _make_client()
    expected = {
        "command": "search",
        "total": 1,
        "returned": 1,
        "offset": 0,
        "results": [],
    }
    client._session.get = MagicMock(return_value=_mock_response(expected))
    result = client.search("MCP", sort="relevant", limit=20, offset=0)
    client._session.get.assert_called_once()
    call_args = client._session.get.call_args
    assert "/v1/search" in call_args[0][0]
    assert call_args[1]["params"]["q"] == "MCP"
    assert result == expected


def test_remote_stats():
    client = _make_client()
    expected = {"command": "stats", "total_tweets": 100}
    client._session.get = MagicMock(return_value=_mock_response(expected))
    result = client.stats()
    assert result["total_tweets"] == 100


def test_remote_tags():
    client = _make_client()
    expected = {"command": "tags", "total": 32, "results": []}
    client._session.get = MagicMock(return_value=_mock_response(expected))
    result = client.tags()
    assert result["total"] == 32


def test_remote_show():
    client = _make_client()
    expected = {"command": "show", "total": 1, "results": [{"id": "123"}]}
    client._session.get = MagicMock(return_value=_mock_response(expected))
    result = client.show("123")
    assert result["results"][0]["id"] == "123"


def test_remote_unauthorized():
    client = _make_client()
    resp = _mock_response({"error": "unauthorized"}, 401)
    resp.raise_for_status.side_effect = Exception("401 Unauthorized")
    client._session.get = MagicMock(return_value=resp)
    with pytest.raises(Exception):
        client.search("test")
