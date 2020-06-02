import argparse
import os
import logging
import json
from pathlib import Path

import pandas as pd
import geopandas as gpd
import networkx as nx

import utils

MAIN_DIR = 'Outputs'
OUTPUT_DIR = 'Graph'
OUTPUT_FILE = '{}_graph.json'
CONFIG_FILE = 'config.yml'

EXPOSURE_DIR = 'Exposure_SADD'
EXPOSURE_FILENAME = '{country_iso3}_Exposure.geojson'

COVID_DIR = 'COVID'
COVID_FILENAME = '{country_iso3}_COVID.csv'

VULNERABILITY_DIR = 'Vulnerability'
VULNERABILITY_FILENAME = '{country_iso3}_Vulnerabilities.geojson'

CONTACT_MATRIX_DIR = 'contact_matrices_152_countries'
CONTACT_MATRIX_FILENAME = 'MUestimates_all_locations_{file_number}.xlsx'

utils.config_logger()
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('country_iso3', help='Country ISO3')
    return parser.parse_args()


def main(country_iso3):

    logger.info(f'Creating graph for {country_iso3}')
    main_dir = os.path.join(MAIN_DIR, country_iso3)
    config = utils.parse_yaml(CONFIG_FILE)[country_iso3]

    # Make a graph
    G = nx.Graph()
    G.graph['country'] = country_iso3

    # Add exposure
    G = add_exposure(G, main_dir, country_iso3)

    # Add COVID cases
    G = add_covid(G, main_dir, country_iso3)

    # Add vulnerability
    G = add_vulnerability(G, main_dir, country_iso3)

    # Add contact matrix
    add_contact_matrix(G, config['contact_matrix'])

    # Write out
    data = nx.readwrite.json_graph.node_link_data(G)
    outdir = os.path.join(main_dir, OUTPUT_DIR)
    Path(outdir).mkdir(parents=True, exist_ok=True)
    outfile = os.path.join(main_dir, OUTPUT_DIR, OUTPUT_FILE.format(country_iso3))
    with open(outfile, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f'Wrote out to {outfile}')


def add_exposure(G, main_dir, country_iso3):
    # Read in exposure file
    filename = os.path.join(main_dir, EXPOSURE_DIR, EXPOSURE_FILENAME.format(country_iso3=country_iso3))
    logger.info(f'Reading in exposure from {filename}')
    exposure = gpd.read_file(filename)
    # Turn disag pop columns into lists
    # TODO: aggregate the ages as the contact matrix
    for gender in ['f', 'm']:
        columns = [c for c in exposure.columns if f'{gender}_' in c]
        exposure[f'group_pop_{gender}'] = exposure[columns].values.tolist()
        # Get the age groups
        age_groups = [s.split('_')[-1] for s in columns]
    # Only keep necessary columns
    columns = [
        'ADM2_EN',
        'ADM1_PCODE',
        'ADM2_PCODE',
        'group_pop_f',
        'group_pop_m'
    ]
    exposure = exposure[columns]
    # Rename some
    rename_dict = {
        'ADM2_EN': 'name',
    }
    exposure = exposure.rename(columns=rename_dict)

    # Add the exposure info to graph
    G.graph['age_groups'] = age_groups
    for row in exposure.to_dict(orient='records'):
        G.add_node(row['ADM2_PCODE'], **row)
    return G


def add_covid(G, main_dir, country_iso3):
    # Read in COVID file
    filename = os.path.join(main_dir, COVID_DIR, COVID_FILENAME.format(country_iso3=country_iso3))
    logger.info(f'Reading in COVID cases from {filename}')
    covid = pd.read_csv(filename)
    date_range = pd.date_range(covid['#date'].min(), covid['#date'].max())
    for cname in ['confirmed', 'dead']:
        # Do some pivoting
        covid_out = covid.pivot(index='#date',
                                values=f'#affected+infected+{cname}+total',
                                columns='#adm2+pcode')
        # Add any missing dates
        covid_out.index = pd.DatetimeIndex(covid_out.index)
        covid_out = covid_out.reindex(date_range)
        # Interpolate the missing values
        covid_out = covid_out.interpolate(method='linear', axis='rows', limit_direction='forward').fillna(0)
        # Add to the graph
        G.graph['dates'] = list(covid_out.index.astype(str))
        for admin2 in covid_out.columns:
            G.add_node(admin2, **{f'infected_{cname}': covid_out[admin2].values.tolist()})
    return G


def add_vulnerability(G, main_dir, country_iso3):
    # Read in vulnerability file
    filename = os.path.join(main_dir, VULNERABILITY_DIR, VULNERABILITY_FILENAME.format(country_iso3=country_iso3))
    logger.info(f'Reading in vulnerability from {filename}')
    vulnerability = gpd.read_file(filename)
    # Only keep necessary columns
    columns = [
        'ADM2_PCODE',
        'frac_urban',
        'Phase 3+',
        'fossil_fuels',
        'handwashing_facilities',
        'raised_blood_pressure',
        'diabetes',
        'smoking'
    ]
    vulnerability = vulnerability[columns]
    # Rename some
    rename_dict = {
        'Phase 3+': 'food_insecurity',
    }
    vulnerability = vulnerability.rename(columns=rename_dict)
    # Make food insecurity be the vulnerability factor
    vulnerability['vulnerability_factor'] = vulnerability['food_insecurity']
    # Add the exposure info to graph
    for row in vulnerability.to_dict(orient='records'):
        G.add_node(row['ADM2_PCODE'], **row)
    return G


def add_contact_matrix(G, config):
    filename = os.path.join(CONTACT_MATRIX_DIR, CONTACT_MATRIX_FILENAME.format(file_number=config['file_number']))
    logger.info(f'Reading in contact matrix from {filename} for country {config["country"]}')
    column_names = [f'X{i+1}' for i in range(16)]
    contact_matrix = pd.read_excel(filename, sheet_name=config['country'], header=None, names=column_names)
    # Add columns X0 and X17
    contact_matrix['X0'] = contact_matrix['X1']
    contact_matrix['X17'] = contact_matrix['X16']
    # Reorder
    contact_matrix = contact_matrix[['X0'] + column_names + ['X17']]
    # Add as metadata
    G.graph['contact_matrix'] = contact_matrix.values.tolist()
    return G


if __name__ == '__main__':
    args = parse_args()
    main(args.country_iso3.upper())
