import geopandas as gpd
import topojson as tp
import matplotlib.pyplot as plt
import os
import requests
import json

# script that pulls data from the WorldPop API https://www.worldpop.org/sdi/advancedapi and populates the exposure file

# input shapefile downloaded from https://data.humdata.org/dataset/afg-admin-boundaries 
INPUT_SHP = 'Inputs/Shapefiles/afg_admbnda_adm2_agcho_20180522/afg_admbnda_adm2_agcho_20180522.shp'
OUTPUT_SHP = 'Outputs/Exposure_SADD/AFG_SADD.shp'
dir_path = os.path.dirname(os.path.realpath(__file__))

api_url = "https://api.worldpop.org/v1/services/stats"
runasync='false'
year='2020'
# dataset='wpgppop'
dataset='wpgpas'
tolerance=0.01

# some districts don't have sadd data from api

def send_request(url,dataset,year,geojson,runasync):
    try:
        response = requests.get(
            url,
            params={
                "dataset": dataset,
                "year": year,
                "geojson": geojson,
                "runasync": runasync,
            },
        )
        print('Response HTTP Status Code: {status_code}'.format(status_code=response.status_code))
        
        print('{}?dataset={}&year={}&geojson={}&runasync={}'.format(url,dataset,year,geojson,runasync))
        # print('Response HTTP Response Body: {content}'.format(
            # content=response.content))
        
        # if response code=200 but empty use national aggregate

        # add difference between total pop and aggregated
        return response.json().get('data').get('agesexpyramid')
    
    except requests.exceptions.RequestException:
        print('HTTP Request failed')
    except Exception as e:
        print(e)

boundaries=gpd.read_file('{}/{}'.format(dir_path,INPUT_SHP))
boundaries['ageclasses']=''
boundaries=boundaries[boundaries['ADM2_EN']=='Chahab']
# plotting map
fig_map, ax_map = plt.subplots(1, 1)
# using this package to avoid gaps in the simplified geometry
# with GeoSeries.simplify we get gaps
# needs fiona > 1.8.5. Update package using 'conda update fiona'
topo = tp.Topology(boundaries, prequantize=False)
boundaries_simplified=topo.toposimplify(tolerance).to_gdf()
boundaries.boundary.plot(ax=ax_map,color='b')
boundaries_simplified.boundary.plot(ax=ax_map,color='r')
plt.show()

for i, row in boundaries_simplified.iterrows():
    # TODO check why some emptys
    print(row['ADM1_EN'],row['ADM2_EN'],row['Shape_Area'])
    # print(row.geometry)
    ADM2geojson=gpd.GeoSeries([row.geometry]).to_json()
    content = send_request(api_url,dataset,year,ADM2geojson,runasync)
    boundaries.loc[i,'ageclasses']=str(content)
    for ageclass in content:
        print(ageclass)
        boundaries.loc[i,'{}-male'.format(ageclass['age'].replace(' ','-'))]=ageclass['male']
        boundaries.loc[i,'{}-female'.format(ageclass['age'].replace(' ','-'))]=ageclass['female']


    # print(type(content))
    print('\n\n')
    # break
boundaries.to_file('{}/{}'.format(dir_path,OUTPUT_SHP))
