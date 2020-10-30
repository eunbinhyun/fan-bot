#!/usr/bin/env python
# -*- coding: utf-8  

#
#     http://www.apache.org/licenses/LICENSE-2.0
#

import requests as rq
from bs4 import BeautifulSoup 
import json
import random
from firebase import firebase
from http.client import HTTPException
from urllib.error import HTTPError, URLError

from flask import Flask, jsonify, make_response, request, render_template 
from googleapiclient.discovery import build

from language_list import _LANGUAGE_CODE_LIST as language_code_dict
from language_list import _LANGUAGE_LIST as language_dict
from translate_response import (_TRANSLATE_ERROR, _TRANSLATE_INTO_W,
                                _TRANSLATE_NETWORK_ERROR, _TRANSLATE_RESULT,
                                _TRANSLATE_UNKNOWN_LANGUAGE, _TRANSLATE_W,
                                _TRANSLATE_W_FROM, _TRANSLATE_W_FROM_TO,
                                _TRANSLATE_W_TO)
import tweepy
import urllib.request
import re

#네이버 api
client_id = "input client id"
client_secret = "input client secret"
#twitter api
ACCESS_TOKEN = 'input access token'
ACCESS_SECRET = 'input access secret'
CONSUMER_KEY = 'input consumer key'
CONSUMER_SECRET = 'input consumer secret'
#firebase
firebasea = firebase.FirebaseApplication("input url", None)

    
# API key to access the Google Cloud Translation API
# 1. Go to console.google.com create or use an existing project
# 2. Enable the Cloud Translation API in the console for your project
# 3. Create an API key in the credentials tab and paste it below
API_KEY = 'input api key'
TRANSLATION_SERVICE = build('translate', 'v2', developerKey=API_KEY)

app = Flask(__name__)
log = app.logger




@app.route('/webhook', methods=['POST'])
def webhook():    

    # Get request parameters
    req = request.get_json(force=True)
    action = req.get('queryResult').get('action')

    # Check if the request is for the translate action
    if action == 'translate.text': #action name
        # Get the parameters for the translation
        text = req['queryResult']['parameters'].get('text')   #get ('parameter name') ,input value into text variable
        source_lang = req['queryResult']['parameters'].get('lang-from') 
        target_lang = req['queryResult']['parameters'].get('lang-to')

        # Fulfill the translation and get a response
        output = translate(text, source_lang, target_lang)

        # Compose the response to Dialogflow
        res = {'fulfillmentText': output,
               'outputContexts': req['queryResult']['outputContexts']}

    #twitter
    elif action == 'read_tweet.text': 
        search_id_word =  get_twitter_id()
        output = tweet_timeline(search_id_word)
        res = {'fulfillmentText': "[twitter]"+"\n"+output,
               'outputContexts': req['queryResult']['outputContexts']}
    
    elif action == 'read_tweet_more.text': 
        search_id_word =  get_twitter_id()
        link = 'https://twitter.com/'
        output = link+search_id_word
        res = {'fulfillmentText': "twitter link!"+"\n"+output,
               'outputContexts': req['queryResult']['outputContexts']}

    elif action == 'search.text':
        artist_search_word = get_search_word()
        output = search_news(0,0,artist_search_word) 
        res = {'fulfillmentText': output,
               'outputContexts': req['queryResult']['outputContexts']}

    elif action == 'select_news.text':
        news_num = req['queryResult']['parameters'].get('select_news_num')
        news_num = int(news_num)
        artist_search_word = get_search_word()
        # 함수에 넘버전달
        output = search_news(news_num,0,artist_search_word)
        # 링크가져오기.   
        res = {'fulfillmentText': 'NO. '+str(news_num)+' News link!'+'\n'+output,
               'outputContexts': req['queryResult']['outputContexts']}
        # 다른 뉴스 가져오기         
    elif action == 'search_news_another.text':
        artist_search_word = get_search_word()
        output = search_news(0,1,artist_search_word) #news_page가 1이면 다음장(6번~10번 까지 검색)
     
        # 링크가져오기.   
        res = {'fulfillmentText': output,
               'outputContexts': req['queryResult']['outputContexts']}
          
    elif action == 'select_news_another.text': 
        news_num = req['queryResult']['parameters'].get('select_news_num')
        news_num = int(news_num)
        artist_search_word = get_search_word()

        # 함수에 넘버전달
        output = search_news(news_num,1,artist_search_word)
        # 링크가져오기.   
        res = {'fulfillmentText': 'NO. '+str(news_num)+'\n'+output,
               'outputContexts': req['queryResult']['outputContexts']}

    elif action == 'datachange.text': # favorite 가수 변경
        singer = req['queryResult']['parameters'].get('singer')
        
        firebasea.get('favorite', None) # favorite에 접근 기존거 삭제
        firebasea.delete('','favorite') # 지우기
        output = str(singer)
        firebasea.put('','favorite',output)# 추가
        res_db = firebasea.get('favorite', None)# 재접근
        res_db = firebasea.get('/'+res_db, None) # 가수가 가진데이터로가기
        output = res_db['greet']
        res = {'fulfillmentText': output + '\n'+'change success!', 
               'outputContexts': req['queryResult']['outputContexts']}

    elif action == 'schedule.text':
        link = get_schedule_link()
        output = get_schedule(link)
       
        res = {'fulfillmentText': "[schedule]"+"\n"+output,
               'outputContexts': req['queryResult']['outputContexts']}   
    
    else:
        # If the request is not to the translate.text action throw an error
        log.error('Unexpected action requested: %s', json.dumps(req))
        res = {'speech': 'error', 'displayText': 'error'}
    
    return make_response(jsonify(res))

def get_schedule(link):
    req = urllib.request.Request(link); # 링크
    data = urllib.request.urlopen(req).read() 
    bs = BeautifulSoup(data, 'html.parser') 
    # div 태그 중, class가 tit3인 태그를 찾는다.
    tag = bs.find('ul', attrs={'class': 'list-group checked-list-box'})
    text=[]
    res=""
    i = 0
    tags = bs.findAll('li', attrs={'class': 'list-group-item'}) # 스케줄리스트찾기
    for tag in tags :
        # 검색된 태그에서 a 태그에서 텍스트를 가져옴

        sentence = tag.text
        pattern = re.compile(r'\s+') # 모든 공백문자 잘라내기
        sentence = re.sub(pattern, ' ', sentence)
        text.append(sentence)
    
        res += text[i]+'\n'
        i += 1

    return res

def tweet_timeline(search_id_word):
    # 트위터
    auth = tweepy.OAuthHandler(CONSUMER_KEY,CONSUMER_SECRET)
    auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
    api = tweepy.API(auth)
    
    pythonTweets = api.user_timeline(screen_name=search_id_word,count=5)
    
    aa = pythonTweets
    count=0
    resT=""
    while count<len(aa):
        aa1 = json.dumps(aa[count]._json)
        aa2 = json.loads(aa1)
        count = count+1              
        datetime = aa2["created_at"]
        datetime = re.sub('[+]|0000', '', datetime) 
    
        resT +="💙 "+aa2["text"]+"\n"+" -"+datetime+"\n"
    return resT
    
def get_search_word(): # firebase에서 뉴스검색어 가져오기
    res_db = firebasea.get('favorite', None)
    res_db = firebasea.get('/'+res_db, None) # favorite 가수가 가진데이터로 가기
    artist_search_word =  res_db['search_txt'] # 검색어 가져오기
    return artist_search_word

def get_twitter_id(): # firebase에서 트위터계정 아이디 가져오기
    res_db = firebasea.get('favorite', None)
    res_db = firebasea.get('/'+res_db, None) # favorite 가수가 가진데이터로 가기
    twitter_id =  res_db['twitter_id'] # 데이터 가져오기
    return twitter_id

def get_schedule_link(): # 스케줄링크
   res_db = firebasea.get('favorite', None) # favorite에 접근
   res_db = firebasea.get('/'+res_db, None) # 가수가 가진데이터로가기
   link = res_db['link'] 
   return link


def search_news(news_num, news_page,artist_search_word): # 뉴스 검색

    encText = urllib.parse.quote(artist_search_word)
    if news_page == 0:
	    url = "https://openapi.naver.com/v1/search/news?query=" + encText+"&display=5&sort=sim" # json result

    elif news_page == 1:
         url = "https://openapi.naver.com/v1/search/news?query=" + encText+"&display=5&sort=date&start=6" # json result
         
    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id",client_id)
    request.add_header("X-Naver-Client-Secret",client_secret)
    response = urllib.request.urlopen(request)
    rescode = response.getcode()

    output=""
    k = 0
    title = []
    num = 1
    link = []
   
    if(rescode==200):
        response_body = response.read()
        resdata = response_body.decode('utf-8')
        jsonresult = json.loads(resdata)

        for i in jsonresult['items']:
            title_text = i['title']
            link_text = i['link']
            link.append(link_text)

            pat = re.compile("\w+")
            m = pat.match(title_text)
            pattern = re.compile('&quot;|<b>|</b>|\B&quot;\B|&lt;|&gt;')
            title.append(pattern.sub('', title_text))
            output += '<'+str(num)+'>'+title[k]+'\n'
            k += 1
            num += 1
         
    else:
        output="Error Code:"+rescode
        
    if news_num != 0:
        return link[news_num - 1]    
    
    return 'Choose news number what you want to read.'+'\n'+output


def translate(text, source_lang, target_lang):
    """ㅡ
    Returns a string containing translated text, or a request for more info

    Takes text input, source and target language for the text (all strings)
    uses the responses found in translate_response.py as templates
    """
    # Validate the languages provided by the user
    source_lang_code = validate_language(source_lang)
    target_lang_code = validate_language(target_lang)

    # If both languages are invalid or no languages are provided tell the user
    if not source_lang_code and not target_lang_code:
        response = random.choice(_TRANSLATE_UNKNOWN_LANGUAGE)

    # If there is no text but two valid languages ask the user for input
    if not text and source_lang_code and target_lang_code:
        response = random.choice(_TRANSLATE_W_FROM_TO).format(
            lang_from=language_code_dict[source_lang_code],
            lang_to=language_code_dict[target_lang_code])

    # If there is no text but a valid target language ask the user for input
    if not text and target_lang_code:
        response = random.choice(_TRANSLATE_W_TO).format(
            lang=language_code_dict[target_lang_code])

    # If there is no text but a valid source language assume the target
    # language is English if the source language is not English
    if (not text and
        source_lang_code and
        source_lang_code != 'en' and
            not target_lang_code):
        target_lang_code = 'en'

    # If there is no text, no target language and the source language is English
    # ask the user for text
    if (not text and
        source_lang_code and
        source_lang_code == 'en' and
            not target_lang_code):
        response = random.choice(_TRANSLATE_W_FROM).format(
            lang=language_code_dict[source_lang_code])

    # If there is no text and no languages
    if not text and not source_lang_code and not target_lang_code:
        response = random.choice(_TRANSLATE_W)

    # If there is text but no languages
    if text and not source_lang_code and not target_lang_code:
        response = random.choice(_TRANSLATE_INTO_W)

    # If there is text and a valid target language but no source language
    if text and not source_lang_code and target_lang_code:
        response = translate_text(text, source_lang_code, target_lang_code)

    # If there is text and 2 valid languages return the translation
    if text and source_lang_code and target_lang_code:
        response = translate_text(text, source_lang_code, target_lang_code)

    # If no response is generated from the any of the 8 possible combinations
    # (3 booleans = 2^3 = 8 options) return an error to the user
    if not response:
        response = random.choice(_TRANSLATE_ERROR)

    return response

def translate_text(query, source_lang_code, target_lang_code):
    """
    returns translated text or text indicating a translation/network error

    Takes a text to be translated, source language and target language code
    2 letter ISO code found in language_list.py
    """

    try:
        translations = TRANSLATION_SERVICE.translations().list(
            source=source_lang_code,
            target=target_lang_code,
            q=query
        ).execute()
        translation = translations['translations'][0]
        if 'detectedSourceLanguage' in translation.keys():
            source_lang_code = translation['detectedSourceLanguage']
        resp = random.choice(_TRANSLATE_RESULT).format(
            text=translation['translatedText'],
            fromLang=language_code_dict[source_lang_code],
            toLang=language_code_dict[target_lang_code])
    except (HTTPError, URLError, HTTPException):
        resp = random.choice(_TRANSLATE_NETWORK_ERROR)
    except Exception:
        resp = random.choice(_TRANSLATE_ERROR)
    return resp
    
    


def validate_language(language):
    """
    returns 2 letter language code if valid, None if language is invalid

    Uses dictionary in language_list.py to verify language is valid
    """

    try:
        lang_code = language_dict[language]
    except KeyError:
        lang_code = None
    return lang_code

if __name__ == '__main__':
    PORT = 8080

    app.run(
        debug=True,
        port=PORT,
        host='0.0.0.0'
    )
