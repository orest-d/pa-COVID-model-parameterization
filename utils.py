import zipfile
from urllib.request import urlretrieve
import logging

import requests
import yaml


logger = logging.getLogger(__name__)


def config_logger():
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S')


def download_url(url, save_path, chunk_size=128):
    r = requests.get(url, stream=True)
    with open(save_path, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            fd.write(chunk)
    logger.info(f'Downloaded "{url}" to "{save_path}"')


def download_ftp(url, save_path):
    logger.info(f'Downloading "{url}" to "{save_path}"')
    urlretrieve(url, filename=save_path)


def unzip(zip_file_path, save_path):
    logger.info(f'Unzipping {zip_file_path}')
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        zip_ref.extractall(save_path)


def parse_yaml(filename):
    with open(filename, 'r') as stream:
        config = yaml.safe_load(stream)
    return config
