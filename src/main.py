#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import webapp2

from google.appengine.ext.webapp import template
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

class MainPage(webapp2.RequestHandler):
  def get(self):
    path = os.path.join(os.path.dirname(__file__), '../template/maps_template.html')
    self.response.out.write(template.render(path, 0))

# PIL.ExifTagsのTAGSとGPSTAGSを使用してExifで取得可能な全データを取得する
# TAGSとGPSTAGSについてはURL参照　
# 1.http://pydoc.net/Pillow/1.1/PIL.ExifTags
# 2.http://www.geopacific.org/opensourcegis/python/8q9u2w
# 3.https://gist.github.com/erans/983821#file-get_lat_lon_exif_pil-py-L34
def get_exif_data(image):
    exif_data = {}
    info = image._getexif()
    if info:
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                gps_data = {}
                for t in value:
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_data[sub_decoded] = value[t]
                exif_data[decoded] = gps_data
            else:
                exif_data[decoded] = value
    return exif_data

# キーが無い場合はNoneを返す
def _get_if_exist(data, key):
    if key in data:
        return data[key]
    return None

# GPSTAGSでは、時、分、秒をそれぞれ分母と分子でもつListで返ってくる。
# Google Maps APIで使うためには、小数の形式に変換する必要があるらしい。
def _convert_to_degrees(value):
    # degrees = value[0][0] / value[0][1] / 1.0     #これでも変換できたが精度が悪かった
    # degrees += value[1][0] / value[1][1] / 60.0
    # degrees += value[2][0] / value[2][1] / 3600.0
    # return degrees

    d0 = value[0][0]
    d1 = value[0][1]
    d = float(d0) / float(d1)

    m0 = value[1][0]
    m1 = value[1][1]
    m = float(m0) / float(m1)

    s0 = value[2][0]
    s1 = value[2][1]
    s = float(s0) / float(s1)

    return d + (m / 60.0) + (s / 3600.0)

#引数からもらったExifデータから経度と緯度を返す
def get_lat_lon(exif_data):
    lat = None
    lon = None

    if "GPSInfo" in exif_data:
        gps_info = exif_data["GPSInfo"]

        # 位置情報に関するタグは全部で27あり、今回使用するのは以下。
        # 0x0001 GPSLatitudeRef:北緯(N)or 南緯(S) 
        # 0x0002　GPSLatitude:緯度（数値） ((38, 1), (58, 1), (115005, 16384))のような感じで、時分秒で取得できる。
        # 0x0003　GPSLongitudeRef:東経(E)or 西経(W)
        # 0x0004　GPSLongitude:経度（数値）　取得される値は緯度と同じ形。
        gps_latitude = _get_if_exist(gps_info, "GPSLatitude")
        gps_latitude_ref = _get_if_exist(gps_info, 'GPSLatitudeRef')
        gps_longitude = _get_if_exist(gps_info, 'GPSLongitude')
        gps_longitude_ref = _get_if_exist(gps_info, 'GPSLongitudeRef')

        if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:#is not None
            lat = _convert_to_degrees(gps_latitude)
            if gps_latitude_ref != "N":
                lat = 0 - lat

            lon = _convert_to_degrees(gps_longitude)
            if gps_longitude_ref != "E":
                lon = 0 - lon
    return lat, lon

def uploadHandler(request):
    file_io = request.POST['file'].file
    image = Image.open(file_io)

    try:
        # GPSInfo = image._getexif()[34853] #この方法でも経度緯度が取れるが、数字キーが分かりにくいので使わない
        # lat = _convert_to_degrees(GPSInfo[2])
        # lng = _convert_to_degrees(GPSInfo[4])
        # if GPSInfo[1] != 'N':
        #     lat = -lat
        # if GPSInfo[3] != 'E':
        #     lng = -lng
        # response = 'Lat = %f, Lng = %f' % (lat, lng)
        # return webapp2.Response(response)

        exif_data = get_exif_data(image)    #Exif全データ取得。日時と位置しか必要ない場合は無駄な処理が多いかも。
        
        # 日時に関するタグは以下。ここでは撮影した画像をデコった場合のことを考慮して、撮影日時であるDateTimeOriginalを使用する
        # 0x0132 DateTime:原画像データの編集日時
        #         編集された日時。"YYYY:MM:DD HH:MM:SS"形式で保存。
        # 0x9003 DateTimeOriginal:原画像データの生成日時
        #         撮影された日時。"YYYY:MM:DD HH:MM:SS"形式で保存。
        # 0x9004　DateTimeDigitized:デジタルデータの作成日時
        #         画像がデジタルデータ化された日時。"YYYY:MM:DD HH:MM:SS"形式で保存。
        # 0x9290　SubSecTime:DateTimeのサブセック
        #         DateTimeタグに関連して時刻を少数点以下の秒単位まで記録。
        # 0x9291　SubSecTimeOriginal:DateTimeOriginalのサブセック
        #         DateTimeOriginalタグに関連して時刻を少数点以下の秒単位まで記録。
        # 0x9292　SubSecTimeDigitized:DateTimeDigitizedのサブセック
        #         DateTimeDigitizedタグに関連して時刻を少数点以下の秒単位まで記録。
        datetime = exif_data["DateTimeOriginal"]

        # 経度緯度の取得
        lat,lon = get_lat_lon(exif_data)

        response = '(Lat,Lon) = (%f,%f),  Date = %s' % (lat, lon, datetime)

        return webapp2.Response(response)

    except:
        return webapp2.Response('No GPS Information')


app = webapp2.WSGIApplication([
    ('/maps', MainPage),
    ('/upload', uploadHandler)
    ],debug=True)