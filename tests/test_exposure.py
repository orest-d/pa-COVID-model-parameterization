import requests
import pytest
import os

from covid_model_parametrization.exposure import *
from covid_model_parametrization.config import Config
import covid_model_parametrization.utils as utils

class MockResponse:
    @staticmethod
    def iter_content(*arg, **kwarg):
        yield b"Hello"
        yield b"world"

class TestUtils:
    def test_get_worldpop_data(self, monkeypatch, tmp_path):
        config = Config()
        config.WORLDPOP_DIR = "TestWorldPop"
        config.AGE_CLASSES = [10,20,30]
        input_dir = tmp_path / "TestInputDir"
        #input_dir.mkdir()

        downloads = []
        def mock_download_ftp(url, save_path):
            downloads.append((url,save_path))

        monkeypatch.setattr(utils, "download_ftp", mock_download_ftp)
        
        get_worldpop_data("XYZ", os.fspath(input_dir), config)

        assert len(downloads)== len(config.AGE_CLASSES)*len(config.GENDER_CLASSES)+2
        files = [f"xyz_{b}_{a}_2020.tif" for a in (10,20,30) for b in "fm"]
        for f,(url,save) in zip(files, downloads):
            assert url.endswith(f)
            assert save.endswith(f)
