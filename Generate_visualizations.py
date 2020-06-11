import argparse
import os
import logging
from pathlib import Path

import geopandas as gpd
import geoplot as gplt
import matplotlib.pyplot as plt
import matplotlib as mpl
import mapclassify as mc
import numpy as np
import pandas as pd

import utils

MAIN_DIR = 'Outputs'
OUTPUT_DIR = 'Figures'

EXPOSURE_DIR = 'Exposure_SADD'
EXPOSURE_FILENAME = '{country_iso3}_Exposure.geojson'

VULNERABILITY_DIR = 'Vulnerability'
VULNERABILITY_FILENAME = '{country_iso3}_Vulnerabilities.geojson'

COVID_DIR = 'COVID'
COVID_FILENAME = '{country_iso3}_COVID.csv'

utils.config_logger()
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('country_iso3', help='Country ISO3')
    return parser.parse_args()


def main(country_iso3):
    main_dir = os.path.join(MAIN_DIR, country_iso3)
    outdir = os.path.join(main_dir, OUTPUT_DIR)
    Path(outdir).mkdir(parents=True, exist_ok=True)
    # Map vulnerabilities
    vulnerability = map_vulnerabilities(main_dir, country_iso3, outdir)
    # Map for COVID cases
    map_covid_cases(main_dir, country_iso3, vulnerability, outdir)
    # Map of population
    map_population(main_dir, country_iso3, outdir)
    # Map of mobility matrix


def map_vulnerabilities(main_dir, country_iso3, outdir):
    filename_vulnerability = os.path.join(main_dir, VULNERABILITY_DIR,
                                          VULNERABILITY_FILENAME.format(country_iso3=country_iso3))
    vulnerability = gpd.read_file(filename_vulnerability)
    # Map for food security
    vulnerability['Phase 3+'] = vulnerability['Phase 3+'].astype(float)
    plot_choropleth(vulnerability,
                    'Phase 3+',
                    'Food insecure population fraction',
                    'Greens',
                    outdir,
                    country_iso3,
                    'food_insecurity',
                    norm=(0, 1))
    # Map for houshold air pollution
    plot_choropleth(vulnerability,
                    'fossil_fuels',
                    'Population fraction using indoor cooking fuels',
                    'Reds',
                    outdir,
                    country_iso3,
                    'indoor_fuels',
                    norm=(0, 1))
    return vulnerability


def map_covid_cases(main_dir, country_iso3, gdf, outdir):
    # TODO: a lot of this is copied from the graph script, refactor
    # Read in COVID file
    filename = os.path.join(main_dir, COVID_DIR, COVID_FILENAME.format(country_iso3=country_iso3))
    logger.info(f'Reading in COVID cases from {filename}')
    covid = pd.read_csv(filename)
    date_range = pd.date_range(covid['#date'].min(), covid['#date'].max())
    for cname, plot_title, cmap in zip(['confirmed', 'dead'], ['confirmed cases', 'deaths'], ['Blues', 'Greys']):
        # Do some pivoting
        covid_out = covid.pivot(index='#date',
                                values=f'#affected+infected+{cname}+total',
                                columns='#adm2+pcode')
        # Add any missing dates
        covid_out.index = pd.DatetimeIndex(covid_out.index)
        covid_out = covid_out.reindex(date_range)
        # Interpolate the missing values
        covid_out = covid_out.interpolate(method='linear', axis='rows', limit_direction='forward').fillna(0)
        # Take only the last row (latest date), and take transpose
        covid_out = covid_out.iloc[[-1]].T
        covid_out.columns = ['covid']
        # Join with geodataframe to make map
        map = gdf.merge(covid_out, left_on='ADM2_PCODE', right_on='#adm2+pcode', how='left').fillna(0)
        plot_choropleth(map,
                        'covid',
                        f'COVID-19 {plot_title}',
                        cmap,
                        outdir,
                        country_iso3,
                        f'covid_{cname}',
                        use_scheme=True)


def map_population(main_dir, country_iso3, outdir):
    logger.info('Mapping population')
    filename = os.path.join(main_dir, EXPOSURE_DIR, EXPOSURE_FILENAME.format(country_iso3=country_iso3))
    logger.info(f'Reading in exposure from {filename}')
    exposure = gpd.read_file(filename)
    # Add pop -- recalculate for now until exposure script updated
    exposure['population'] = exposure[[c for c in exposure.columns if 'f_' in c or 'm_' in c]].sum(axis=1)
    plot_choropleth(exposure,
                    'population',
                    'Population',
                    'Purples',
                    outdir,
                    country_iso3,
                    'population',
                    use_scheme=True)


def plot_choropleth(gdf, parameter, title, cmap, outdir, country_iso3, filename, norm=None, use_scheme=False):
    fig, ax = plt.subplots()
    if use_scheme:
        try:
            scheme = mc.FisherJenks(gdf[parameter], k=5)
        except ValueError:
            logger.warning(f'Not enough values to plot {filename}')
            return 0
        # Make nice legend labels
        if gdf[parameter].max() < 10:
            format_bin = lambda bin: f'{np.round(bin, 1)}'
        else:
            precision = len(str(int(scheme.bins[0]))) - 2
            format_bin = lambda bin: f'{int(np.round(bin, -precision)):,}'
        legend_labels = [f'< {format_bin(scheme.bins[0])}'] + \
                        [f'{format_bin(scheme.bins[i] + 1)}–{format_bin(scheme.bins[i + 1])}'
                         for i in range(len(scheme.bins) - 2)] + \
                        [f'> {format_bin(scheme.bins[-2])}']
        legend_kwargs = ({'title': title})
    else:
        scheme = None
        legend_labels = None
        legend_kwargs = ({'orientation': 'horizontal', 'label': title, 'shrink': 0.5})
    if norm is not None:
        norm = mpl.colors.Normalize(vmin=norm[0], vmax=norm[1])
    gplt.choropleth(gdf,
                    ax=ax,
                    legend=True,
                    lw=0.5,
                    hue=parameter,
                    cmap=cmap,
                    legend_kwargs=legend_kwargs,
                    scheme=scheme,
                    legend_labels=legend_labels,
                    norm=norm)
    fig.savefig(os.path.join(outdir, f'{country_iso3}_{filename}.png'), dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    args = parse_args()
    main(args.country_iso3.upper())
