# script that pulls data from several sources and generate COVID-19 breakdown for subnational SEIR model

import argparse
import utils
import datetime
import pandas as pd
import geopandas as gpd
from pathlib import Path
import os
import logging
import itertools
import getpass
from Generate_SADD_exposure_from_tiff import GENDER_CLASSES, AGE_CLASSES

CONFIG_FILE = 'config.yml'
DIR_PATH = os.path.dirname(os.path.realpath(__file__))
INPUT_DIR = 'Inputs'
OUTPUT_CSV = '{}_COVID.csv'
OUTPUT_DIR = os.path.join('Outputs', '{}', 'COVID')

# Exposure files
EXP_DIR = os.path.join('Outputs', '{}', 'Exposure_SADD')
EXP_FILE = '{}_Exposure.geojson'

# COVID
COVID_DIR = 'COVID'

# maybe we can move this to the yml file?
HLX_TAG_TOTAL_CASES='#affected+infected+confirmed+total'
HLX_TAG_TOTAL_DEATHS='#affected+infected+dead+total'
HLX_TAG_DATE='#date'
HLX_TAG_ADM1_NAME='#adm1+name'
HLX_TAG_ADM1_PCODE='#adm1+pcode'
HLX_TAG_ADM2_PCODE='#adm2+pcode'

utils.config_logger()
logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('country_iso3',
                        help='Country ISO3')
    parser.add_argument('-d', '--download-covid', action='store_true',
                        help='Download the COVID-19 data')
    return parser.parse_args()

def main(country_iso3, download_covid=False):
    # Get config file
    config = utils.parse_yaml(CONFIG_FILE)[country_iso3]

    # Get input covid file
    input_dir = os.path.join(DIR_PATH, INPUT_DIR, country_iso3)
   
    # Download latest covid file tiles and read them in
    if download_covid:
        get_covid_data(config['covid'], country_iso3, input_dir)
    df_covid = pd.read_csv('{}/{}'.format(os.path.join(input_dir, COVID_DIR),\
                            config['covid']['filename']), header=config['covid']['header'],\
                            skiprows=config['covid']['skiprows'])
    # convert to standard HLX
    if 'hlx_dict' in config['covid']:
        df_covid=df_covid.rename(columns=config['covid']['hlx_dict'])

    # in some files we have province explicitely
    df_covid[HLX_TAG_ADM1_NAME]= df_covid[HLX_TAG_ADM1_NAME].str.replace(' Province','')
    if 'replace_dict' in config['covid']:
        df_covid[HLX_TAG_ADM1_NAME] = df_covid[HLX_TAG_ADM1_NAME].replace(config['covid']['replace_dict'])
    
    # convert to float
    # TODO check conversions
    if df_covid[HLX_TAG_TOTAL_CASES].dtype == 'object':
        df_covid[HLX_TAG_TOTAL_CASES]=df_covid[HLX_TAG_TOTAL_CASES].str.replace(',','')
    df_covid[HLX_TAG_TOTAL_CASES]=pd.to_numeric(df_covid[HLX_TAG_TOTAL_CASES],errors='coerce')
    if df_covid[HLX_TAG_TOTAL_CASES].dtype == 'object':
       df_covid[HLX_TAG_TOTAL_DEATHS]=df_covid[HLX_TAG_TOTAL_DEATHS].str.replace('-','')
    df_covid[HLX_TAG_TOTAL_DEATHS]=pd.to_numeric(df_covid[HLX_TAG_TOTAL_DEATHS],errors='coerce')

    df_covid.fillna(0,inplace=True)
    
    # Get exposure file
    try:
        exposure_file=f'{DIR_PATH}/{EXP_DIR.format(country_iso3)}/{EXP_FILE.format(country_iso3)}'
        exposure_gdf=gpd.read_file(exposure_file)
    except:
        logger.info(f'Cannot get exposure file for {country_iso3}, COVID file not generate')
    
    # add pcodes
    ADM1_names = dict()
    for k, v in exposure_gdf.groupby('ADM1_EN'):
        ADM1_names[k] = v.iloc[0,:].ADM1_PCODE
    df_covid[HLX_TAG_ADM1_PCODE]= df_covid[HLX_TAG_ADM1_NAME].map(ADM1_names)
    if(df_covid[HLX_TAG_ADM1_PCODE].isnull().sum()>0):
        logger.info('missing PCODE for the following admin units ',df_covid[df_covid[HLX_TAG_ADM1_PCODE].isnull()])
    #recalculate total for each ADM1 unit
    gender_age_groups = list(itertools.product(GENDER_CLASSES, AGE_CLASSES))
    gender_age_group_names = ['{}_{}'.format(gender_age_group[0], gender_age_group[1]) for gender_age_group in
                              gender_age_groups]

    # TODO fields should depend on country
    output_df_covid=pd.DataFrame(columns=[HLX_TAG_ADM1_PCODE,
                                          HLX_TAG_ADM2_PCODE,
                                          HLX_TAG_DATE,
                                          HLX_TAG_TOTAL_CASES,
                                          HLX_TAG_TOTAL_DEATHS])

    # make a loop over reported cases and downscale ADM1 to ADM2
    # print(df_covid.sum())
    for _, row in df_covid.iterrows():
        adm2_pop_fractions=get_adm2_to_adm1_pop_frac(row[HLX_TAG_ADM1_PCODE],exposure_gdf,gender_age_group_names)
        adm1pcode=row[HLX_TAG_ADM1_PCODE]
        date=row[HLX_TAG_DATE]
        adm1cases=row[HLX_TAG_TOTAL_CASES]
        adm1deaths=row[HLX_TAG_TOTAL_DEATHS]
        adm2cases=[v*adm1cases for v in adm2_pop_fractions.values()]
        adm2deaths=[v*adm1deaths for v in adm2_pop_fractions.values()]
        adm2pcodes=[v for v in adm2_pop_fractions.keys()]
        raw_data = {HLX_TAG_ADM1_PCODE:adm1pcode,
                    HLX_TAG_ADM2_PCODE:adm2pcodes,
                    HLX_TAG_DATE:date,
                    HLX_TAG_TOTAL_CASES:adm2cases,
                    HLX_TAG_TOTAL_DEATHS:adm2deaths}
        output_df_covid=output_df_covid.append(pd.DataFrame(raw_data),ignore_index=True)
    
    # cross-check: the total must match
    if(abs((output_df_covid[HLX_TAG_TOTAL_CASES].sum()-\
        df_covid[HLX_TAG_TOTAL_CASES].sum()))>10):
        logger.info('WARNING The sum of input and output files don\'t match')

    # Write to file
    output_df_covid['created_at'] = str(datetime.datetime.now())
    output_df_covid['created_by'] = getpass.getuser()
    output_csv = get_output_filename(country_iso3)
    logger.info(f'Writing to file {output_csv}')
    output_df_covid.to_csv(f'{DIR_PATH}/{output_csv}',index=False)

def get_output_filename(country_iso3):
    # get the filename for writing the file
    output_dir = OUTPUT_DIR.format(country_iso3)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    return os.path.join(output_dir, OUTPUT_CSV.format(country_iso3))

def get_adm2_to_adm1_pop_frac(pcode,exposure_gdf,gender_age_group_names):
    # get the full exposure and returns a dictionary with 
    # the fraction of the population of each ADM2
    exp_adm1=exposure_gdf[exposure_gdf['ADM1_PCODE']==pcode]
    adm2_pop=exp_adm1[gender_age_group_names].sum(axis=1)
    adm2_pop_fractions=dict(zip(exp_adm1['ADM2_PCODE'],adm2_pop/adm2_pop.sum()))
    return adm2_pop_fractions 

def get_covid_data(config, country_iso3, input_dir):
    # download covid data from HDX
    logger.info(f'Getting COVID data for {country_iso3}')
    download_dir = os.path.join(input_dir, COVID_DIR)
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    covid_filename = os.path.join(download_dir,config['filename'])
    try:
        utils.download_url(config['url'], covid_filename)
    except Exception:
        logger.info(f'Cannot get COVID file from for {country_iso3}')

if __name__ == '__main__':
    args = parse_args()
    main(args.country_iso3.upper(), download_covid=args.download_covid)