# script that pulls data from several sources and generate COVID-19 breakdown for subnational SEIR model

import argparse
import utils
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
OUTPUT_GEOJSON = '{country_iso3}_covid.csv'
OUTPUT_DIR = os.path.join('Outputs', '{}', 'COVID')
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
    # convert to float
    # TODO check conversions
    df_covid['#affected+infected+cases']=df_covid['#affected+infected+cases'].str.replace(',','')
    df_covid['#affected+infected+cases']=pd.to_numeric(df_covid['#affected+infected+cases'],errors='coerce')
    
    df_covid['#affected+infected+deaths']=df_covid['#affected+infected+deaths'].str.replace('-','')
    df_covid['#affected+infected+deaths']=pd.to_numeric(df_covid['#affected+infected+deaths'],errors='coerce')

    df_covid.fillna(0,inplace=True)
    
    # Get exposure file
    try:
        exposure_file=f'{DIR_PATH}/{EXP_DIR.format(country_iso3)}/{EXP_FILE.format(country_iso3)}'
        exposure_gdf=gpd.read_file(exposure_file)
    except:
        logger.info(f'Cannot get exposure file for {country_iso3}, COVID file not generate')
        return
    
    # add pcodes
    ADM1_names = dict()
    for k, v in exposure_gdf.groupby('ADM1_EN'):
        ADM1_names[k] = v.iloc[0,:].ADM1_PCODE
    df_covid['#adm1+pcode']= df_covid['#adm1+name'].map(ADM1_names)
    if(df_covid['#adm1+pcode'].isnull().sum()>0):
        logger.info('missing PCODE for the following admin units ',df_covid[df_covid['#adm1+pcode'].isnull()])
    
    #recalculate total for each ADM1 unit
    gender_age_groups = list(itertools.product(GENDER_CLASSES, AGE_CLASSES))
    gender_age_group_names = ['{}_{}'.format(gender_age_group[0], gender_age_group[1]) for gender_age_group in
                              gender_age_groups]
    
    # TODO fields should depend on country
    output_df_covid=pd.DataFrame(columns=['#adm1+pcode','#adm2+pcode','#date','#affected+infected+cases',\
                                        '#affected+infected+deaths'])
    # make a loop over reported cases
    for _, row in df_covid.iterrows():
        adm2_pop_fractions=get_adm2_to_adm1_pop_frac(row['#adm1+pcode'],exposure_gdf,gender_age_group_names)
        adm1pcode=row['#adm1+pcode']
        date=row['#date']
        adm1cases=row['#affected+infected+cases']
        adm1deaths=row['#affected+infected+deaths']
        adm2pcodes=[v for v in adm2_pop_fractions.keys()]
        adm2cases=[v*adm1cases for v in adm2_pop_fractions.values()]
        adm2deaths=[v*adm1deaths for v in adm2_pop_fractions.values()]
        raw_data = {'#adm1+pcode':adm1pcode,'#adm2+pcode':adm2pcodes,\
                    '#date':date,'#affected+infected+cases':adm2cases,'#affected+infected+deaths':adm2cases}
        output_df_covid=output_df_covid.append(pd.DataFrame(raw_data),ignore_index=True)
    
    # Write to file
    output_df_covid['created_at'] = str(datetime.datetime.now())
    output_df_covid['created_by'] = getpass.getuser()
    output_csv = get_output_filename(country_iso3)
    logger.info(f'Writing to file {output_geojson}')
    utils.write_to_geojson(output_geojson, ADM2boundaries)

def get_output_filename(country_iso3):
    output_dir = OUTPUT_DIR.format(country_iso3)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    return os.path.join(output_dir, OUTPUT_GEOJSON.format(country_iso3))

def get_adm2_to_adm1_pop_frac(pcode,exposure_gdf,gender_age_group_names):
    # filter ADM1
    exp_adm1=exposure_gdf[exposure_gdf['ADM1_PCODE']==pcode]
    adm2_pop=exp_adm1[gender_age_group_names].sum(axis=1)
    adm2_pop_fractions=dict(zip(exp_adm1['ADM2_PCODE'],adm2_pop/adm2_pop.sum()))
    return adm2_pop_fractions


    # print(tot_sad)
 
    



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