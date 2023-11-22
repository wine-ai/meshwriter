import os

import pandas as pd


def geology_xlsx_to_json():
    """
    「長野県岩相区分.xlsx」の内容をjsonに保存する。
    xlsxファイルに変更があった時に実行する。
    """
    # エクセルをpd.dataframeとして読み込み
    geology_rgb = pd.read_excel("長野県岩相区分.xlsx")

    # RGBから得たhex値をhexカラムに保存する
    geology_rgb["hex"] = geology_rgb.apply(lambda s: '#{:02x}{:02x}{:02x}'.format(s["R"], s["G"], s["B"]), axis=1)

    # 必要なカラムだけ残す
    geology_hex = geology_rgb.loc[:, ["hex", "ピクセル値"]]

    # jsonファイル書き出す
    geology_hex.to_json(os.path.join(os.path.dirname(__file__), "geology_hex.json"), orient='values')


def main():
    geology_xlsx_to_json()


if __name__ == "__main__":
    main()
