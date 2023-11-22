# Grid Square Environmental Data Generage Program

[日本語](./README-ja.md) | English

The Grid Square Environmental Data Generage Program is a program that generates binary files containing tile images and attributes of geographical features, cut to match the boundaries of each Grid Square geographical feature, using specified Grid Square data. This document describes the specifications and usage instructions for this program.

## Operating Environment

- Python 3.8 and the following libraries
    - pandas v1.4.1
    - shapely v1.8.1.post1
    - tiletanic v1.1.0
    - pyproj v3.3.0
    - Pillow v8.0.0
- GDAL v3.4.0

## Environment setup

Using `Docker`, build an image as follows:

```sh
cd meshwriter
docker build . -t meshscript
```

## Creating a Rock Type Dictionary File

- `prepare.py` is a script that creates a dictionary for converting pixel values of geological PNGs.
- If there are any changes in `長野県岩相区分.xlsx`, execute the script with the following command and place the generated `geology_hex.json` file in the root directory of the grid square data obtained by running this program.

```shell
cd src/meshwriter
docker run --rm -v $PWD:/usr/src/app meshscript python3 prepare.py
#./meshwriter/geology_hex.json will be generated
```


## Placement of Input Files

Deploy `mesh.gpkg` and `Weather Information CSV folder (in the example below, it's referred to as "output")` in the `./meshwriter` directory.

```
./meshwriter
├── Dockerfile
├── README.md
├── README-ja.md
├── __init__.py
├── __main__.py
├── mesh.gpkg
├── output
│   ├── 523764
│   │   ├── 52376436.csv
│   │   ├── 52376437.csv
│   │   ...// 中略
│   │   └── 52376499.csv
│   ├── 523765
│   │   ├── 52376540.csv
│   │   ├── 52376541.csv
// rest is omitted.
```


## How to run it:

```sh
cd meshwriter
docker run --rm -v $PWD:/usr/src/app meshscript python3 __main__.py
```

As you start the process as described above, Grid Square data will be generated in `./meshwriter/meshdata`.

### ### Configuration Items

As mentioned above, you can generate Grid Square data by placing the required files, but there are several configuration options that can be modified. The settings are defined by the following variables at the beginning of the `__main__.py` file.

```python
# Starting from line 15 in `__main__.py`
############ Configuration Items ############
OVERWRITE = False
INPUT_GPKG = "mesh.gpkg"
OUTPUT_DIR = "meshdata"
MESH_CLIMATE_CSV_DIR = "output"
###############################
```

#### OVERWRITE

- The default is `False`. In this case, if the Grid Square generation is already completed, it will skip the process. So, you can resume the process from where you left off if you had interrupted it.
- Setting it to `True` will force the retrieval of tiles and overwrite them, even if the grid square generation is already completed. This means starting the process from scratch.

#### INPUT_GPKG

- Defines the location of the input Grid Square data as a relative path from the current directory.

#### OUTPUT_DIR

- Defines the location of the output folder as a relative path from the current directory.

#### MESH_CLIMATE_CSV_DIR

- Defines the location of the folder containing the CSV files for the climate data as a relative path from the current directory.

## Specifications

### General

- Files are always output in the following structure under the folder specified by `OUTPUT_DIR`. Note that the `.aux.xml` file is a GDAL metadata file and is outside the scope of this program's specifications. However, it is left in place because it is small in size and harmless, and it is useful for display confirmation in software like `QGIS`.

    ```
    .
    ├── dem.png
    ├── dem.png.aux.xml
    ├── direction.png
    ├── direction.png.aux.xml
    ├── geology.png
    ├── geology.png.aux.xml
    ├── meshdata.pickle
    ├── slope.png
    └── slope.png.aux.xml
    ```

### Climate and Land Use Data and grid square Regions

- Save the meteorological data CSV files and grid square data attribute values (land use data) as Pickle format binary data.
- Store the grid square region as `minx, miny, maxx, maxy`.
- The file name should be `meshdata.pickle`.
- The Pickle data should store a `dict` with the following structure.
    ```python
    {
        "日降水量": list,
        "日照時間": list,
        "日積算日射量": list,
        "日平均気温": list,
        "日最高気温": list,
        "日最低気温": list,
        "田": int,
        "他農用地": int,
        "森林": int,
        "荒地": int,
        "建物用地": int,
        "道路": int,
        "鉄道": int,
        "他用地": int,
        "河川湖沼": int,
        "海浜": int,
        "海水域": int,
        "ゴルフ場": int,
        "minx": float,
        "miny": float,
        "maxx": float,
        "maxy": float,
    }
    ```


### Tile Data

- Obtain PNG tiles for elevation, slope, aspect, and geology, and crop them to match the grid square region. The file names correspond as follows.
    - 標高: `dem.png`
    - 傾斜: `slope.png`
    - 傾斜方向: `direction.png`
    - 地質: `geology.png`
- The zoom level for obtaining tiles is fixed at 14.
- Crop the extracted images after reprojecting the tile images (EPSG:3857) to the projection of the grid square data (EPSG:4301).
    - Use the "nearest" resampling method during reprojection.

### Miscellaneous

- Exceptions may occur due to communication with the tile server, and in such cases, the process will be interrupted. In such a situation, you can resume the process from where it was interrupted by starting it again with the same command.
