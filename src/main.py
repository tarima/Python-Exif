#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import glob
import logging
import webapp2
import datetime
import dircache

from google.appengine.ext.webapp import template
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

EXIFGPSINFO = "GPSInfo"
EXIFDATETIME = "DateTimeOriginal"
EXIFGPSLAT = "GPSLatitude"
EXIFGPSLATREF = "GPSLatitudeRef"
EXIFGPSLON = "GPSLongitude"
EXIFGPSLONREF = "GPSLongitudeRef"
EXIFIMAGEDESCRIPTION = "ImageDescription"
EXIFUSERCOMMENT = "Artist"
DYNAMIC_IMG_PATH = "/src/imgs/"
IMG_DIR = "img/"
JS_TEMPLATE_PATH = "../template/maps_js.html"
MAPS_TEMPLATE_PATH = "../template/maps_template.html"

class Exif:
    # PIL.ExifTagsのTAGSとGPSTAGSを使用してExifで取得可能な全データを取得する
    @classmethod
    def getExifData(cls, image):
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
    @classmethod
    def getKeyData(cls, data, key):
        if key in data:
            return data[key]
        return None

    # 時間から経度、緯度を算出する。
    @classmethod
    def __convertDegrees(cls, value):
        # GPSTAGSでは、時、分、秒をそれぞれ分母と分子でもつListで返ってくる。
        date = float(value[0][0]) / float(value[0][1])
        minute = float(value[1][0]) / float(value[1][1])
        second = float(value[2][0]) / float(value[2][1])

        # 少数形式に変換する。
        return date + (minute / 60.0) + (second / 3600.0)

    # 経度、緯度をGoogle Mapに利用する形式で取得
    @classmethod
    def __getPosition(cls, distance, direction, compType):
        posi = None

        if distance and direction:
            posi = cls.__convertDegrees(distance)
            if direction == compType:
                posi = 0 - posi

        return posi

    #引数からもらったExifデータから経度と緯度を返す
    @classmethod
    def getLatAndLon(cls, exifData):
        lat = None
        lon = None

        if EXIFGPSINFO in exifData:
            gpsInfo = exifData[EXIFGPSINFO]
            gpsLat    = cls.getKeyData(gpsInfo, EXIFGPSLAT)     # 緯度
            gpsLatRef = cls.getKeyData(gpsInfo, EXIFGPSLATREF)  # 北緯(N)、南緯(S)
            gpsLon    = cls.getKeyData(gpsInfo, EXIFGPSLON)     # 緯度
            gpsLonRef = cls.getKeyData(gpsInfo, EXIFGPSLONREF)  # 東経(E)、西経(W)

            lat = cls.__getPosition(gpsLat, gpsLatRef, "S");
            lon = cls.__getPosition(gpsLon, gpsLonRef, "W");

        return lat, lon

class ImageFiles:
    __east = 0;     # 東
    __west = 300;   # 西
    __south = 300;  # 南
    __north = 0;    # 北

    # イメージファイルのパスを取得
    @classmethod
    def __getImgPath(cls):
        return os.getcwd() + DYNAMIC_IMG_PATH

    # イメージファイルを取得
    @classmethod
    def getImgFiles(cls):
        imgFiles = dircache.listdir(cls.__getImgPath())
        #logging.debug("images files:" + imgFiles)

        return imgFiles

    # 日時フォーマット変換
    @classmethod
    def __changeDateTimeFormat(cls, exifDateTime):
        # YYYY:MM:DD hh:mm:ss --> WWW MMM DD hh:mm:ss YYYY
        tmp = exifDateTime.replace(" ", ":")
        params = tmp.split(":")
        dt = datetime.datetime(int(params[0]), int(params[1]), int(params[2]), 
                              int(params[3]), int(params[4]), int(params[5]))
        return dt.ctime()

    # 画像情報のディクショナリ作成
    @classmethod
    def __getImageInfo(cls, imgFile, datetime, imgTitle, lat, lon, userComment):
        imageInfoValues = {
                "imgpath": IMG_DIR + imgFile,
                "datetime": datetime,
                "lat": lat,
                "lon": lon,
                "imgtitle": imgTitle,
                "userComment": userComment
        }
        return imageInfoValues

    # 東西南北の決定
    @classmethod
    def __compareLatLon(cls, lat, lon):
        if(lat > cls.__north):
            cls.__north = lat # 最北
        if(lat < cls.__south):
            cls.__south = lat # 最南
        if(lon > cls.__east):
            cls.__east = lon # 最東
        if(lon < cls.__west):
            cls.__west = lon # 最西

    # 画像の中央位置を取得
    @classmethod
    def getCenter(cls):
        return (cls.__north + cls.__south)/2, (cls.__east + cls.__west)/2

    # イメージリスト取得
    @classmethod
    def getImgList(cls, imgFiles):
        imgList = []
        imgPath = cls.__getImgPath()
        centerLatCal = 0
        centerLotCal = 0

        for imgFile in imgFiles:
            # 画像位置情報の取得
            image = Image.open(imgPath + imgFile)
            exifData = Exif.getExifData(image)                                              # Exifデータ取得
            datetime = cls.__changeDateTimeFormat(Exif.getKeyData(exifData, EXIFDATETIME))  # 日時取得
            lat,lon = Exif.getLatAndLon(exifData)                                           # 位置取得
            imgTitle = Exif.getKeyData(exifData, EXIFIMAGEDESCRIPTION)                      # タイトル取得
            userComment = Exif.getKeyData(exifData, EXIFUSERCOMMENT)                        # ユーザーコメント取得
            imageInfo = cls.__getImageInfo(imgFile, datetime, imgTitle, lat, lon, userComment)  # 画像情報のディクショナリ作成
            logging.debug(imageInfo)
            imgList.append(imageInfo)
            # 東西南北の決定
            cls.__compareLatLon(lat, lon)
        return imgList

    # テンプレートのJS部分に渡すディクショナリ生成
    @classmethod
    def getTemplateJs(cls, imgList, centerLat, centerLon):
        templateJsValues = {
            "imgList": imgList,
            "centerLat": centerLat,
            "centerLon": centerLon,
        }
        return templateJsValues

    # テンプレートの地図部分に渡すディクショナリ生成
    @classmethod
    def getTemplateMap(cls, mapsJs):
        templateMapValues = {
            "mapsjs": mapsJs,
        }
        return templateMapValues

class MainPage(webapp2.RequestHandler):
  def get(self):
    logging.getLogger().setLevel(logging.DEBUG)

    imgFiles = ImageFiles.getImgFiles()
    imgList = ImageFiles.getImgList(imgFiles)
    centerLat, centerLon = ImageFiles.getCenter()
    # テンプレートのJS部分をレンダリング
    mapsJsPath = os.path.join(os.path.dirname(__file__), JS_TEMPLATE_PATH)
    mapsJs = template.render(mapsJsPath, ImageFiles.getTemplateJs(imgList, centerLat, centerLon))
    # テンプレートの地図部分をレンダリング
    mapsTempatePath = os.path.join(os.path.dirname(__file__), MAPS_TEMPLATE_PATH)
    self.response.out.write(template.render(mapsTempatePath, ImageFiles.getTemplateMap(mapsJs)))

app = webapp2.WSGIApplication([
    ("/maps", MainPage),
    ],debug=True)
