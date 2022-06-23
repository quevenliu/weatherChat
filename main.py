from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, LocationMessage, SourceUser,
)

import os
import json
import requests
from math import *
import datetime
import boto3
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')

LINE_ACCESS_TOKEN = ""

OPEN_MAP_TOKEN = ""

SECRET = ""

AQICN_TOKEN = ""

def getAQString(value):
    if value < 50:
      return "良好"
    if value > 50 and value <= 100:
      return "普通"
    if value >= 100 and value < 150:
      return "不適於敏感人群"
    if value > 150 and value < 200:
      return "不健康"
    if value >= 200:
      return "非常不健康"
    return "無法取得"
  

def msgGen(lon, lat):

    forecastWeatherUrl = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&units=metric&lang=zh_tw&appid={OPEN_MAP_TOKEN}"
    currentWeatherUrl = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&lang=zh_tw&appid={OPEN_MAP_TOKEN}"
    aqiurl = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={AQICN_TOKEN}"
      
    weatherData = json.loads(requests.get(forecastWeatherUrl).text)
    currentWeather = json.loads(requests.get(currentWeatherUrl).text)
    aqiData = json.loads(requests.get(aqiurl).text)
    reply_message = textGen(weatherData["cnt"], weatherData["list"], currentWeather, aqiData)
         
    return reply_message

def textGen(cnt, weatherDataList, currentWeather, aqiData):
    currentTime = datetime.datetime.now()
    returnMessage = f"您好，您所選擇的地方目前溫度{round(currentWeather['main']['temp'])}°C，體感{round(currentWeather['main']['feels_like'])}°C，{currentWeather['weather'][0]['description']} ，空氣品質{getAQString(int(aqiData['data']['aqi']))}，為您播報您所在的地方的未來天氣\n"
    difd = 2
    if currentTime.hour < 18:
        difd = 1
    
    for i in range(0, len(weatherDataList)):
        forecastTime = datetime.datetime.fromtimestamp(int(weatherDataList[i]['dt']))

        if (forecastTime.hour + 8) % 24 == 2 and forecastTime.day == currentTime.day + difd:
            break
          
        else:
            timeStr = f"{(forecastTime.hour + 8) % 24}:00"
            returnMessage += f'''{timeStr.ljust(7)}{round(weatherDataList[i]['main']['temp'])}°C，體感 {round(weatherDataList[i]['main']['feels_like'])}°C
            {weatherDataList[i]['weather'][0]['description'].ljust(4)}降雨機率 {int(weatherDataList[i]['pop'] * 100)}%\n'''
    

    return returnMessage.rstrip()


line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(SECRET)





def lambda_handler(event, context):
    
    
    signature = event['headers']['x-line-signature']
    
    body = event['body']

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return {
            'statusCode': 502,
            'body': json.dumps("Invalid signature. Please check your channel access token/channel secret.")
            }
    
    return {
        'statusCode': 200,
        'body': json.dumps("Successful")
        }
        
        
@handler.add(MessageEvent, message=LocationMessage)
def locationHandler(event):
    table = dynamodb.Table('weatherChat')

    response = table.get_item(
        Key={
            'user_id': str(event.source.user_id),
        }
    )
    if response != dict():
        try:
            if response["Item"]["isSet"] == 1:
                table.update_item(TableName = "weatherChat",
                    Key= {
                        "user_id":event.source.user_id,
                        }, UpdateExpression= "SET #latitude = :latitude, #longitude = :longitude, #isSet = :isSet",
                    ExpressionAttributeValues= {
                            ":latitude": Decimal(str(event.message.latitude)),
                            ":longitude": Decimal(str(event.message.longitude)),
                            ":isSet": 2,
                    },
                    ExpressionAttributeNames= {
                        "#latitude" : "latitude",
                        "#longitude": "longitude",
                        "#isSet" : "isSet"
                    }
                    
        
                )
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="已完成設定"))
                return
        except Exception as e:
            line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=str(e)))
            
    
    line_bot_api.reply_message(
    event.reply_token,
    TextSendMessage(text=f"{msgGen(event.message.longitude, event.message.latitude)}")
    )
    
@handler.add(MessageEvent, message=TextMessage)
def locationHandler(event):
    table = dynamodb.Table('weatherChat')
    
    try:
        if event.message.text.isnumeric():
            response = table.get_item(
            Key={
                'user_id': event.source.user_id,
            }
            )
            
            
            if response["Item"]["time"] == 0 and response["Item"]["isSet"] == 0:
                table.update_item(TableName = "weatherChat",
                Key= {
                    "user_id":event.source.user_id,
                    }, UpdateExpression= "SET #time = :time, #isSet = :isSet",
                ExpressionAttributeValues= {
                        ":time": event.message.text,
                        ":isSet": 1,
                },
                ExpressionAttributeNames= {
                    "#time" : "time",
                    "#isSet": "isSet"
                }
                
    
                )
            
                line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="請輸入你希望播報的位置")
                )
                return
            
    except ClientError as e:
        print(e.response['Error']['Message'])
        line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="發生錯誤")
    )
    
    
    if event.message.text != "通知設定" and event.message.text != "說明":
        line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="請傳送您的位置信息💓💓")
    )
    elif event.message.text == "通知設定":
        
        response = table.put_item(
        Item={
        'user_id': event.source.user_id,
        'time': 0,
        'latitude': 0,
        'longitude': 0,
        'isSet': 0,
        })
        line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="接下來請告訴我要幾點提醒你~~💓💓 \n（目前僅支援整點，請輸入整數，如下午三點請輸入15，晚上十二點請輸入0）")
    )
    elif event.message.text == "說明":
        line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="直接傳送位置信息即可知道該地的天氣，若希望設定固定地點的每日提醒，請點選「通知設定」！")
    )
