import os
import logging
from pathlib import Path
import argparse

import pandas as pd

from utils import utils
from utils.hdx_api import query_api

CONFIG_FILE = 'config.yml'

ACAPS_HDX_ADDRESS = 'acaps-covid19-government-measures-dataset'
INPUT_DIR = 'Inputs'

RAW_DATA_DIR = os.path.join(INPUT_DIR, 'ACAPS_NPIs')
RAW_DATA_FILENAME = 'ACAPS_npis_raw_data.xlsx'
RAW_DATA_FILEPATH = os.path.join(RAW_DATA_DIR, RAW_DATA_FILENAME)

OUTPUT_DATA_DIR = 'NPIs'
OUTPUT_JSON_FILENAME = '{}_NPIs.json'

MEASURE_EQUIVALENCE_FILENAME = 'NPIs - ACAPS NPIs.csv'

logger = logging.getLogger()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--download', action='store_true',
                        help='Download the latest ACAPS data -- required upon first run')
    return parser.parse_args()


def main(download):
    config = utils.parse_yaml(CONFIG_FILE)
    countries = config.keys()
    # Get ACAPS and Natural Earth data
    if download:
        logger.info('Getting ACAPS data')
        get_df_acaps()
        logger.info('Done')
    df_acaps =  pd.read_excel(RAW_DATA_FILEPATH, sheet_name='Database')
    print(df_acaps)
    # Take only the countries of concern
    df_acaps = df_acaps[df_acaps['ISO'].isin(countries)]
    # Simplify LOG_TYPE
    df_acaps = df_acaps.replace({'Introduction / extension of measures': 'implement',
                                'Phase-out measure': 'remove'})
    print(df_acaps)
    # Get our measures equivalent, and drop any that we don't use
    measures_dict = get_measures_equivalence_dictionary()
    df_acaps['our_measures'] = df_acaps["MEASURE"].str.lower().map(measures_dict)
    df_acaps = df_acaps[df_acaps['our_measures'].notnull()]
    # Write to country-specific input file
    for country_iso3 in countries:
        Path(RAW_DATA_DIR).mkdir(parents=True, exist_ok=True)
        output_dir = os.path.join(INPUT_DIR, country_iso3, OUTPUT_DATA_DIR)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        filename = os.path.join(output_dir, OUTPUT_JSON_FILENAME.format(country_iso3))
        logger.info(f'Writing to {filename}')
        df_acaps[df_acaps['ISO'] == country_iso3].set_index('ID').to_json(filename, indent=2, orient='index')


def get_df_acaps():
    # Get the ACAPS data from HDX
    Path(RAW_DATA_DIR).mkdir(parents=True, exist_ok=True)
    filename = list(query_api(ACAPS_HDX_ADDRESS, RAW_DATA_DIR).values())[0]
    os.rename(os.path.join(RAW_DATA_DIR, filename), RAW_DATA_FILEPATH)


def get_measures_equivalence_dictionary():
    df = pd.read_csv(os.path.join(RAW_DATA_DIR, MEASURE_EQUIVALENCE_FILENAME),
                     usecols=['ACAPS NPI', 'Our equivalent'])
    return df.set_index('ACAPS NPI').to_dict()['Our equivalent']


if __name__ == '__main__':
    args = parse_args()
    main(args.download)
