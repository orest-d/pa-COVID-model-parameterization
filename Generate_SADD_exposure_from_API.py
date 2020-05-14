import geopandas as gpd
import time
import topojson as tp
import matplotlib.pyplot as plt
import os
import requests
import json
import datetime
import getpass

# dismissed as the API has several bugs and limitations:
# MultiPolygons are not accepted
# no long URL accepted
# some populated areas return no data
# limited number of requests to the sever (1000/day)

# script that pulls data from the WorldPop API https://www.worldpop.org/sdi/advancedapi and populates the exposure file
country_iso3='AFG'

# input shapefile downloaded from https://data.humdata.org/dataset/afg-admin-ADM2boundaries 
if country_iso3=='AFG':
    INPUT_SHP = 'Inputs/Shapefiles/afg_admbnda_adm2_agcho_20180522/afg_admbnda_adm2_agcho_20180522.shp'

OUTPUT_SHP = 'Outputs/Exposure_SADD/{}_Exposure.shp'.format(country_iso3)
dir_path = os.path.dirname(os.path.realpath(__file__))

wp_api_url = "https://api.worldpop.org/v1/services/stats"
wp_api_url_async = "https://api.worldpop.org/v1/tasks"
runasync='false'
year='2020'
dataset_pop='wpgppop'
dataset_sadd='wpgpas'
tolerance=0.02

def send_request(dataset,year,geojson,runasync):
    # send request to the WorldPop API based on parameters
    # retuns 'data' dictionary or error message if data not available
    # TODO API doesn't work for multipolygons. Add functionality to split in several calls
    maxntries=5
    tries = 0
    success = False
    while not success:
        tries+=1
        try:
            response = requests.get(
                wp_api_url,
                params={
                    "dataset": dataset,
                    "year": year,
                    "geojson": geojson,
                    "runasync": runasync,
                },
            )
            # print('  {}?dataset={}&year={}&geojson={}&runasync={}'.format(wp_api_url,dataset,year,geojson,runasync))
            
            # if the response is taking too long the API automatically switches to async.
            # See documentation https://www.worldpop.org/sdi/advancedapi
            # We wait and query the api_url_async endpoint
            while response.json().get('status')!='finished':
                print('  switching to async mode')
                time.sleep(10)
                response = requests.get('{}/{}'.format(wp_api_url_async,response.json().get('taskid')))
            data=str(response.json().get('data'))
            print('  data: ',data)
            # we have data, setting success to true
            success=True
            return data
        except ConnectionError:   
            # sometimes the connection get reset by the server, need to make a new request
            if(tries==maxntries):
                success=True
                return '{} data not available. No reponse from sever'.format(dataset)
        except Exception:
            # we have a response from the server
            status_code=response.status_code
            success=True
            return '{} data not available. response code {}'.format(dataset,status_code)

def unpack_wpgpas_ADM2data(idx,df):
    # reads the dataset_sadd column and splits it to age/gender columns
    # returns false is data not available
    try:
        totalpop_sadd=0
        jsonstringADM2=df.loc[idx,'{}'.format(dataset_sadd)].replace("'", "\"")
        jsondataADM2=json.loads(jsonstringADM2)
        for ageclass in jsondataADM2.get('agesexpyramid'):
            df.loc[idx,'M_{}'.format(ageclass['class'])]=ageclass['male']
            df.loc[idx,'F_{}'.format(ageclass['class'])]=ageclass['female']
            totalpop_sadd+=ageclass['male']
            totalpop_sadd+=ageclass['female']
        df.loc[idx,'totalwpgpas']=totalpop_sadd
        return True
    except Exception:
        return False

def unpack_wpgppop_ADM2data(idx,df):
    # reads the dataset_pop column and splits create new column with total
    # returns false is data not available
    try:
        jsonstringADM2=df.loc[idx,'{}'.format(dataset_pop)].replace("'", "\"")
        jsondataADM2=json.loads(jsonstringADM2)
        df.loc[idx,'totalwpgppop']=jsondataADM2.get('total_population')
        return True
    except Exception:
        return False

def unpack_wpgpas_ADM1data(idx,df):
    # reads the ADM1_dataset_sadd, total_dataset_pop columns and splits them to age/gender columns
    # the value are calculated as the fraction at the ADM1 level of each age/gender group, scaled by the total population of the ADM2 unit
    # returns false is data not available
    try:
        totalpop_saddADM1=0
        jsonstringADM1=df.loc[idx,'ADM1_{}'.format(dataset_sadd)].replace("'", "\"")
        jsondataADM1=json.loads(jsonstringADM1)
        total_popADM2=df.loc[idx,'total_{}'.format(dataset_pop)]
        # print(total)
        for ageclassADM1 in jsondataADM1.get('agesexpyramid'):
            totalpop_saddADM1+=ageclassADM1['male']
            totalpop_saddADM1+=ageclassADM1['female']
        for ageclassADM1 in jsondataADM1.get('agesexpyramid'):
            df.loc[idx,'M_{}'.format(ageclassADM1['class'])]=ageclassADM1['male']/totalpop_saddADM1*total_popADM2
            df.loc[idx,'F_{}'.format(ageclassADM1['class'])]=ageclassADM1['female']/totalpop_saddADM1*total_popADM2
        df.loc[idx,'comments']='Data extracted from ADM1 average'
    except Exception:
        return False

def simplify_geodataframe(tolerance,gdf,plot_simplified=False):
    # using this package to avoid gaps in the simplified geometry
    # with GeoSeries.simplify we get gaps
    # needs fiona > 1.8.5. Update package using 'conda update fiona'
    topo = tp.Topology(gdf, prequantize=False)
    gdf_simplified=topo.toposimplify(tolerance).to_gdf()
    if(plot_simplified):
        _, ax_map = plt.subplots(1, 1)
        gdf.boundary.plot(ax=ax_map,color='b')
        gdf_simplified.boundary.plot(ax=ax_map,color='r')  
        plt.show()
    return gdf_simplified


def get_ADM1_geojson(ADM1pcode,gdf):
    # get the ADM1 level and return the geojson by dissolving the ADM2 geodataframe

    ADM1gdf=gdf[gdf['ADM1_PCODE']==ADM1pcode]
    # group by admin 1
    ADM1gdf_dissolved=ADM1gdf.dissolve(by='ADM1_EN')
    # get topology and simplify ADM1
    ADM1df_dissolved_simplified=simplify_geodataframe(tolerance,ADM1gdf_dissolved)
    # get the geometry
    ADM1geojson=gpd.GeoSeries([ADM1df_dissolved_simplified.loc[0].geometry]).to_json()
    return ADM1geojson
    
ADM2boundaries=gpd.read_file('{}/{}'.format(dir_path,INPUT_SHP))
ADM2boundaries_simplified=simplify_geodataframe(tolerance,ADM2boundaries)
ADM2boundaries['totalwpgpas']=''
ADM2boundaries['totalwpgppop']=''

# ADM2boundaries=ADM2boundaries[ADM2boundaries['ADM2_PCODE'].isin(['AF2702'])]
# print(ADM2boundaries)

for row_index, row in ADM2boundaries.iterrows():
    irow=1
    print('{} out of {} done'.format(irow,len(ADM2boundaries)))
    irow+=1
    ADM2name=row['ADM2_EN']
    ADM2pcode=row['ADM2_PCODE']
    
    # if(ADM2pcode!='AF1816'):
        # continue
    print('ADMIN2 name : {} (pcode {})'.format(ADM2name,ADM2pcode))
    # get corresponding simplified geometry using ADM2_EN as key
    ADM2geometry_simplified=ADM2boundaries_simplified[ADM2boundaries_simplified['ADM2_PCODE']==ADM2pcode].geometry
    ADM2geojson=gpd.GeoSeries(ADM2geometry_simplified).to_json()
    
    print('  sending request for ADM2 {} data'.format(dataset_sadd))
    ADM2boundaries.loc[row_index,dataset_sadd]=send_request(dataset_sadd,year,ADM2geojson,runasync)
    print('  sending request for ADM2 {} data'.format(dataset_pop))
    ADM2boundaries.loc[row_index,dataset_pop]=send_request(dataset_pop,year,ADM2geojson,runasync)
    unpack_wpgppop_ADM2data(row_index,ADM2boundaries)
    
    if not unpack_wpgpas_ADM2data(row_index,ADM2boundaries):
        ADM1name=row['ADM1_EN']
        ADM1pcode=row['ADM1_PCODE']
        print('    ADM2 data not available, moving to ADM1 {} (pcode {})'.format(ADM1name,ADM1pcode))
        ADM1geojson=get_ADM1_geojson(ADM1pcode,ADM2boundaries)
        print('    sending request for ADM1 {} data'.format(dataset_sadd))
        ADM2boundaries.loc[row_index,'ADM1_{}'.format(dataset_sadd)]=send_request(dataset_sadd,year,ADM1geojson,runasync)    
        unpack_wpgpas_ADM1data(row_index,ADM2boundaries)
    print('\n\n')

# TODO adding undocumented nomads for Afghanistan
# TODO update README
# TODO Google Slides with tech description
# TODO Google Sheet to track  status
# TODO Google folder with latest outputs
# TODO requirements
ADM2boundaries['created_at']=str(datetime.datetime.now()) 
ADM2boundaries['created_by']=getpass.getuser()
# print(ADM2boundaries.columns)
ADM2boundaries.to_file('{}/{}'.format(dir_path,OUTPUT_SHP))
