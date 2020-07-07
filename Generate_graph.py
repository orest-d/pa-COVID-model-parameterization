import argparse
import logging
from covid_model_parametrization import utils
from covid_model_parametrization.graph import graph


utils.config_logger()
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('country_iso3', help='Country ISO3')
    parser.add_argument('-m', '--mobility', required=True, help="Path to mobility CSV file")
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    graph(args.country_iso3.upper(), args.mobility)
