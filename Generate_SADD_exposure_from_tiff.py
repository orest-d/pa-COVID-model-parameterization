from rasterstats import zonal_stats
import rasterio
import datetime
import getpass
import geopandas as gpd
import pandas as pd
import itertools
import os

# script that reads WorldPop tiff files and populates the exposure file
country_iso3='AFG'

# input shapefile downloaded from https://data.humdata.org/dataset/afg-admin-ADM2boundaries 
if country_iso3=='AFG':
    INPUT_SHP = 'Inputs/Shapefiles/afg_admbnda_adm2_agcho_20180522/afg_admbnda_adm2_agcho_20180522.shp'
    INPUT_TIFF_SADD = 'Inputs/WorldPop/afg_{}_{}_2020.tif'
    INPUT_TIFF_POP = 'Inputs/WorldPop/afg_ppp_2020.tif'
    INPUT_TIFF_POP_UNadj='Inputs/WorldPop/afg_ppp_2020_UNadj.tif'

OUTPUT_SHP = 'Outputs/Exposure_SADD/{}_Exposure.shp'.format(country_iso3)
dir_path = os.path.dirname(os.path.realpath(__file__))
ADM2boundaries=gpd.read_file('{}/{}'.format(dir_path,INPUT_SHP))

gender_classes=["f","m"]
age_classes=[0,1,5,10,15,20,25,30,35,40,45,50,55,60,65,70,75,80]
gender_age_groups=list(itertools.product(gender_classes,age_classes))
gender_age_group_names=['{}_{}'.format(gender_age_group[0],gender_age_group[1]) for gender_age_group in gender_age_groups]

# # gender and age groups
for gender_age_group in gender_age_groups:
    gender_age_group_name='{}_{}'.format(gender_age_group[0],gender_age_group[1])
    print('analyising gender age ',gender_age_group_name)
    input_tif_file=INPUT_TIFF_SADD.format(gender_age_group[0],gender_age_group[1])
    zs = zonal_stats('{}/{}'.format(dir_path,INPUT_SHP),'{}/{}'.format(dir_path,input_tif_file),stats='sum')
    total_pop=[district_zs.get('sum') for district_zs in zs]
    ADM2boundaries[gender_age_group_name]=total_pop

# total population for cross check
print('adding total population ')
zs = zonal_stats('{}/{}'.format(dir_path,INPUT_SHP),'{}/{}'.format(dir_path,INPUT_TIFF_POP),stats='sum')
total_pop=[district_zs.get('sum') for district_zs in zs]
ADM2boundaries['tot_pop']=total_pop

# total population UNadj for cross check
print('adding total population UN adjusted')
zs = zonal_stats('{}/{}'.format(dir_path,INPUT_SHP),'{}/{}'.format(dir_path,INPUT_TIFF_POP_UNadj),stats='sum')
total_pop=[district_zs.get('sum') for district_zs in zs]
ADM2boundaries['tot_UN']=total_pop

# Scaling to match UN adjusted
print('scaling SADD data to match UN Adjusted population estimates')
for index, row in ADM2boundaries.iterrows():
    tot_UN=row['tot_UN']
    tot_sad=row[gender_age_group_names].sum()
    ADM2boundaries.loc[index,gender_age_group_names]*=tot_UN/tot_sad

if country_iso3=='AFG':
    print('Further scaling SADD data to match CO estimates')
    # scaling at the ADM1 level to match figures used by Country Office instead of UN stats
    INPUT_POP_CO='Inputs/InputsFromCOs/AFG/AFG_PopEstimatesOperationalPlanning.xlsx'
    df_operational_figures=pd.read_excel('{}/{}'.format(dir_path,INPUT_POP_CO),usecols='A,D')
    df_operational_figures['Province']=df_operational_figures['Province'].\
        replace({'Helmand':'Hilmand','Herat':'Hirat','Nooristan':'Nuristan','Sar-e-pul':'Sar-e-Pul',\
            'Urozgan':'Uruzgan','Wardak':'Maidan Wardak'})
    # creating dictionary and add pcode the pcode
    ADM1_names = dict()
    for k, v in ADM2boundaries.groupby('ADM1_EN'):
        ADM1_names[k] = v.iloc[0,:].ADM1_PCODE
    df_operational_figures['ADM1_PCODE']= df_operational_figures['Province'].map(ADM1_names)
    if(df_operational_figures['ADM1_PCODE'].isnull().sum()>0):
        print('missing PCODE for: ',df_operational_figures[df_operational_figures['ADM1_PCODE'].isnull()])
    # get total by ADM1
    tot_co_adm1=df_operational_figures.groupby('ADM1_PCODE').sum()['Estimated Population - 2020']
    tot_sad_adm1=ADM2boundaries.groupby('ADM1_PCODE')[gender_age_group_names].sum().sum(axis=1)
    for index, row in ADM2boundaries.iterrows():
        adm1_pcode=row['ADM1_PCODE']
        pop_co=tot_co_adm1.get(adm1_pcode)
        pop_sad=tot_sad_adm1.get(adm1_pcode)
        ADM2boundaries.loc[index,gender_age_group_names]*=pop_co/pop_sad
   
    # adding manually Kochi nomads
    total_kuchi_in_afg=2000000
    # East/South of country
    # from CO: The main focus would be in east as the Kuchis spend winter primarily Kunar, Laghman, Nuristan, Nangahar
    ADM1_kuchi = ["AF15","AF07","AF16","AF06"]
    # total population in these provinces
    pop_in_kuchi_ADM1=ADM2boundaries[ADM2boundaries['ADM1_PCODE'].isin(ADM1_kuchi)]['tot_sad'].sum()
    for row_index, row in ADM2boundaries.iterrows():
        if(row['ADM1_PCODE'] in ADM1_kuchi):
            tot_kuchi_in_ADM2=0
            for gender_age_group in gender_age_groups:
                # population weighted
                gender_age_group_name='{}_{}'.format(gender_age_group[0],gender_age_group[1])
                kuchi_pp=total_kuchi_in_afg*(row[gender_age_group_name]/pop_in_kuchi_ADM1)            
                ADM2boundaries.loc[row_index,gender_age_group_name]=row[gender_age_group_name]+kuchi_pp
                tot_kuchi_in_ADM2+=kuchi_pp
            ADM2boundaries.loc[row_index,'kuchi']=tot_kuchi_in_ADM2
            ADM2boundaries.loc[row_index,'comment']='Added in total {} Kuchi nomads to WorldPop estimates'.format(tot_kuchi_in_ADM2)

# total from disaggregated
ADM2boundaries['tot_sad']=ADM2boundaries.loc[:,gender_age_group_names].sum(axis=1)
ADM2boundaries['created_at']=str(datetime.datetime.now()) 
ADM2boundaries['created_by']=getpass.getuser()
ADM2boundaries.to_file('{}/{}'.format(dir_path,OUTPUT_SHP))