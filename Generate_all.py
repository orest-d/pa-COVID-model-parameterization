# script that reads WorldPop tiff files and populates the exposure file
import argparse

import logging
from covid_model_parametrization.exposure import exposure
from covid_model_parametrization.vulnerability import vulnerability
from covid_model_parametrization.covid import covid
from covid_model_parametrization.graph import graph

from covid_model_parametrization import utils


utils.config_logger()
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("country_iso3", help="Country ISO3")
    parser.add_argument(
        "-d",
        "--download",
        action="store_true",
        help="Download all -- required upon first run",
    )
    parser.add_argument(
        "-m", "--mobility", required=True, help="Path to mobility CSV file"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    country_iso3 = args.country_iso3.upper() 
    exposure(country_iso3, download_worldpop=args.download)
    vulnerability(country_iso3, download_ghs=args.download)
    covid(country_iso3, download_covid=args.download)
    graph(country_iso3, args.mobility)
