import zipfile

import requests


def download_url(url, save_path, chunk_size=128):
    r = requests.get(url, stream=True)
    with open(save_path, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            fd.write(chunk)
    print(f'Downloaded "{url}" to "{save_path}"')


def unzip(zip_file_path, save_path):
    print(f'Unzipping {zip_file_path}')
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        zip_ref.extractall(save_path)
