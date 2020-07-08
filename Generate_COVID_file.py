# script that pulls data from several sources and generate COVID-19 breakdown for subnational SEIR model

import argparse
import logging
from covid_model_parametrization import utils
from covid_model_parametrization.covid import covid


utils.config_logger()
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("country_iso3", help="Country ISO3")
    parser.add_argument(
        "-d", "--download-covid", action="store_true", help="Download the COVID-19 data"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    covid(args.country_iso3.upper(), download_covid=args.download_covid)
