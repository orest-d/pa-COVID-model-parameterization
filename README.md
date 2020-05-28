# COVID model parameterization

[Input description (Google slides)](https://docs.google.com/presentation/d/16hplfTHyJtXoAXTLgNp3LHWP2Upig0eofGcufOsv3RY/edit?usp=sharing)

[Status tracking sheet (Google sheets)](https://docs.google.com/spreadsheets/d/1F-15iyDf_v7hBtr-jdCQMptt5bSFY52YivYRyLFVFBQ/edit?usp=sharing)

[Latest input file (zip)](https://drive.google.com/file/d/1gK3opqhwCc4BRu5PvnYagi0sSI6qnyxn/view)


## Exposure

### Setup

Download the country boundaries shapefile from HDX and place in `Inputs/$COUNTRY_ISO3/Shapefile/`. Unzip the contents
into a directory with the same name as the shapefile, and add this name to the config file.  
Commit the shapefile to the repository.

### Running
To run, execute:
```bash
python Generate_SADD_exposure_from_tiff.py -d
```
The `-d ` flag is for downloading the WolrdPop file the first time you run.  

## Vulnerability

### Setup

Make sure you have run the exposure script for the country. 

Check [GHS](https://ghsl.jrc.ec.europa.eu/download.php) for the grid square numbers that cover the country
and add these to the config file. 

Download food security data from [IPC](http://www.ipcinfo.org/ipc-country-analysis/population-tracking-tool/en/).
Select the country and only data from 2020, save the excel file to 'Inputs/$COUNTRY_ISO3/IPC'. 
Add the filename to the config file, and commit the excel file to the repository. 

Add [solid fuels](https://apps.who.int/gho/data/node.main.135?lang=en), 
[raised blood pressure](https://www.who.int/nmh/countries), and
[diabetes](https://www.who.int/nmh/countries) data to the config file, if available. 
 
## Running 

To run, execute:
```bash
python Generate_vulnerability_file.py -d
```
The `-d ` flag is for downloading and mosaicing the GHS data the first time you run.

### Methodology

Urban / rural data is taken from [GHS](https://ghsl.jrc.ec.europa.eu/). We use the GHS-SMOD raster at 1 km resolution
to determine which cells within a province are urban vs rural. The description of the 
classifcations can be found [here](https://ghsl.jrc.ec.europa.eu/documents/GHSL_Data_Package_2019.pdf).
We take anything denser than suburban (class 21 or above) to be urban, and the rest to be rural.
For more information about the definition of urban vs rural settlements, see 
[here](https://ghsl.jrc.ec.europa.eu/degurbaDefinitions.php).

Then we use the GHS-POP raster to calculate the number of people per urban or rural cell,
and compute the fraction of the population residing in urban cells. 

## Contact matrices

Contact matrices are extracted from [this paper on PLOS Computational Biology](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005697#sec020).
The contact matrices used are taken from the _all\_locations_ dataset which is available in two different files: _MUestimates\_all\_locations\_1.xlsx_ (containing data for Algeria to Morocco) and _MUestimates\_all\_locations\_2.xlsx_ (containing data for Mozambique to Zimbabwe).

### Methodology

#### Selection of contact matrices

For some of the countries the contact matrix is not directly available and we are usign a country in the same region and with similat socioeconomic indicators as proxy, as also done by [LSHTM](https://www.dropbox.com/sh/m3n6qjesd7v3rd0/AAC0OblfX-8sVyIuGCsqSZjMa?dl=0). Specifically:
| Country     | Contact Matrix used |
|-------------|---------------------|
| Afghanistan | Pakistan            |
| Sudan       | Ethiopia            |
| South Sudan | Uganda              |
| DRC         | Zambia              |
| Haiti       | available on PLOS   |

#### Correspondence of age classes

The contact matrices are categorised into 5-year age intervals {1,2,...,16} which don't correspond exactly to the age classes in WorldPop. Classes are matched in the following way:
| WorlpPop Class   | Contact Matrix class |
|------------------|----------------------|
| class 0 (0 to 1) | class X1 (0 to 4)       |
| class 1 (1 to 4) | class X1 (0 to 4)       |
| class 5 (5 to 9) | class X2 (5 to 9)       |
| class 10 (10 to 14) | class X3 (10 to 14)       |
| class 15 (15 to 19) | class X4 (15 to 19)       |
| class 20 (20 to 24) | class X5 (20 to 24)       |
| class 25 (25 to 29) | class X6 (25 to 29)       |
| class 30 (30 to 34) | class X7 (30 to 34)       |
| class 35 (35 to 39) | class X8 (35 to 39)       |
| class 40 (40 to 44) | class X9 (40 to 44)       |
| class 45 (45 to 49) | class X10 (45 to 49)       |
| class 50 (50 to 54) | class X11 (50 to 54)       |
| class 55 (55 to 59) | class X12 (55 to 59)       |
| class 60 (60 to 64) | class X13 (60 to 64)       |
| class 65 (65 to 69) | class X14 (65 to 69)       |
| class 70 (70 to 74) | class X15 (70 to 74)       |
| class 75 (70 to 79) | class X16 (75+)       |
| class 80 (80+) | class X16 (75+)       |
