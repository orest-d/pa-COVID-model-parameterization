#!/bin/bash
for iso3 in AFG SSD SDN COD SOM
do
    python Generate_SADD_exposure_from_tiff.py $iso3
    python Generate_vulnerability_file.py $iso3
    python Generate_COVID_file.py -d $iso3
    # python Generate_graph.py -m https://raw.githubusercontent.com/OCHA-DAP/pa-movement-patterns-matrix/master/output/${iso3,,}/${iso3,,}_mobility_matrix.csv $iso3
done
python Generate_graph.py -m https://raw.githubusercontent.com/OCHA-DAP/pa-movement-patterns-matrix/master/output/afg/afg_mobility_matrix.csv AFG
python Generate_graph.py -m https://raw.githubusercontent.com/OCHA-DAP/pa-movement-patterns-matrix/master/output/ssd/ssd_mobility_matrix.csv SSD
python Generate_graph.py -m https://raw.githubusercontent.com/OCHA-DAP/pa-movement-patterns-matrix/master/output/sdn/sdn_mobility_matrix.csv SDN
python Generate_graph.py -m https://raw.githubusercontent.com/OCHA-DAP/pa-movement-patterns-matrix/master/output/cod/cod_mobility_matrix.csv COD
python Generate_graph.py -m https://raw.githubusercontent.com/OCHA-DAP/pa-movement-patterns-matrix/master/output/hti/hti_mobility_matrix.csv HTI
