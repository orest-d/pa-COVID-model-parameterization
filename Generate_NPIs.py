import os
import logging
from pathlib import Path

import pandas as pd

from utils.hdx_api import query_api

ACAPS_HDX_ADDRESS = 'acaps-covid19-government-measures-dataset'
OUTPUT_DIR = os.path.join('Inputs', 'ACAPS_NPIs')

logger = logging.getLogger()


def main():
    # Get ACAPS and Natural Earth data
    logger.info('Getting ACAPS data')
    df_acaps = get_df_acaps()
    logger.info('Done')


def get_df_acaps() -> pd.DataFrame:
    # Get the ACAPS data from HDX
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    filename = list(query_api(ACAPS_HDX_ADDRESS, OUTPUT_DIR).values())[0]
    filepath = os.path.join(OUTPUT_DIR, filename)
    return pd.read_excel(filepath, sheet_name='Database')


if __name__ == '__main__':
    main()
