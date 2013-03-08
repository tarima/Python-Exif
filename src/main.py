#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import glob
import logging
import webapp2

from google.appengine.ext.webapp import template
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

EXIFGPSINFO = "GPSInfo"
EXIFDATETIME = "DateTimeOriginal"
EXIFGPSLAT = "GPSLatitude"
EXIFGPSLATREF = "GPSLatitudeRef"
EXIFGPSLON = "GPSLongitude"
EXIFGPSLONREF = "GPSLongitudeRef"

# PIL.ExifTagsのTAGSとGPSTAGSを使用してExifで取得可能な全データを取得する
def getExifData(image):
    exifData = {}
    exifInfo = image._getexif()
    if exifInfo:
        for tagData, value in exifInfo.items():
            keyData = TAGS.get(tagData, tagData)
            if keyData == EXIFGPSINFO:
                # GPSに関する情報（位置情報など）。階層構造になっている。
                gpsData = {}
                for subTagData in value:
                    subKeyData = GPSTAGS.get(subTagData, subTagData)
                    gpsData[subKeyData] = value[subTagData]
                exifData[keyData] = gpsData
            else:
                # GPS以外に関する情報（日時情報など）。
                exifData[keyData] = value
    return exifData

# キーが無い場合はNoneを返す
def getKeyData(data, key):
    if key in data:
        return data[key]
    return None

# 時間から経度、緯度を算出する。
def convertDegrees(value):
    # GPSTAGSでは、時、分、秒をそれぞれ分母と分子でもつListで返ってくる。
    date = float(value[0][0]) / float(value[0][1])
    minute = float(value[1][0]) / float(value[1][1])
    second = float(value[2][0]) / float(value[2][1])

    # 少数形式に変換する。
    return date + (minute / 60.0) + (second / 3600.0)

# 経度、緯度をGoogle Mapに利用する形式で取得
def getPosition(distance, direction, compType):
    posi = None

    if distance and direction:
        posi = convertDegrees(distance)
        if direction == compType:
            posi = 0 - posi

    return posi

#引数からもらったExifデータから経度と緯度を返す
def getLatAndLon(exifData):
    lat = None
    lon = None

    if EXIFGPSINFO in exifData:
        gpsInfo = exifData[EXIFGPSINFO]
        gpsLat    = getKeyData(gpsInfo, EXIFGPSLAT)     # 緯度
        gpsLatRef = getKeyData(gpsInfo, EXIFGPSLATREF)  # 北緯(N)、南緯(S)
        gpsLon    = getKeyData(gpsInfo, EXIFGPSLON)     # 緯度
        gpsLonRef = getKeyData(gpsInfo, EXIFGPSLONREF)  # 東経(E)、西経(W)

        lat = getPosition(gpsLat, gpsLatRef, "S");
        lon = getPosition(gpsLon, gpsLonRef, "W");

    return lat, lon

# イメージファイルのパスを取得
def getImgPath():
    return os.getcwd() + "/src/imgs/"

# イメージファイルを取得
def getImgFiles():
    imgFiles = os.listdir(getImgPath())
    #logging.debug("images files:" + imgFiles)

    return imgFiles

# イメージリスト取得
def getImgList(imgFiles):
    imgList = []
    imgTitle = "金沢日記"
    imgPath = getImgPath()
    cnt = 0

    for imgFile in imgFiles:
    cnt += 1
        image = Image.open(imgPath + imgFile)
        exifData = getExifData(image)                   # Exifデータ取得
        datetime = getKeyData(exifData, EXIFDATETIME)   # 日時取得
        lat,lon = getLatAndLon(exifData)                # 位置取得
        # 画像情報のディクショナリ作成
        imageInfo = {
            "imgpath": "img/" + imgFile,
            "datetime": datetime,
            "lat": lat,
            "lon": lon,
            "imgtilte": imgTitle + " ("  + str(cnt) + ")"
        }
        logging.debug(imageInfo)
        imgList.append(imageInfo)

    return imgList

# テンプレートのJS部分に渡すディクショナリ生成
def getTemplateJs(imgList):
    templateJsValues = {
        "imgList": imgList,
    }
    return templateJsValues

# テンプレートの地図部分に渡すディクショナリ生成
def getTemplateMap(imgFiles, imgList, mapsJs):
    templateMapValues = {
        "mapsjs": mapsJs,
        "imgFiles": imgFiles,
        "imgList": imgList,
    }
    return templateMapValues

class MainPage(webapp2.RequestHandler):
  def get(self):
    logging.getLogger().setLevel(logging.DEBUG)

    imgFiles = getImgFiles()
    imgList = getImgList(imgFiles)
    # テンプレートのJS部分をレンダリング
    mapsJsPath = os.path.join(os.path.dirname(__file__), "../template/maps_js.html")
    mapsJs = template.render(mapsJsPath, getTemplateJs(imgList))
    # テンプレートの地図部分をレンダリング
    mapsTempatePath = os.path.join(os.path.dirname(__file__), "../template/maps_template.html")
    self.response.out.write(template.render(mapsTempatePath, getTemplateMap(imgFiles, imgList, mapsJs)))

def uploadHandler(request):
    file_io = request.POST["file"].file
    image = Image.open(file_io)

    try:
        exifData = getExifData(image)
        dateTime = exifData[EXIFDATETIME]
        lat, lon = getLatAndLon(exifData)
        response = "(Lat,Lon) = (%f,%f),  Date = %s"  % (lat, lon, dateTime)
        return webapp2.Response(response)
    except:
        return webapp2.Response("No GPS Information")


app = webapp2.WSGIApplication([
    ("/maps", MainPage),
    ("/upload", uploadHandler)
    ],debug=True)
