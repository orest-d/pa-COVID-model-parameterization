import argparse
import os
import logging
import json
from pathlib import Path

import geopandas as gpd
import networkx as nx

import utils

MAIN_DIR = 'Outputs'
EXPOSURE_DIR = 'Exposure_SADD'
OUTPUT_DIR = 'Graph'
OUTPUT_FILE = '{}_graph.json'

CONFIG_FILE = 'config.yml'
DIR_PATH = os.path.dirname(os.path.realpath(__file__))

utils.config_logger()
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('country_iso3', help='Country ISO3')
    return parser.parse_args()


def main(country_iso3):

    main_dir = os.path.join(DIR_PATH, MAIN_DIR, country_iso3)

    # Make a graph
    G = nx.Graph()
    G.graph['country'] = country_iso3

    # TODO: Add mobility matrix in metadata

    # Read in exposure file
    exposure = gpd.read_file(os.path.join(main_dir, EXPOSURE_DIR, f'{country_iso3}_Exposure.geojson'))
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
        'tot_pop_WP',
        'tot_pop_UN',
        'tot_sad',
        'group_pop_f',
        'group_pop_m'
    ]
    exposure = exposure[columns]
    # Rename some
    rename_dict = {
        'ADM2_EN': 'name',
    }
    exposure = exposure.rename(columns=rename_dict)

    # Add the exposure info
    G.graph['age_groups'] = age_groups
    for row in exposure.to_dict(orient='records'):
        G.add_node(row['ADM2_PCODE'], **row)

    # TODO: Add covid cases

    # TODO: Add vulnerability

    # Write out
    data = nx.readwrite.json_graph.node_link_data(G)
    outdir = os.path.join(main_dir, OUTPUT_DIR)
    Path(outdir).mkdir(parents=True, exist_ok=True)
    outfile = os.path.join(main_dir, OUTPUT_DIR, OUTPUT_FILE.format(country_iso3))
    with open(outfile, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f'Wrote out to {outfile}')


if __name__ == '__main__':
    args = parse_args()
    main(args.country_iso3.upper())
