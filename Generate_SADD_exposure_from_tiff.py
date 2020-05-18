from rasterstats import zonal_stats
import rasterio
import datetime
import getpass
import geopandas as gpd
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

# gender and age groups
for gender_age_group in gender_age_groups:
    gender_age_group_name='{}_{}'.format(gender_age_group[0],gender_age_group[1])
    print('analyising gender age ',gender_age_group_name)
    input_tif_file=INPUT_TIFF_SADD.format(gender_age_group[0],gender_age_group[1])
    zs = zonal_stats('{}/{}'.format(dir_path,INPUT_SHP),'{}/{}'.format(dir_path,input_tif_file),stats='sum')
    total_pop=[district_zs.get('sum') for district_zs in zs]
    ADM2boundaries[gender_age_group_name]=total_pop

# total population for cross check
zs = zonal_stats('{}/{}'.format(dir_path,INPUT_SHP),'{}/{}'.format(dir_path,INPUT_TIFF_POP),stats='sum')
total_pop=[district_zs.get('sum') for district_zs in zs]
ADM2boundaries['tot_pop']=total_pop

# total population UNadj for cross check
zs = zonal_stats('{}/{}'.format(dir_path,INPUT_SHP),'{}/{}'.format(dir_path,INPUT_TIFF_POP_UNadj),stats='sum')
total_pop=[district_zs.get('sum') for district_zs in zs]
ADM2boundaries['tot_pop_UNadj']=total_pop

# total from disaggregated
columns_to_sum=['{}_{}'.format(gender_age_group[0],gender_age_group[1]) for gender_age_group in gender_age_groups]
ADM2boundaries['tot_sad']=ADM2boundaries.loc[:,columns_to_sum].sum(axis=1)

# adding manually Kochi nomads
if country_iso3=='AFG':
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

ADM2boundaries['created_at']=str(datetime.datetime.now()) 
ADM2boundaries['created_by']=getpass.getuser()
ADM2boundaries.to_file('{}/{}'.format(dir_path,OUTPUT_SHP))