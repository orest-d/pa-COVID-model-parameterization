#!/bin/bash
for i in 0 1 5 10 15 20 25 30 35 40 45 50 55 60 65 70 75 80
do
   wget ftp://ftp.worldpop.org.uk/GIS/AgeSex_structures/Global_2000_2020/2020/AFG/afg_f_$i\_2020.tif
   wget ftp://ftp.worldpop.org.uk/GIS/AgeSex_structures/Global_2000_2020/2020/AFG/afg_m_$i\_2020.tif
done
wget ftp://ftp.worldpop.org.uk/GIS/Population/Global_2000_2020/2020/AFG/afg_ppp_2020.tif