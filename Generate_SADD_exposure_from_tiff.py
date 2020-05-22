# script that reads WorldPop tiff files and populates the exposure file
import os
import datetime
import itertools
import getpass
import argparse
import logging

import geopandas as gpd
from rasterstats import zonal_stats

import utils

INPUT_DIR = 'Inputs'
SHAPEFILE_DIR = 'Shapefiles'
WORLDPOP_DIR = 'WorldPop'
DIR_PATH = os.path.dirname(os.path.realpath(__file__))

CONFIG_FILE = 'config.yml'
OUTPUT_SHP = os.path.join(DIR_PATH, 'Outputs', '{0}', 'Exposure_SADD', '{0}_Exposure.shp')

GENDER_CLASSES = ["f","m"]
AGE_CLASSES = [0,1,5,10,15,20,25,30,35,40,45,50,55,60,65,70,75,80]

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('country_iso3',
                        help='Country ISO3. Options are: afg')
    return parser.parse_args()


def main(country_iso3):
    # Get config file
    config = utils.parse_yaml(CONFIG_FILE)[country_iso3]

    # Get input boundary shape file
    input_dir = os.path.join(DIR_PATH, INPUT_DIR, country_iso3)
    input_shp = os.path.join(input_dir, SHAPEFILE_DIR, config['admin']['directory'], config['admin']['filename'])
    ADM2boundaries = gpd.read_file(input_shp)

    # gender and age groups
    gender_age_groups = list(itertools.product(GENDER_CLASSES, AGE_CLASSES))
    for gender_age_group in gender_age_groups:
        gender_age_group_name = f'{gender_age_group[0]}_{gender_age_group[1]}'
        logger.info(f'analyising gender age {gender_age_group_name}')
        input_tif_file = os.path.join(input_dir, WORLDPOP_DIR,
                                      config['worldpop']['sadd'].format(gender_age_group[0],gender_age_group[1]))
        zs = zonal_stats(input_shp, input_tif_file, stats='sum')
        total_pop=[district_zs.get('sum') for district_zs in zs]
        ADM2boundaries[gender_age_group_name]=total_pop

    # total population for cross check
    logger.info('Cross-checking with total pop')
    input_tiff_pop = os.path.join(input_dir, WORLDPOP_DIR, config['worldpop']['pop'])
    zs = zonal_stats(input_shp, input_tiff_pop,stats='sum')
    total_pop=[district_zs.get('sum') for district_zs in zs]
    ADM2boundaries['tot_pop']=total_pop

    # total population UNadj for cross check
    logger.info('Cross-checking with UNadj total pop')
    input_tiff_pop_unadj = os.path.join(input_dir, WORLDPOP_DIR, config['worldpop']['unadj'])
    zs = zonal_stats(input_shp, input_tiff_pop_unadj, stats='sum')
    total_pop=[district_zs.get('sum') for district_zs in zs]
    ADM2boundaries['tot_pop_UNadj']=total_pop

    # total from disaggregated
    logger.info('Getting totals from disaggregated')
    columns_to_sum=['{}_{}'.format(gender_age_group[0],gender_age_group[1]) for gender_age_group in gender_age_groups]
    ADM2boundaries['tot_sad']=ADM2boundaries.loc[:,columns_to_sum].sum(axis=1)

    # adding manually Kochi nomads
    if 'kochi' in config:
        logger.info('Adding Kuchi')
        ADM1_kuchi = config['kochi']['adm1']
        # total population in these provinces
        pop_in_kuchi_ADM1=ADM2boundaries[ADM2boundaries['ADM1_PCODE'].isin(ADM1_kuchi)]['tot_sad'].sum()
        for row_index, row in ADM2boundaries.iterrows():
            if row['ADM1_PCODE'] in ADM1_kuchi:
                tot_kuchi_in_ADM2=0
                for gender_age_group in gender_age_groups:
                    # population weighted
                    gender_age_group_name = f'{gender_age_group[0]}_{gender_age_group[1]}'
                    kuchi_pp=config['kochi']['total']*(row[gender_age_group_name]/pop_in_kuchi_ADM1)
                    ADM2boundaries.loc[row_index,gender_age_group_name]=row[gender_age_group_name]+kuchi_pp
                    tot_kuchi_in_ADM2+=kuchi_pp
                ADM2boundaries.loc[row_index,'kuchi']=tot_kuchi_in_ADM2
                comment = f'Added in total {tot_kuchi_in_ADM2} Kuchi nomads to WorldPop estimates'
                ADM2boundaries.loc[row_index,'comment'] = comment

    # Write to file
    ADM2boundaries['created_at'] = str(datetime.datetime.now())
    ADM2boundaries['created_by'] = getpass.getuser()
    output_shp = OUTPUT_SHP.format(country_iso3)
    logger.info(f'Writing to file {output_shp}')
    ADM2boundaries.to_file(output_shp)


if __name__ == '__main__':
    args = parse_args()
    main(args.country_iso3.upper())
