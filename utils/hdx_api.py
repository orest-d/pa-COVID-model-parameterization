import shutil
import os
import logging

from hdx.utilities.easy_logging import setup_logging
from hdx.hdx_configuration import Configuration
from hdx.data.dataset import Dataset


HDX_SITE = 'prod'
USER_AGENT = 'MapAction'


setup_logging()
logger = logging.getLogger()
Configuration.create(hdx_site=HDX_SITE, user_agent=USER_AGENT, hdx_read_only=True)


def query_api(hdx_address, directory, resource_format='XLSX'):
    dataset = Dataset.read_from_hdx(hdx_address)
    resources = dataset.get_resources()
    filenames = {}
    for resource in resources:
        if resource['format'] == resource_format:
            _, path = resource.download()
            filename = os.path.basename(path)
            shutil.move(path, os.path.join(directory, filename))
            filenames[resource['name']] = filename
            logging.info(f'Saved \"{resource["name"]}\" to \"{directory}/{filename}\"')
    return filenames
