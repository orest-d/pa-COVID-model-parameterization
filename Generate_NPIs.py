import os
import logging
from pathlib import Path
import argparse
from datetime import datetime

import pandas as pd
import geopandas as gpd
import xarray as xr
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
OUTPUT_JSON_FILENAME = '{}_NPIs.json'
OUTPUT_CSV_FILENAME = '{}_NPIs.csv'

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
    measures_dict = get_measures_equivalence_dictionary()
    df_acaps['our_measures'] = df_acaps["MEASURE"].str.lower().map(measures_dict)
    df_acaps = df_acaps[df_acaps['our_measures'].notnull()]
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


def get_boundaries_file(country_iso3, config):
    # Get input boundary shape file, for the admin regions
    input_dir = os.path.join(INPUT_DIR, country_iso3)
    input_shp = os.path.join(input_dir, SHAPEFILE_DIR, config['admin']['directory'],
                             f'{config["admin"]["directory"]}.shp')
    return gpd.read_file(input_shp)


def get_country_info(country_iso3, df_acaps, boundaries):
    logger.info(f'Getting info for {country_iso3}')
    df = df_acaps[df_acaps['ISO'] == country_iso3]
    # Get list of admin 0, 1 and 2 regions
    admin_regions = {
        'admin0': boundaries['ADM0_PCODE'].unique().tolist(),
        'admin1': boundaries['ADM1_PCODE'].unique().tolist(),
        'admin2': boundaries['ADM2_PCODE'].unique().tolist()
    }
    admin1_to_2_dict = boundaries.groupby('ADM1_PCODE')['ADM2_PCODE'].apply(lambda x: x.tolist()).to_dict()
    # Check if JSON file already exists, if so read it in
    output_dir = os.path.join(INPUT_DIR, country_iso3, OUTPUT_DATA_DIR)
    filename = os.path.join(output_dir, OUTPUT_JSON_FILENAME.format(country_iso3))
    if os.path.isfile(filename):
        df_manual = pd.read_json(filename, orient='index')
        df_manual['ID'] = df_manual.index
        # Join the pcode info
        df = df.merge(df_manual[['ID', 'affected_pcodes']], how='left', on='ID')
        # Warn about any empty entries
        empty_entries = df[df['affected_pcodes'].isna()]
        if not empty_entries.empty:
            logger.warning(f'The following NPIs need location info: {empty_entries["ID"].values}')
    else:
        # If it doesn't exist, add an affected pcodes column
        df['affected_pcodes'] = None
    # Write out to a JSON
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    logger.info(f'Writing to {filename}')
    df.set_index('ID').to_json(filename, indent=2, orient='index')
    # Convert all region levels to admin 2
    # If admin 0, just add all of admin 2 directly
    df['affected_pcodes'] = df['affected_pcodes'].apply(lambda x: admin_regions['admin2'] if x == admin_regions['admin0'] else x)
    # For the rest, check if any items in the list are admin 1. If they are, expand them and add them back in
    for row in df.itertuples():
        loc_list = df.at[row.Index, 'affected_pcodes']
        final_loc_list = []
        try:
            for loc in loc_list:
                if loc in admin_regions['admin1']:
                    final_loc_list += admin1_to_2_dict[loc]
                elif loc in admin_regions['admin2']:
                    final_loc_list.append(loc)
                else:
                    logger.error(f'Found incorrect pcode {loc}')
        # If loc_list is not a list
        except TypeError:
            continue
        df.at[row.Index, 'affected_pcodes'] = final_loc_list
    return df


def write_country_info_to_csv(country_iso3, df, boundaries):
    # Create 3d xarray
    coords = {
        'date': pd.date_range(df['ENTRY_DATE'].min(), datetime.today()),
        'measure': sorted(df['our_measures'].unique()),
        'admin2': sorted(boundaries['ADM2_PCODE'].unique()),
    }
    da = xr.DataArray(np.zeros([len(val) for val in coords.values()], dtype=int),
                      dims=coords.keys(), coords=coords)
    # Only take rows with locations
    df = df[df['affected_pcodes'].notna()]
    if df.empty:
       logger.warning(f'No location information available for {country_iso3}, output file will just have 0s')
    # Populate it by looping through the dataframe
    for _, row in df.iterrows():
        date_range = pd.date_range(row['ENTRY_DATE'], datetime.today())
        value_to_add = 1 if row['LOG_TYPE'] == 'add' else -1
        da.loc[date_range, row['our_measures'], row['affected_pcodes']] += value_to_add
    # Convert to dataframe and write out
    df_out = da.to_dataframe('result').unstack().droplevel(0, axis=1)
    output_dir = os.path.join(OUTPUT_DIR, country_iso3, 'NPIs')
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filename = os.path.join(output_dir, OUTPUT_CSV_FILENAME.format(country_iso3))
    logger.info(f'Writing final results to {filename}')
    df_out.to_csv(filename)


if __name__ == '__main__':
    args = parse_args()
    main(args.download)
