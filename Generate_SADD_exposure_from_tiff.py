# script that reads WorldPop tiff files and populates the exposure file
import argparse

import logging
from covid_model_parametrization.exposure import exposure
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
        help="Download the WorldPop data -- required upon first run",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    exposure(args.country_iso3.upper(), download_worldpop=args.download)
