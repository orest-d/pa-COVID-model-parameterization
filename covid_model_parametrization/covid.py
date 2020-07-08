# script that pulls data from several sources and generate COVID-19 breakdown for subnational SEIR model

import argparse
import datetime
import pandas as pd
import geopandas as gpd
from pathlib import Path
import os
import logging
import itertools
import getpass

from covid_model_parametrization import utils
from covid_model_parametrization.config import Config


logger = logging.getLogger(__name__)


def covid(country_iso3, download_covid=False, config=None):
    # Get config file
    if config is None:
        config = Config()
    parameters = config.parameters[country_iso3]

    # Get input covid file
    input_dir = os.path.join(config.DIR_PATH, config.INPUT_DIR, country_iso3)

    # Download latest covid file tiles and read them in
    if download_covid:
        get_covid_data(parameters["covid"], country_iso3, input_dir, config)
    df_covid = pd.read_csv(
        "{}/{}".format(
            os.path.join(input_dir, config.COVID_OUTPUT_DIR),
            parameters["covid"]["filename"],
        ),
        header=parameters["covid"]["header"],
        skiprows=parameters["covid"]["skiprows"],
    )
    # convert to standard HLX
    if "hlx_dict" in parameters["covid"]:
        df_covid = df_covid.rename(columns=parameters["covid"]["hlx_dict"])
    if (
        parameters["covid"]["individual_case_data"]
        and parameters["covid"]["admin_level"] == 2
    ):
        df_covid = pd.pivot_table(
            df_covid,
            index=[
                config.HLX_TAG_DATE,
                config.HLX_TAG_ADM1_NAME,
                config.HLX_TAG_ADM2_NAME,
            ],
            aggfunc="count",
        ).reset_index()
        df_covid = df_covid.rename(columns={"Case No.": config.HLX_TAG_TOTAL_CASES})
        df_covid = df_covid[
            [
                config.HLX_TAG_DATE,
                config.HLX_TAG_ADM1_NAME,
                config.HLX_TAG_ADM2_NAME,
                config.HLX_TAG_TOTAL_CASES,
            ]
        ]

    # in some files we have province explicitely
    df_covid = df_covid[df_covid[config.HLX_TAG_ADM1_NAME] != "Total"]
    df_covid[config.HLX_TAG_ADM1_NAME] = df_covid[config.HLX_TAG_ADM1_NAME].str.replace(
        "Province", ""
    )
    df_covid[config.HLX_TAG_ADM1_NAME] = df_covid[config.HLX_TAG_ADM1_NAME].str.replace(
        "State", ""
    )
    df_covid[config.HLX_TAG_ADM1_NAME] = df_covid[config.HLX_TAG_ADM1_NAME].str.strip()
    if (
        "replace_dict" in parameters["covid"]
        and parameters["covid"]["admin_level"] == 1
    ):
        df_covid[config.HLX_TAG_ADM1_NAME] = df_covid[config.HLX_TAG_ADM1_NAME].replace(
            parameters["covid"]["replace_dict"]
        )
    if (
        "replace_dict" in parameters["covid"]
        and parameters["covid"]["admin_level"] == 2
    ):
        df_covid[config.HLX_TAG_ADM2_NAME] = df_covid[config.HLX_TAG_ADM2_NAME].replace(
            parameters["covid"]["replace_dict"]
        )

    # convert to numeric
    if parameters["covid"]["cases"]:
        df_covid[config.HLX_TAG_TOTAL_CASES] = convert_to_numeric(
            df_covid[config.HLX_TAG_TOTAL_CASES]
        )
    if parameters["covid"]["deaths"]:
        df_covid[config.HLX_TAG_TOTAL_DEATHS] = convert_to_numeric(
            df_covid[config.HLX_TAG_TOTAL_DEATHS]
        )
    df_covid.fillna(0, inplace=True)

    # Get exposure file
    try:
        exposure_file = f"{config.SADD_output_dir().format(country_iso3)}/{config.EXPOSURE_GEOJSON.format(country_iso3)}"
        exposure_gdf = gpd.read_file(exposure_file)
    except:
        logger.error(
            f"Cannot get exposure file for {country_iso3}, COVID file not generate"
        )

    output_fields = [
        config.HLX_TAG_ADM1_PCODE,
        config.HLX_TAG_ADM2_PCODE,
        config.HLX_TAG_DATE,
        config.HLX_TAG_TOTAL_CASES,
        config.HLX_TAG_TOTAL_DEATHS,
    ]
    output_df_covid = pd.DataFrame(columns=output_fields)

    ADM2_ADM1_pcodes = get_dict_pcodes(exposure_gdf, "ADM2_PCODE")

    if parameters["covid"]["admin_level"] == 2:
        ADM2_names = get_dict_pcodes(
            exposure_gdf, parameters["covid"]["adm2_name_exp"], "ADM2_PCODE"
        )
        df_covid[config.HLX_TAG_ADM2_PCODE] = df_covid[config.HLX_TAG_ADM2_NAME].map(
            ADM2_names
        )
        if df_covid[config.HLX_TAG_ADM2_PCODE].isnull().sum() > 0:
            logger.warning(
                "missing PCODE for the following admin units ",
                df_covid[df_covid[config.HLX_TAG_ADM2_PCODE].isnull()],
            )
            # print(df_covid)
            return
        df_covid[config.HLX_TAG_ADM1_PCODE] = df_covid[config.HLX_TAG_ADM2_PCODE].map(
            ADM2_ADM1_pcodes
        )
        adm1pcode = df_covid[config.HLX_TAG_ADM1_PCODE]
        adm2pcodes = df_covid[config.HLX_TAG_ADM2_PCODE]
        date = pd.to_datetime(
            df_covid[config.HLX_TAG_DATE], format=parameters["covid"]["date_format"]
        )
        date = date.dt.strftime("%Y-%m-%d")
        adm2cases = (
            df_covid[config.HLX_TAG_TOTAL_CASES]
            if parameters["covid"]["cases"]
            else None
        )
        adm2deaths = (
            df_covid[config.HLX_TAG_TOTAL_DEATHS]
            if parameters["covid"]["deaths"]
            else None
        )
        raw_data = {
            config.HLX_TAG_ADM1_PCODE: adm1pcode,
            config.HLX_TAG_ADM2_PCODE: adm2pcodes,
            config.HLX_TAG_DATE: date,
            config.HLX_TAG_TOTAL_CASES: adm2cases,
            config.HLX_TAG_TOTAL_DEATHS: adm2deaths,
        }
        output_df_covid = output_df_covid.append(
            pd.DataFrame(raw_data), ignore_index=True
        )
    elif parameters["covid"]["admin_level"] == 1:
        if parameters["covid"].get("federal_state_dict", False):
            # for Somalia we replace the ADM1_PCODE the name of the ADM1 and with the name of the state
            # this is done according to the dictionary
            exposure_gdf["ADM1_PCODE"] = exposure_gdf[
                parameters["covid"]["adm1_name_exp"]
            ].replace(parameters["covid"]["federal_state_dict"])
            exposure_gdf[parameters["covid"]["adm1_name_exp"]] = exposure_gdf[
                "ADM1_PCODE"
            ]
        ADM1_names = get_dict_pcodes(
            exposure_gdf, parameters["covid"]["adm1_name_exp"], "ADM1_PCODE"
        )
        df_covid[config.HLX_TAG_ADM1_PCODE] = df_covid[config.HLX_TAG_ADM1_NAME].map(
            ADM1_names
        )
        if df_covid[config.HLX_TAG_ADM1_PCODE].isnull().sum() > 0:
            logger.warning("missing PCODE for the following admin units :")
            logger.warning(
                df_covid[df_covid[config.HLX_TAG_ADM1_PCODE].isnull()][
                    [config.HLX_TAG_ADM1_NAME, config.HLX_TAG_DATE]
                ]
            )
        # recalculate total for each ADM1 unit
        gender_age_groups = list(
            itertools.product(config.GENDER_CLASSES, config.AGE_CLASSES)
        )
        gender_age_group_names = [
            "{}_{}".format(gender_age_group[0], gender_age_group[1])
            for gender_age_group in gender_age_groups
        ]

        for _, row in df_covid.iterrows():
            adm2_pop_fractions = get_adm2_to_adm1_pop_frac(
                row[config.HLX_TAG_ADM1_PCODE], exposure_gdf, gender_age_group_names
            )
            adm1pcode = row[config.HLX_TAG_ADM1_PCODE]
            date = datetime.datetime.strptime(
                row[config.HLX_TAG_DATE], parameters["covid"]["date_format"]
            ).strftime("%Y-%m-%d")
            adm2cases = scale_adm1_by_adm2_pop(
                parameters["covid"]["cases"],
                config.HLX_TAG_TOTAL_CASES,
                row,
                adm2_pop_fractions,
            )
            adm2deaths = scale_adm1_by_adm2_pop(
                parameters["covid"]["deaths"],
                config.HLX_TAG_TOTAL_DEATHS,
                row,
                adm2_pop_fractions,
            )

            adm2pcodes = [v for v in adm2_pop_fractions.keys()]
            raw_data = {
                config.HLX_TAG_ADM1_PCODE: adm1pcode,
                config.HLX_TAG_ADM2_PCODE: adm2pcodes,
                config.HLX_TAG_DATE: date,
                config.HLX_TAG_TOTAL_CASES: adm2cases,
                config.HLX_TAG_TOTAL_DEATHS: adm2deaths,
            }
            output_df_covid = output_df_covid.append(
                pd.DataFrame(raw_data), ignore_index=True
            )
    else:
        logger.error(f"Missing admin_level info for COVID data")
    # cross-check: the total must match
    if (
        abs(
            (
                output_df_covid[config.HLX_TAG_TOTAL_CASES].sum()
                - df_covid[config.HLX_TAG_TOTAL_CASES].sum()
            )
        )
        > 10
    ):
        logger.warning("The sum of input and output files don't match")

    if not parameters["covid"]["cumulative"]:
        logger.info(f"Calculating cumulative numbers COVID data")
        groups = [
            config.HLX_TAG_ADM1_PCODE,
            config.HLX_TAG_ADM2_PCODE,
            config.HLX_TAG_DATE,
        ]
        # get sum by day (in case multiple reports per day)
        output_df_covid = (
            output_df_covid.groupby(groups).sum().sort_values(by=config.HLX_TAG_DATE)
        )
        # get cumsum by day (grouped by ADM2)
        output_df_covid = (
            output_df_covid.groupby(config.HLX_TAG_ADM2_PCODE).cumsum().reset_index()
        )

    if parameters["covid"].get("federal_state_dict", False):
        # bring back the adm1 pcode that we modified to calculate the sum
        output_df_covid[config.HLX_TAG_ADM1_PCODE] = output_df_covid[
            config.HLX_TAG_ADM2_PCODE
        ].map(ADM2_ADM1_pcodes)

    # Write to file
    output_df_covid["created_at"] = str(datetime.datetime.now())
    output_df_covid["created_by"] = getpass.getuser()
    output_csv = get_output_filename(country_iso3, config)
    logger.info(f"Writing to file {output_csv}")
    output_df_covid.to_csv(output_csv, index=False)


def get_dict_pcodes(exposure, adm_unit_name, adm_unit_pcode="ADM1_PCODE"):
    pcode_dict = dict()
    for k, v in exposure.groupby(adm_unit_name):
        pcode_dict[k] = v.iloc[0, :][adm_unit_pcode]
    return pcode_dict


def scale_adm1_by_adm2_pop(parameters_val, tag, df_row, fractions):
    if parameters_val:
        adm1val = df_row[tag]
        adm2val = [v * adm1val for v in fractions.values()]
    else:
        adm2val = None
    return adm2val


def convert_to_numeric(df_col):
    # TODO check conversions
    if df_col.dtype == "object":
        df_col = df_col.str.replace(",", "")
        df_col = df_col.str.replace("-", "")
        df_col = pd.to_numeric(df_col, errors="coerce")
    return df_col


def get_output_filename(country_iso3, config):
    # get the filename for writing the file
    output_dir = config.COVID_output_dir().format(country_iso3)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    return os.path.join(output_dir, config.COVID_OUTPUT_CSV.format(country_iso3))


def get_adm2_to_adm1_pop_frac(pcode, exposure_gdf, gender_age_group_names):
    # get the full exposure and returns a dictionary with
    # the fraction of the population of each ADM2
    exp_adm1 = exposure_gdf[exposure_gdf["ADM1_PCODE"] == pcode]
    adm2_pop = exp_adm1[gender_age_group_names].sum(axis=1)
    adm2_pop_fractions = dict(zip(exp_adm1["ADM2_PCODE"], adm2_pop / adm2_pop.sum()))
    return adm2_pop_fractions


def get_covid_data(parameters, country_iso3, input_dir, config):
    # download covid data from HDX
    logger.info(f"Getting COVID data for {country_iso3}")
    download_dir = os.path.join(input_dir, config.COVID_OUTPUT_DIR)
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    covid_filename = os.path.join(download_dir, parameters["filename"])
    try:
        utils.download_url(parameters["url"], covid_filename)
    except Exception:
        logger.warning(f"Cannot download COVID file from for {country_iso3}")
