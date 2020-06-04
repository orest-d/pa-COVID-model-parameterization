#!/bin/bash
for iso3 in AFG SSD SDN COD HTI
do
    python Generate_SADD_exposure_from_tiff.py $iso3
    python Generate_vulnerability_file.py $iso3
    python Generate_COVID_file.py -d $iso3
    python Generate_graph.py -m https://raw.githubusercontent.com/OCHA-DAP/pa-movement-patterns-matrix/master/output/${iso3,,}/${iso3,,}_mobility_matrix.csv iso3
done
