import os
import logging
from pathlib import Path
import argparse
from datetime import datetime

import pandas as pd
import geopandas as gpd
import numpy as np

from utils import utils
from utils.hdx_api import query_api

CONFIG_FILE = 'config.yml'

ACAPS_HDX_ADDRESS = 'acaps-covid19-government-measures-dataset'
INPUT_DIR = 'Inputs'
OUTPUT_DIR = 'Outputs'

RAW_DATA_DIR = os.path.join(INPUT_DIR, 'ACAPS_NPIs')
RAW_DATA_FILENAME = 'ACAPS_npis_raw_data.xlsx'
RAW_DATA_FILEPATH = os.path.join(RAW_DATA_DIR, RAW_DATA_FILENAME)

OUTPUT_DATA_DIR = 'NPIs'
INTERMEDIATE_OUTPUT_FILENAME = '{}_NPIs_input.csv'
FINAL_OUTPUT_FILENAME = '{}_NPIs.csv'

MEASURE_EQUIVALENCE_FILENAME = 'NPIs - ACAPS NPIs.csv'

SHAPEFILE_DIR = 'Shapefiles'

logger = logging.getLogger()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--download', action='store_true',
                        help='Download the latest ACAPS data -- required upon first run')
    return parser.parse_args()


def main(download):
    config = utils.parse_yaml(CONFIG_FILE)
    countries = list(config.keys())
    # Get ACAPS and Natural Earth data
    if download:
        logger.info('Getting ACAPS data')
        get_df_acaps()
        logger.info('Done')
    df_acaps =  pd.read_excel(RAW_DATA_FILEPATH, sheet_name='Database')
    # Take only the countries of concern
    df_acaps = df_acaps[df_acaps['ISO'].isin(countries)]
    # Simplify LOG_TYPE
    df_acaps = df_acaps.replace({'Introduction / extension of measures': 'add',
                                'Phase-out measure': 'remove'})
    # Get our measures equivalent, and drop any that we don't use
    df_acaps['our_measures'] = df_acaps["MEASURE"].str.lower().map(get_measures_equivalence_dictionary())
    df_acaps = df_acaps[df_acaps['our_measures'].notnull()]
    df_acaps['category'] = df_acaps['our_measures'].map(get_measures_category_dictionary())
    # Loop through countries
    for country_iso3 in countries:
        boundaries = get_boundaries_file(country_iso3, config[country_iso3])
        df_country = get_country_info(country_iso3, df_acaps, boundaries)
        write_country_info_to_csv(country_iso3, df_country, boundaries)


def get_df_acaps():
    # Get the ACAPS data from HDX
    Path(RAW_DATA_DIR).mkdir(parents=True, exist_ok=True)
    filename = list(query_api(ACAPS_HDX_ADDRESS, RAW_DATA_DIR).values())[0]
    os.rename(os.path.join(RAW_DATA_DIR, filename), RAW_DATA_FILEPATH)


def get_measures_equivalence_dictionary():
    df = pd.read_csv(os.path.join(RAW_DATA_DIR, MEASURE_EQUIVALENCE_FILENAME),
                     usecols=['ACAPS NPI', 'Our equivalent'])
    return df.set_index('ACAPS NPI').to_dict()['Our equivalent']


def get_measures_category_dictionary():
    df = pd.read_csv(os.path.join(RAW_DATA_DIR, MEASURE_EQUIVALENCE_FILENAME),
                     usecols=['Our NPIs', 'Category']).dropna()
    return df.set_index('Our NPIs').to_dict()['Category']


def get_boundaries_file(country_iso3, config):
    # Get input boundary shape file, for the admin regions
    input_dir = os.path.join(INPUT_DIR, country_iso3)
    input_shp = os.path.join(input_dir, SHAPEFILE_DIR, config['admin']['directory'],
                             f'{config["admin"]["directory"]}.shp')
    # Read in and rename columns for Somalia
    return gpd.read_file(input_shp).rename(columns={
        'admin0Pcod': 'ADM0_PCODE',
        'admin1Pcod': 'ADM1_PCODE',
        'admin2Pcod': 'ADM2_PCODE',
    })


def get_country_info(country_iso3, df_acaps, boundaries):
    logger.info(f'Getting info for {country_iso3}')
    df = df_acaps[df_acaps['ISO'] == country_iso3]
    admin_regions = get_admin_regions(boundaries)
    # Check if JSON file already exists, if so read it in
    output_dir = os.path.join(INPUT_DIR, country_iso3, OUTPUT_DATA_DIR)
    filename = os.path.join(output_dir, INTERMEDIATE_OUTPUT_FILENAME.format(country_iso3))
    new_cols = ['affected_pcodes',
                'end_date',
                'add_npi_id',
                'remove_npi_id',
                'compliance',
                'use_in_model']
    if os.path.isfile(filename):
        logger.info(f'Reading in input file {filename}')
        df_manual = pd.read_csv(filename)
        # Join the pcode info
        df = df.merge(df_manual[['ID'] + new_cols], how='left', on='ID')
        # Warn about any empty entries
        empty_entries = df[df['affected_pcodes'].isna()]
        if not empty_entries.empty:
            logger.warning(f'The following NPIs for {country_iso3} need location info: {empty_entries["ID"].values}')
    else:
        # If it doesn't exist, add empty columns
        logger.info(f'No input file {filename} found, creating one')
        for col in new_cols:
            df[col] = None
    # Write out to a JSON
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    logger.info(f'Writing to {filename}')
    df.to_csv(filename, index=False)
    return df


def get_admin_regions(boundaries):
    # Get list of admin 0, 1 and 2 regions
    return {
        'admin0': boundaries['ADM0_PCODE'].unique().tolist(),
        'admin1': boundaries['ADM1_PCODE'].unique().tolist(),
        'admin2': boundaries['ADM2_PCODE'].unique().tolist()
    }


def write_country_info_to_csv(country_iso3, df, boundaries):
    # Only take rows with locations, and that are NPI addtiona
    df = df[df['affected_pcodes'].notna() & (df['LOG_TYPE'] == 'add')]
    if df.empty:
        logger.warning(f'No location information available for {country_iso3}, output file will just have 0s')
    # Make the output df
    df_out = pd.DataFrame(columns=[
        'npi_type',
        'npi_category',
        'admin_level',
        'region_geotag',
        'start_date',
        'end_date',
        'compliance'
    ])
    for _, row in df.iterrows():
        # Get admin level
        admin_level = None
        admin_regions = get_admin_regions(boundaries)
        for level in [0, 1, 2]:
            if row['affected_pcodes'][0] in admin_regions[f'admin{level}']:
                admin_level = level
                break
        # TODO: add warning if admin level is still None
        # Loop through locs
        for loc in row['affected_pcodes']:
            new_row = {
                'npi_type': row['our_measures'],
                'npi_category': row['category'],
                'admin_level': admin_level,
                'region_1_geotag': loc,
                'start_date': row['ENTRY_DATE'],
                'end_date': row['end_date']
            }
            df_out = df_out.append(new_row, ignore_index=True)
    # Write out
    output_dir = os.path.join(OUTPUT_DIR, country_iso3, 'NPIs')
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filename = os.path.join(output_dir, FINAL_OUTPUT_FILENAME.format(country_iso3))
    logger.info(f'Writing final results to {filename}')
    df_out.to_csv(filename, index=None)


if __name__ == '__main__':
    args = parse_args()
    main(args.download)
