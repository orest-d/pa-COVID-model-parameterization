# script that pulls data from several sources and generate COVID-19 breakdown for subnational SEIR model

# TODO automatically download file as done in Generate_vulnerability_file.py

# link for AFG
# https://docs.google.com/spreadsheets/d/1F-AMEDtqK78EA6LYME2oOsWQsgJi4CT3V_G4Uo-47Rg/edit?usp=sharing

import pandas as pd
import geopandas as gpd
import os

COVID_FILE='Inputs/COVID_Cases/Afghanistan COVID-19 Stats by Province.xlsx'
INPUT_SHP = 'Inputs/Shapefiles/afg_admbnda_adm2_agcho_20180522/afg_admbnda_adm2_agcho_20180522.shp'
OUTPUT_XLSX = 'Outputs/COVID_cases/COVIDcases.xlsx'

dir_path = os.path.dirname(os.path.realpath(__file__))

df_covid = (pd.read_excel('{}/{}'.format(dir_path,COVID_FILE), header=[0], skiprows=[1]))
df_covid['Province']=df_covid['Province'].str.replace(' Province','')
df_covid['Province']=df_covid['Province'].replace({'Helmand':'Hilmand','Paktia':'Paktya','Jowzjan':'Jawzjan',\
    'Panjshir':'Panjsher','Urozgan':'Uruzgan','Sar-e Pol':'Sar-e-Pul','Nimruz':'Nimroz','Wardak':'Maidan Wardak'})
ADM2boundaries=gpd.read_file('{}/{}'.format(dir_path,INPUT_SHP))
ADM1_names = dict()
for k, v in ADM2boundaries.groupby('ADM1_EN'):
    ADM1_names[k] = v.iloc[0,:].ADM1_PCODE

print('latest covid data from {}'.format(df_covid['Date'].max()))

df_covid=df_covid.rename(columns={'Province':'ADM1_EN','Cases':'cases','Recoveries':'recoveries',\
    'Active Cases':'active_cases','Date':'date'})
df_covid['ADM1_PCODE']= df_covid['ADM1_EN'].map(ADM1_names)

df_covid.to_excel(OUTPUT_XLSX)