# メッシュデータ生成プログラム

メッシュデータ生成プログラムとは、所定のメッシュデータをもちいて、各メッシュ地物の範囲と一致するように切り出したタイル画像および地物の属性等を格納したバイナリファイルを生成するプログラムです。本書は、本プログラムの仕様・使用方法などを記載するものです。

## 動作確認環境

- Python 3.8および下記のライブラリ
    - pandas v1.4.1
    - shapely v1.8.1.post1
    - tiletanic v1.1.0
    - pyproj v3.3.0
    - Pillow v8.0.0
- GDAL v3.4.0

## 環境構築

`Docker`をもちいて下記のとおりイメージをビルドします。

```sh
cd meshwriter
docker build . -t meshscript
```

## 岩相辞書ファイルの作成

- `prepare.py`は地質PNGのピクセル値を変換するための辞書を作成するスクリプトです。
- `長野県岩相区分.xlsx`に変更があった場合は下記コマンドによりスクリプトを実行し、生成される`geology_hex.json`を、本プログラムを実行して得られるメッシュデータディレクトリ直下に配置してください。

```shell
cd src/meshwriter
docker run --rm -v $PWD:/usr/src/app meshscript python3 prepare.py
#./meshwriter/geology_hex.json として生成されます
```


## 入力ファイルの配置

`./meshwriter`以下に、`mesh.gpkg`および`気象情報CSVフォルダ(下記例ではoutput)`を配置します。

```
./meshwriter
├── Dockerfile
├── README.md
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
// 以下略
```


## 実行方法

```sh
cd meshwriter
docker run --rm -v $PWD:/usr/src/app meshscript python3 __main__.py
```

上記のとおり処理を開始すると、`./meshwriter/meshdata`にメッシュデータが生成されていきます。全ての処理が完了するまで2時間ほどかかると思われます。


### 設定項目

上述のとおりファイル等を配置すればメッシュデータを生成できますが、設定を変更可能な項目がいくつかあります。
設定は`__main__.py`ファイル冒頭の下記の変数で定義されます。

```python
# __main__.pyの15行目以下
############ 設定値 ############
OVERWRITE = False
INPUT_GPKG = "mesh.gpkg"
OUTPUT_DIR = "meshdata"
MESH_CLIMATE_CSV_DIR = "output"
###############################
```

#### OVERWRITE(上書き)

- デフォルトは`False`です。この場合、既に生成が完了したメッシュについては処理をスキップします。なので一度中断しても途中から再開が可能です。
- `True`とすると、既に生成が完了したメッシュがあっても、再度タイルを取得し上書きします。全て最初からやり直すという意味です。

#### INPUT_GPKG

- 入力メッシュデータの位置を、カレントディレクトリから見た相対パスで定義します。

#### OUTPUT_DIR

- 出力フォルダの位置を、カレントディレクトリから見た相対パスで定義します。

#### MESH_CLIMATE_CSV_DIR

- 2020年度成果のCSVファイル群を含むフォルダの位置を、カレントディレクトリから見た相対パスで定義します。

## 仕様

### 全般

- `OUTPUT_DIR`で指定したフォルダ以下に、常に下記の構造でファイルを出力する。なお、`.aux.xml`ファイルはGDALのメタデータファイルであり、今回のプログラム仕様の範囲外のファイルであるが、ファイルサイズは小さく無害なことと、`QGIS`などで表示確認をする際に便利であるため、配置したままとする。
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

### 気候・土地利用データおよびメッシュ領域について

- 2020年度成果のCSVファイル群およびメッシュデータの属性値（土地利用データ）をPickle形式のバイナリデータとして保存する。
- メッシュ領域を`minx, miny, maxx, maxy`として格納する。
- ファイル名は`meshdata.pickle`とする。
- Pickleデータには、下記構造の`dict`を保存する。
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


### タイルデータについて

- 標高、傾斜、傾斜方向、地質はPNGタイルを取得し、メッシュの領域に一致するよう切り出す。ファイル名の対応は下記のとおり。
    - 標高: `dem.png`
    - 傾斜: `slope.png`
    - 傾斜方向: `direction.png`
    - 地質: `geology.png`
- 取得するタイルのズームレベルはすべて14とする。
- 切り出し画像は、タイル画像（EPSG:3857）をメッシュデータの投影法（EPSG:4301）へ再投影したうえで切り出す。
    - 再投影時のリサンプリング手法は`nearest`とする。

### その他

- タイルサーバーとの通信状況によって例外が発生することがあり、その際は処理が中断されます。その場合は再度同じコマンドで処理を開始すれば、中断された箇所から再開することができます。
