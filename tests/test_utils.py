import requests
import pytest
import os

from covid_model_parametrization.utils import *

class MockResponse:
    @staticmethod
    def iter_content(*arg, **kwarg):
        yield b"Hello"
        yield b"world"

class TestUtils:
    def test_dummy(self):
        assert True
        
    def test_download_url(self, monkeypatch, tmp_path):
        path = os.fspath(tmp_path / "hello.txt")
        test_url = "http://testurl"
        def mock_get(url, *args, **kwargs):
            assert url == test_url
            return MockResponse()

        monkeypatch.setattr(requests, "get", mock_get)
        download_url(test_url, path)
        assert b"Helloworld" == open(path, "rb").read()
        
        