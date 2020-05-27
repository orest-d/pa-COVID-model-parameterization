# script that pulls data from several sources and generate COVID-19 breakdown for subnational SEIR model

import argparse
import utils
import pandas as pd
import geopandas as gpd
from pathlib import Path
import os
import logging

CONFIG_FILE = 'config.yml'
DIR_PATH = os.path.dirname(os.path.realpath(__file__))
INPUT_DIR = 'Inputs'
OUTPUT_GEOJSON = '{country_iso3}_covid.geojson'
OUTPUT_DIR = os.path.join('Outputs', '{}', 'Covid')
EXP_DIR = os.path.join('Outputs', '{}', 'Exposure_SADD')
EXP_FILE = '{}_Exposure.geojson'

# COVID
COVID_DIR = 'COVID'


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
                            config['covid']['filename']), header=[1], skiprows=0)
    if 'replace_names' in config['covid']:
        df_covid['#adm1+name']= df_covid['#adm1+name'].str.replace(' Province','')
        df_covid['#adm1+name'] = df_covid['#adm1+name'].replace(config['covid']['replace_names'])
    
    exposure_file=f'{DIR_PATH}/{EXP_DIR.format(country_iso3)}/{EXP_FILE.format(country_iso3)}'
    exposure_gdf=gpd.read_file(exposure_file)
    ADM1_names = dict()
    for k, v in exposure_gdf.groupby('ADM1_EN'):
        ADM1_names[k] = v.iloc[0,:].ADM1_PCODE

# print('latest covid data from {}'.format(df_covid['Date'].max()))


def get_covid_data(config, country_iso3, input_dir):
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



# df_covid = (pd.read_excel('{}/{}'.format(dir_path,COVID_FILE), header=[0], skiprows=[1]))
# df_covid['Province']=df_covid['Province'].str.replace(' Province','')
# df_covid['Province']=df_covid['Province'].replace({'Helmand':'Hilmand','Paktia':'Paktya','Jowzjan':'Jawzjan',\
#     'Panjshir':'Panjsher','Urozgan':'Uruzgan','Sar-e Pol':'Sar-e-Pul','Nimruz':'Nimroz','Wardak':'Maidan Wardak'})
# ADM2boundaries=gpd.read_file('{}/{}'.format(dir_path,INPUT_SHP))
# ADM1_names = dict()
# for k, v in ADM2boundaries.groupby('ADM1_EN'):
#     ADM1_names[k] = v.iloc[0,:].ADM1_PCODE

# print('latest covid data from {}'.format(df_covid['Date'].max()))

# df_covid=df_covid.rename(columns={'Province':'ADM1_EN','Cases':'cases','Recoveries':'recoveries',\
#     'Active Cases':'active_cases','Date':'date'})
# df_covid['ADM1_PCODE']= df_covid['ADM1_EN'].map(ADM1_names)
# if(df_covid['ADM1_PCODE'].isnull().sum()>0):
#     print('missing PCODE for ',df_covid[df_covid['ADM1_PCODE'].isnull()])


# df_covid.to_excel(OUTPUT_XLSX)