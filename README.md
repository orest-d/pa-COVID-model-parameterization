# COVID model parameterization

## Urban Rural disagregation

### Methodology

Data is taken from [GHS](https://ghsl.jrc.ec.europa.eu/). We use the GHS-SMOD raster at 1 km resolution
to determine which cells within a province are urban vs rural. The description of the 
classifcations can be found [here](https://ghsl.jrc.ec.europa.eu/documents/GHSL_Data_Package_2019.pdf).
We take anything denser than suburban (class 21 or above) to be urban, and the rest to be rural.

Then we use the GHS-POP raster to calculate the number of people per urban or rural cell,
and compute the fraction of the population residing in urban cells. 

## Running 

To run, execute:
```bash
python Generate_vulnerability_file.py -g
```
The `-g ` flag is for downloading and mosaicing the GHS data the first time you run.
