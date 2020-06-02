#!/bin/bash
for iso3 in AFG SSD SDN COD HTI
do
    python Generate_SADD_exposure_from_tiff.py $iso3
    python Generate_vulnerability_file.py $iso3
    python Generate_COVID_file.py -d $iso3
    python Generate_graph.py $iso3
done