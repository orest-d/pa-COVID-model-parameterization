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

EXPOSURE_DIR = 'Exposure_SADD'
EXPOSURE_FILENAME = '{country_iso3}_Exposure.geojson'

COVID_DIR = 'COVID'
COVID_FILENAME = '{country_iso3}_COVID.csv'

VULNERABILITY_DIR = 'Vulnerability'
VULNERABILITY_FILENAME = '{country_iso3}_Vulnerabilities.geojson'

utils.config_logger()
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('country_iso3', help='Country ISO3')
    return parser.parse_args()


def main(country_iso3):

    main_dir = os.path.join(MAIN_DIR, country_iso3)

    # Make a graph
    G = nx.Graph()
    G.graph['country'] = country_iso3
    # TODO: Add contact matrix in metadata

    # Add exposure
    add_exposure(G, main_dir, country_iso3)

    # Add COVID cases
    add_covid(G, main_dir, country_iso3)

    # TODO: Add vulnerability
    add_vulnerability(G, main_dir, country_iso3)

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
    # Do some pivoting
    for cname in ['confirmed', 'dead']:
        covid_out = covid.pivot(columns='#date',
                                values=f'#affected+infected+{cname}+total',
                                index='#adm2+pcode').fillna(0)
        # Get the date list
        dates = list(covid_out.columns)
        # Get the numbers in a list
        covid_out[f'infected_{cname}'] = covid_out.values.tolist()
        covid_out = covid_out[[f'infected_{cname}']]
        # Add to the graph
        G.graph['dates'] = dates
        for admin2, row in covid_out.to_dict(orient='index').items():
            G.add_node(admin2, **row)
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


if __name__ == '__main__':
    args = parse_args()
    main(args.country_iso3.upper())
