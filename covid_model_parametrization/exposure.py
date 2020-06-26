import os
import datetime
import itertools
import getpass
import argparse
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
from rasterstats import zonal_stats

from covid_model_parametrization import utils
from covid_model_parametrization.config import Config


utils.config_logger()
logger = logging.getLogger(__name__)

def exposure(country_iso3, download_worldpop=False, config=None):

    # Get parameters file
    if config is None:
        config = Config()
    parameters = config.parameters[country_iso3]

    # Get input boundary shape file
    input_dir = os.path.join(config.DIR_PATH, config.INPUT_DIR, country_iso3)
    input_shp = os.path.join(input_dir, config.SHAPEFILE_DIR, parameters['admin']['directory'],
                             f'{parameters["admin"]["directory"]}.shp')
    ADM2boundaries = gpd.read_file(input_shp)

    # Download the worldpop data
    if download_worldpop:
        get_worldpop_data(country_iso3, input_dir, config)

    # gender and age groups
    gender_age_groups = list(itertools.product(config.GENDER_CLASSES, config.AGE_CLASSES))
    for gender_age_group in gender_age_groups:
        gender_age_group_name = f'{gender_age_group[0]}_{gender_age_group[1]}'
        logger.info(f'analyising gender age {gender_age_group_name}')
        input_tif_file = os.path.join(input_dir, config.WORLDPOP_DIR,
                                      config.WORLDPOP_FILENAMES['sadd'].format(country_iso3=country_iso3.lower(),
                                                                        gender=gender_age_group[0],
                                                                        age=gender_age_group[1]))
        zs = zonal_stats(input_shp, input_tif_file, stats='sum')
        total_pop=[district_zs.get('sum') for district_zs in zs]
        ADM2boundaries[gender_age_group_name]=total_pop

    # total population for cross check
    logger.info('adding total population')
    input_tiff_pop = os.path.join(input_dir, config.WORLDPOP_DIR,
                                  config.WORLDPOP_FILENAMES['pop'].format(country_iso3=country_iso3.lower()))
    zs = zonal_stats(input_shp, input_tiff_pop,stats='sum')
    total_pop=[district_zs.get('sum') for district_zs in zs]
    ADM2boundaries['tot_pop_WP']=total_pop

    # total population UNadj for cross check
    logger.info('adding total population UN adjusted')
    input_tiff_pop_unadj = os.path.join(input_dir, config.WORLDPOP_DIR,
                                        config.WORLDPOP_FILENAMES['unadj'].format(country_iso3=country_iso3.lower()))
    zs = zonal_stats(input_shp, input_tiff_pop_unadj, stats='sum')
    total_pop=[district_zs.get('sum') for district_zs in zs]
    ADM2boundaries['tot_pop_UN']=total_pop

    # total from disaggregated
    logger.info('scaling SADD data to match UN Adjusted population estimates')
    gender_age_group_names = ['{}_{}'.format(gender_age_group[0], gender_age_group[1]) for gender_age_group in
                              gender_age_groups]
    for index, row in ADM2boundaries.iterrows():
        tot_UN = row['tot_pop_UN']
        tot_sad = row[gender_age_group_names].sum()
        try:
            ADM2boundaries.loc[index, gender_age_group_names] *= tot_UN / tot_sad
        except ZeroDivisionError:
            region_name = row[f'ADM2_{parameters["admin"]["language"]}']
            logger.warning(f'The sum across all genders and ages for admin region {region_name} is 0')

    if 'pop_co' in parameters:
        print('Further scaling SADD data to match CO estimates')
        # scaling at the ADM1 level to match figures used by Country Office instead of UN stats
        input_pop_co_filename = os.path.join(input_dir, config.CO_DIR, parameters['pop_co']['filename'])
        df_operational_figures = pd.read_excel(input_pop_co_filename, usecols='A,D')
        df_operational_figures['Province'] = (df_operational_figures['Province']
                                              .replace(parameters['pop_co']['province_names']))
        # creating dictionary and add pcode the pcode
        ADM1_names = dict()
        for k, v in ADM2boundaries.groupby('ADM1_EN'):
            ADM1_names[k] = v.iloc[0, :].ADM1_PCODE
        df_operational_figures['ADM1_PCODE'] = df_operational_figures['Province'].map(ADM1_names)
        if (df_operational_figures['ADM1_PCODE'].isnull().sum() > 0):
            print('missing PCODE for: ', df_operational_figures[df_operational_figures['ADM1_PCODE'].isnull()])
        # get total by ADM1
        tot_co_adm1 = df_operational_figures.groupby('ADM1_PCODE').sum()['Estimated Population - 2020']
        tot_sad_adm1 = ADM2boundaries.groupby('ADM1_PCODE')[gender_age_group_names].sum().sum(axis=1)
        for index, row in ADM2boundaries.iterrows():
            adm1_pcode = row['ADM1_PCODE']
            pop_co = tot_co_adm1.get(adm1_pcode)
            pop_sad = tot_sad_adm1.get(adm1_pcode)
            ADM2boundaries.loc[index, gender_age_group_names] *= pop_co / pop_sad

    ADM2boundaries['tot_sad'] = ADM2boundaries.loc[:, gender_age_group_names].sum(axis=1)

    # adding manually Kochi nomads
    if 'kochi' in parameters:
        logger.info('Adding Kuchi')
        ADM1_kuchi = parameters['kochi']['adm1']
        # total population in these provinces
        pop_in_kuchi_ADM1=ADM2boundaries[ADM2boundaries['ADM1_PCODE'].isin(ADM1_kuchi)]['tot_sad'].sum()
        for row_index, row in ADM2boundaries.iterrows():
            if row['ADM1_PCODE'] in ADM1_kuchi:
                tot_kuchi_in_ADM2=0
                for gender_age_group in gender_age_groups:
                    # population weighted
                    gender_age_group_name = f'{gender_age_group[0]}_{gender_age_group[1]}'
                    kuchi_pp=parameters['kochi']['total']*(row[gender_age_group_name]/pop_in_kuchi_ADM1)
                    ADM2boundaries.loc[row_index,gender_age_group_name]=row[gender_age_group_name]+kuchi_pp
                    tot_kuchi_in_ADM2+=kuchi_pp
                ADM2boundaries.loc[row_index,'kuchi']=tot_kuchi_in_ADM2
                comment = f'Added in total {tot_kuchi_in_ADM2} Kuchi nomads to WorldPop estimates'
                ADM2boundaries.loc[row_index,'comment'] = comment

    # Write to file
    ADM2boundaries['created_at'] = str(datetime.datetime.now())
    ADM2boundaries['created_by'] = getpass.getuser()
    output_geojson = get_output_filename(country_iso3, config)
    logger.info(f'Writing to file {output_geojson}')
    utils.write_to_geojson(output_geojson, ADM2boundaries)


def get_worldpop_data(country_iso3, input_dir, config):
    output_dir = os.path.join(input_dir, config.WORLDPOP_DIR)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    for age in config.AGE_CLASSES:
        for gender in config.GENDER_CLASSES:
            url = config.WORLDPOP_URL['age_sex'].format(country_iso3.upper(), country_iso3.lower(), gender, age)
            utils.download_ftp(url, os.path.join(output_dir, url.split('/')[-1]))
    for pop_type in ['pop', 'unadj']:
        url = config.WORLDPOP_URL[pop_type].format(country_iso3.upper(), country_iso3.lower())
        utils.download_ftp(url, os.path.join(output_dir, url.split('/')[-1]))


def get_output_filename(country_iso3, config):
    output_dir = config.SADD_output_dir().format(country_iso3)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    return os.path.join(output_dir, config.EXPOSURE_GEOJSON.format(country_iso3))

