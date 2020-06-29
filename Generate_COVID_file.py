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
HLX_TAG_ADM2_NAME='#adm2+name'
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
    df_covid[HLX_TAG_ADM1_NAME]= df_covid[HLX_TAG_ADM1_NAME].str.replace('Province','')
    df_covid[HLX_TAG_ADM1_NAME]= df_covid[HLX_TAG_ADM1_NAME].str.strip()
    if 'replace_dict' in config['covid'] and config['covid']['admin_level']==1: 
        df_covid[HLX_TAG_ADM1_NAME] = df_covid[HLX_TAG_ADM1_NAME].replace(config['covid']['replace_dict'])
    if 'replace_dict' in config['covid'] and config['covid']['admin_level']==2: 
        df_covid[HLX_TAG_ADM2_NAME] = df_covid[HLX_TAG_ADM2_NAME].replace(config['covid']['replace_dict'])
    
    # convert to numeric
    if config['covid']['cases']:
        df_covid[HLX_TAG_TOTAL_CASES]=convert_to_numeric(df_covid[HLX_TAG_TOTAL_CASES])
    if config['covid']['deaths']:
        df_covid[HLX_TAG_TOTAL_DEATHS]=convert_to_numeric(df_covid[HLX_TAG_TOTAL_DEATHS])
    df_covid.fillna(0,inplace=True)
    
    # Get exposure file
    try:
        exposure_file=f'{DIR_PATH}/{EXP_DIR.format(country_iso3)}/{EXP_FILE.format(country_iso3)}'
        exposure_gdf=gpd.read_file(exposure_file)
    except:
        logger.error(f'Cannot get exposure file for {country_iso3}, COVID file not generate')

    output_fields=[ HLX_TAG_ADM1_PCODE,
                    HLX_TAG_ADM2_PCODE,
                    HLX_TAG_DATE,
                    HLX_TAG_TOTAL_CASES,
                    HLX_TAG_TOTAL_DEATHS]
    output_df_covid=pd.DataFrame(columns=output_fields)

    if config['covid']['admin_level']==2:
        ADM2_names=get_dict_pcodes(exposure_gdf,config['covid']['adm2_name_exp'],'ADM2_PCODE')
        df_covid[HLX_TAG_ADM2_PCODE]= df_covid[HLX_TAG_ADM2_NAME].map(ADM2_names)
        if(df_covid[HLX_TAG_ADM2_PCODE].isnull().sum()>0):
            logger.warning('missing PCODE for the following admin units ',df_covid[df_covid[HLX_TAG_ADM2_PCODE].isnull()])        
        ADM2_ADM1_pcodes=get_dict_pcodes(exposure_gdf,'ADM2_PCODE')
        df_covid[HLX_TAG_ADM1_PCODE]= df_covid[HLX_TAG_ADM2_PCODE].map(ADM2_ADM1_pcodes)
        adm1pcode=df_covid[HLX_TAG_ADM1_PCODE]
        adm2pcodes=df_covid[HLX_TAG_ADM2_PCODE]
        date=pd.to_datetime(df_covid[HLX_TAG_DATE],format=config['covid']['date_format'])
        date=date.dt.strftime('%Y-%m-%d')
        adm2cases=df_covid[HLX_TAG_TOTAL_CASES] if config['covid']['cases'] else None
        adm2deaths=df_covid[HLX_TAG_TOTAL_DEATHS] if config['covid']['deaths'] else None
        raw_data = {HLX_TAG_ADM1_PCODE:adm1pcode,
                    HLX_TAG_ADM2_PCODE:adm2pcodes,
                    HLX_TAG_DATE:date,
                    HLX_TAG_TOTAL_CASES:adm2cases,
                    HLX_TAG_TOTAL_DEATHS:adm2deaths}
        output_df_covid=output_df_covid.append(pd.DataFrame(raw_data),ignore_index=True)
    elif config['covid']['admin_level']==1:
        ADM1_names = get_dict_pcodes(exposure_gdf,config['covid']['adm1_name_exp'],'ADM1_PCODE')
        df_covid[HLX_TAG_ADM1_PCODE]= df_covid[HLX_TAG_ADM1_NAME].map(ADM1_names)
        if(df_covid[HLX_TAG_ADM1_PCODE].isnull().sum()>0):
            logger.warning('missing PCODE for the following admin units :')
            logger.warning(df_covid[df_covid[HLX_TAG_ADM1_PCODE].isnull()][[HLX_TAG_ADM1_NAME,HLX_TAG_DATE]])
        #recalculate total for each ADM1 unit
        gender_age_groups = list(itertools.product(GENDER_CLASSES, AGE_CLASSES))
        gender_age_group_names = ['{}_{}'.format(gender_age_group[0], gender_age_group[1]) for gender_age_group in
                                gender_age_groups]

        
        for _, row in df_covid.iterrows():
            adm2_pop_fractions=get_adm2_to_adm1_pop_frac(row[HLX_TAG_ADM1_PCODE],exposure_gdf,gender_age_group_names)
            adm1pcode=row[HLX_TAG_ADM1_PCODE]
            date=datetime.datetime.strptime(row[HLX_TAG_DATE],config['covid']['date_format']).strftime('%Y-%m-%d')
            adm2cases=scale_adm1_by_adm2_pop(config['covid']['cases'],HLX_TAG_TOTAL_CASES,row,adm2_pop_fractions)
            adm2deaths=scale_adm1_by_adm2_pop(config['covid']['deaths'],HLX_TAG_TOTAL_DEATHS,row,adm2_pop_fractions)
        
            adm2pcodes=[v for v in adm2_pop_fractions.keys()]
            raw_data = {HLX_TAG_ADM1_PCODE:adm1pcode,
                        HLX_TAG_ADM2_PCODE:adm2pcodes,
                        HLX_TAG_DATE:date,
                        HLX_TAG_TOTAL_CASES:adm2cases,
                        HLX_TAG_TOTAL_DEATHS:adm2deaths}
            output_df_covid=output_df_covid.append(pd.DataFrame(raw_data),ignore_index=True)
    else:
        logger.error(f'Missing admin_level info for COVID data')
    # cross-check: the total must match
    if(abs((output_df_covid[HLX_TAG_TOTAL_CASES].sum()-\
        df_covid[HLX_TAG_TOTAL_CASES].sum()))>10):
        logger.warning('The sum of input and output files don\'t match')
    
    if not config['covid']['cumulative']:
        logger.info(f'Calculating cumulative numbers COVID data')
        groups=[HLX_TAG_ADM1_PCODE,HLX_TAG_ADM2_PCODE,HLX_TAG_DATE]
        # get sum by day (in case multiple reports per day)
        output_df_covid=output_df_covid.groupby(groups).sum().sort_values(by=HLX_TAG_DATE)
        # get cumsum by day (grouped by ADM2)
        output_df_covid=output_df_covid.groupby(HLX_TAG_ADM2_PCODE).cumsum().reset_index()
        
    # Write to file
    output_df_covid['created_at'] = str(datetime.datetime.now())
    output_df_covid['created_by'] = getpass.getuser()
    output_csv = get_output_filename(country_iso3)
    logger.info(f'Writing to file {output_csv}')
    output_df_covid.to_csv(f'{DIR_PATH}/{output_csv}',index=False)

def get_dict_pcodes(exposure,adm_unit_name,adm_unit_pcode='ADM1_PCODE'):
    pcode_dict=dict()
    for k, v in exposure.groupby(adm_unit_name):
        pcode_dict[k] = v.iloc[0,:][adm_unit_pcode]
    return(pcode_dict)

def scale_adm1_by_adm2_pop(config_val,tag,df_row,fractions):
    if config_val:
        adm1val=df_row[tag]
        adm2val=[v*adm1val for v in fractions.values()]
    else:
        adm2val=None
    return adm2val

def convert_to_numeric(df_col):
    # TODO check conversions
    if df_col.dtype == 'object':
        df_col=df_col.str.replace(',','')
        df_col=df_col.str.replace('-','')
        df_col=pd.to_numeric(df_col,errors='coerce')
    return df_col

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
        logger.warning(f'Cannot download COVID file from for {country_iso3}')

if __name__ == '__main__':
    args = parse_args()
    main(args.country_iso3.upper(), download_covid=args.download_covid)