import os
import csv
import subprocess
import math
import urllib.request
import socket
import shutil
import pickle

import pandas as pd
import pyproj
import tiletanic
import shapely

############ 設定値 ############
OVERWRITE = False
INPUT_GPKG = "mesh.gpkg"
OUTPUT_DIR = "meshdata"
MESH_CLIMATE_CSV_DIR = "output"
###############################

TILE_URLS = {
    "geology": r"https://habs.rad.naro.go.jp/data_tiles/nagano/seamless_original/{z}/{x}/{y}.png",
    "dem": r"https://cyberjapandata.gsi.go.jp/xyz/dem_png/{z}/{x}/{y}.png",
    "slope": r"https://habs.rad.naro.go.jp/data_tiles/nagano/dem_gradation/{z}/{x}/{y}.png",
    "direction": r"https://habs.rad.naro.go.jp/data_tiles/nagano/dem_direction/{z}/{x}/{y}.png"
}


def is_completed(meshdata_dir: str) -> bool:
    """
    メッシュデータを保存するディレクトリについて、処理が完了しているかをチェックする
    """
    return os.path.exists(os.path.join(meshdata_dir, 'meshdata.pickle')) and \
           os.path.exists(os.path.join(meshdata_dir, 'dem.png')) and \
           os.path.exists(os.path.join(meshdata_dir, 'direction.png')) and \
           os.path.exists(os.path.join(meshdata_dir, 'geology.png')) and \
           os.path.exists(os.path.join(meshdata_dir, 'slope.png'))


def gpkg2csv(gpkg: str, output_csv_path='') -> str:
    """
    GeoPackageをCSVファイルに変換する
    CSVには属性値のほかメッシュの座標を保持する

    Args:
        gpkg (str): GeoPackageのパス
        output_csv_path (str, optional): CSVの出力先ファイルパス、未指定の場合はfoo.gpkg->foo.csv

    Returns:
        str: 出力したCSVファイルのフルパス
    """
    if output_csv_path == '':
        output_csv = gpkg.replace(".gpkg", ".csv")
    else:
        output_csv = output_csv_path

    subprocess.run(
        f"ogr2ogr {output_csv} {gpkg} -dialect sqlite -sql 'select *, ST_MinX(geom) as minx, ST_MinY(geom) as miny, ST_MaxX(geom) as maxx, ST_MaxY(geom) as maxy from \"{os.path.basename(gpkg).replace('.gpkg', '')}\"'",
        shell=True)
    return output_csv


def mesh_extent_as_webmecator(extent: tuple) -> tuple:
    """
    入力データのメッシュのCRSはEPSG:4301
    これをEPSG:3857に変換する

    Args:
        extent (tuple): [minx, miny, maxx, maxy] in EPSG:4301

    Returns:
        tuple: [minx, miny, maxx, maxy] in EPSG:3857
    """

    transformer = pyproj.Transformer.from_crs(4301, 3857, always_xy=True)
    transformed_minxy = transformer.transform(extent[0], extent[1])
    transformed_maxxy = transformer.transform(extent[2], extent[3])
    return (transformed_minxy[0],
            transformed_minxy[1],
            transformed_maxxy[0],
            transformed_maxxy[1])


def get_tile_indices_covering(extent: tuple, zoomlevel: int) -> tuple:
    """
    returns tile indices covering the extent in specific zoomlevet
    Args:
        extent (tuple): [minx, miny, maxx, maxy] in EPSG:3857
        zoomlevel (int)
    Returns:
        tuple: list of [x, y, z]
    """

    geometry = {
        "type": "Polygon",
        "coordinates": ((
                            (extent[0], extent[1]),
                            (extent[2], extent[1]),
                            (extent[2], extent[3]),
                            (extent[0], extent[3]),
                            (extent[0], extent[1]),
                        ),)
    }

    tilesceme = tiletanic.tileschemes.WebMercator()
    feature_shape = shapely.geometry.shape(geometry)
    generator = tiletanic.tilecover.cover_geometry(
        tilesceme, feature_shape, zoomlevel)
    return tuple(generator)


def make_tile_world_file(tile_png: str):
    """
    タイルPNG画像のワールドファイルを生成する
    位置情報はファイルパスから判定する(z-x-y.png -> タイルインデックスz-x-yの位置は一意)
    PNG画像と同じディレクトリ・ファイル名で、拡張子だけが違うファイルを生成する(12-34-5678.png -> 12-34-5678.pgw)

    Args:
        tile_png (str): タイル画像のパス
    """

    # ファイル名をパースしてタイルインデックスを取得
    (z, x, y) = tuple(map(int, os.path.basename(
        tile_png).replace(".png", "").split("-")))

    TILE_SIZE = 256

    # タイルインデックスからウェブメルカトルの座標を計算しワールドファイルを作成
    # https://qiita.com/MALORGIS/items/1a9114dd090e5b891bf7
    GEO_R = 6378137
    orgX = -1 * (2 * GEO_R * math.pi / 2)
    orgY = (2 * GEO_R * math.pi / 2)
    unit = 2 * GEO_R * math.pi / math.pow(2, z)
    minx = orgX + x * unit
    maxy = orgY - y * unit

    # ワールドファイルの原点位置は、ピクセルの中心を意味するので、ピクセルの半分をオフセット
    pixel_offset = 0.5 * unit / TILE_SIZE

    world_file_txt = f"""\
{unit / TILE_SIZE}
0.0
0.0
{-unit / TILE_SIZE}
{minx + pixel_offset}
{maxy - pixel_offset}"""
    with open(tile_png.replace(".png", ".pgw"), mode='w') as f:
        f.write(world_file_txt)


def merge_tiles_as_vrt(tiles_dir: str) -> str:
    """
    ワールドファイルを持った状態のPNGファイルで仮想ラスタを生成する
    引数のディレクトリにmerged.vrtというファイル名で保存される

    Args:
        tiles_dir (str): タイル画像のPNGファイルが保存されているディレクトリ

    Returns:
        str: 書き出したVRTファイルのパス
    """
    vrt = os.path.join(tiles_dir, "merged.vrt")
    pngs = os.path.join(tiles_dir, "*.png")
    subprocess.run(f"gdalbuildvrt {vrt} {pngs} -a_srs EPSG:3857", shell=True)
    return vrt


def generate_mesh_png(src: str, dst: str, extent: list, resampling="bilinear") -> str:
    """
    入力メッシュの形状で切り抜いたPNG画像を生成する
    gdalwarpで形式変換と切り抜きと再投影を同時に行う、出力形式は常にPNG
    出力されるPNGはEPSG:4301

    Args:
        src (str): 入力ラスターのファイルパス（任意形式）
        dst (str): 出力ラスターのファイルパス（PNG）
        extent (list): [minx, miny, maxx, maxy] in EPSG:4301

    Returns:
        str: 出力したラスターのファイルパス
    """
    subprocess.run(
        f"gdalwarp {src} {dst} -t_srs EPSG:4301 -te {' '.join(tuple(map(str, extent)))} -r {resampling}", shell=True)
    return dst


def read_mesh_climate_csv(meshcode: str, mesh_climate_csv_dir: str) -> dict:
    """
    メッシュコードをもとに出力済みのメッシュ気象データCSVファイルを読み込む

    Args:
        meshcode (str): 3次メッシュコード8桁
        mesh_climate_csv_dir: 気象データCSVファイルが保存されているディレクトリのパス

    Raises:
        FileNotFoundError: ファイルが存在しない場合はエラー

    Returns:
        dict: _description_
    """
    mesh_climate_csv = os.path.join(mesh_climate_csv_dir,
                                    meshcode[:6],
                                    f"{meshcode}.csv")
    if not os.path.exists(mesh_climate_csv):
        raise FileNotFoundError(f"{meshcode}: 該当するCSVファイルが存在しませんでした。")

    mesh_climate_df = pd.read_csv(mesh_climate_csv)
    return {
        "日降水量": mesh_climate_df["日降水量"].tolist(),
        "日照時間": mesh_climate_df["日照時間"].tolist(),
        "日積算日射量": mesh_climate_df["日積算日射量"].tolist(),
        "日平均気温": mesh_climate_df["日平均気温"].tolist(),
        "日最低気温": mesh_climate_df["日最低気温"].tolist(),
        "日最高気温": mesh_climate_df["日最高気温"].tolist(),
    }


def main(input_gpkg=INPUT_GPKG, output_dir=OUTPUT_DIR, mesh_climate_csv_dir=MESH_CLIMATE_CSV_DIR):
    # 1行:1メッシュデータのCSV
    csvfile = gpkg2csv(input_gpkg)

    with open(csvfile) as f:
        reader = csv.DictReader(f)
        # 1行ずつ=1メッシュずつ処理する
        for row in reader:
            # <出力先フォルダ>/<メッシュコード> というメッシュ単位のファイル群を保存するフォルダを作成
            mesh_dir = os.path.join(output_dir, row['メッシュ'])
            if os.path.exists(mesh_dir):
                if OVERWRITE or not is_completed(mesh_dir):
                    # OVERWRITEフラグがTrueか、処理が中断されたことで不完全なディレクトリの場合はやり直す
                    shutil.rmtree(mesh_dir)
                else:
                    # 処理をスキップ
                    continue

            os.makedirs(mesh_dir)

            # <出力先フォルダ>/<メッシュコード>/tmp_tiles というダウンロードしたタイル画像群を一時保存するフォルダを作成
            tmp_tiles_dir = os.path.join(mesh_dir, 'tmp_tiles')
            os.makedirs(tmp_tiles_dir, exist_ok=True)

            # GPKG->CSVとして得たデータを、型キャストしつつ辞書に
            gpkg_mesh_data = {
                "田": int(row['田']),
                "他農用地": int(row['他農用地']),
                "森林": int(row['森林']),
                "荒地": int(row['荒地']),
                "建物用地": int(row['建物用地']),
                "道路": int(row['道路']),
                "鉄道": int(row['鉄道']),
                "他用地": int(row['他用地']),
                "河川湖沼": int(row['河川湖沼']),
                "海浜": int(row['海浜']),
                "海水域": int(row['海水域']),
                "ゴルフ場": int(row['ゴルフ場']),
            }

            # 事前に生成済みのメッシュ単位気象データCSVを辞書として読み込み
            mesh_climate_data = read_mesh_climate_csv(
                row['メッシュ'], mesh_climate_csv_dir=mesh_climate_csv_dir)

            bbox_data = {
                "minx": float(row['minx']),
                "miny": float(row['miny']),
                "maxx": float(row['maxx']),
                "maxy": float(row['maxy']),
            }

            # 辞書をPickleファイルとして書き出し
            with open(os.path.join(mesh_dir, "meshdata.pickle"), mode='wb') as g:
                pickle.dump({**gpkg_mesh_data, **mesh_climate_data, **bbox_data}, g)

            # メッシュに重なるXYZタイルのインデックス(x,y,z)を全て取得する
            mesh_extent_4301 = tuple(
                map(float, (row['minx'], row['miny'], row['maxx'], row['maxy'])))
            mesh_extent_3857 = mesh_extent_as_webmecator(mesh_extent_4301)
            tiles = get_tile_indices_covering(mesh_extent_3857, 14)

            # タイルダウンロード処理
            for tile in tiles:
                (x, y, z) = tile
                for tilename in TILE_URLS:
                    # <出力先フォルダ>/<メッシュコード>/tmp_tiles/<タイル名>としてダウンロードしたタイル画像を保存するフォルダを作成
                    tmp_child_tiles_dir = os.path.join(tmp_tiles_dir, tilename)
                    os.makedirs(tmp_child_tiles_dir, exist_ok=True)

                    url = TILE_URLS[tilename].replace(r"{x}", str(x)).replace(
                        r"{y}", str(y)).replace(r"{z}", str(z))
                    while True:
                        try:
                            data = urllib.request.urlopen(url, timeout=5)
                            break
                        except urllib.error.URLError as e:
                            # HTTPがタイムアウトの場合のみ再試行する
                            if isinstance(e.reason, socket.timeout):
                                print(f"{url}: connection timeout, retry...")
                                continue
                            raise e

                    # ダウンロードしたデータをz-x-y.pngとして書き出し
                    tile_png = os.path.join(
                        tmp_child_tiles_dir, f"{z}-{x}-{y}.png")
                    with open(tile_png, mode='wb') as f:
                        f.write(data.read())
                    # z-x-y.pngに対し、z-x-y.pgwというワールドファイルを作成する
                    make_tile_world_file(tile_png)

            # ダウンロードしたタイル画像をEPSG:4301のメッシュに合わせて切り出し
            for tilename in TILE_URLS:
                tmp_child_tiles_dir = os.path.join(tmp_tiles_dir, tilename)
                merged_vrt = merge_tiles_as_vrt(tmp_child_tiles_dir)
                generate_mesh_png(merged_vrt,
                                  os.path.join(
                                      mesh_dir, f'{tilename}.png'),
                                  mesh_extent_4301,
                                  resampling="nearest")

            shutil.rmtree(tmp_tiles_dir)


if __name__ == "__main__":
    main()
