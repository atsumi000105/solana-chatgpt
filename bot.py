import requests
import time
import json
import tweepy
import yfinance as yf
import os.path
from os import path

######################### GLOBAL DEFINITIONS #########################################

#Fetching config data
conf = open("./config/config.json")
config = json.load(conf)

#List of supported currency
supported_fiat = ["EUR", "USD", "CAD", "JPY", "GPB", "AUD", "CNY", "INR"]

#This value is added to the delay in case MagicEden thinks we are cutting too close into their TPS
#If you feel risky lower this value or make it 0
safety_delay = 0.05
delay = (1/config['TPS']) + safety_delay

client = tweepy.Client(bearer_token=config['twitter_credentials']['bearer_token'],
                       consumer_key=config['twitter_credentials']['consumer_key'],
                       consumer_secret=config['twitter_credentials']['consumer_secret'],
                       access_token=config['twitter_credentials']['access_token'],
                       access_token_secret=config['twitter_credentials']['access_token_secret'])

auth = tweepy.OAuth1UserHandler(config['twitter_credentials']['consumer_key'],
                        config['twitter_credentials']['consumer_secret'],
                        config['twitter_credentials']['access_token'],
                        config['twitter_credentials']['access_token_secret'])

api = tweepy.API(auth)


######################### FUNCTION DEFINITIONS #########################################

#Returns a hasmap of the last buyNow activites from the last config['activities_per_call'] activites
def init_collections():
    #Hasmap: Activity Signature => Activity
    ret = {}
    limit = config['activities_per_call']
    url = "http://api-mainnet.magiceden.dev/v2/collections/" + config['ME_symbol'] + "/activities?offset=0&limit=" + str(limit)
    response = requests.request("GET", url, headers={}, data={}).json()
    for x in response:
        if x['type'] == 'buyNow':
            ret[x['signature']] = x
    return ret

#Fetches the latest Solana price in selected currency
def get_current_price(symbol):
    ticker = yf.Ticker(symbol)
    todays_data = ticker.history(period='1d')
    return todays_data['Close'][0]

#Fetches metadata from mint address using the ME api
def get_meta_from_mint(mint):
    import requests
    url = "http://api-mainnet.magiceden.dev/v2/tokens/" + mint
    response = requests.request("GET", url, headers={}, data={})
    return response.json()

#Converts tweet text to config text
def convert_tweet(sale_data, meta):
    text = config['tweet_text']
    text = text.replace("[-f]", "$" + str(round((get_current_price("SOL-" + config['fiat_currency'])*sale_data["price"]), 2)) + " " + config['fiat_currency'])
    text = text.replace("[-n]", meta['name'])
    text = text.replace("[-p]", str(sale_data["price"]) + " SOL")
    text = text.replace("[-o]", str(meta["owner"]))
    text = text.replace("[-m]", str(meta["mintAddress"]))
    text = text.replace("[-i]", str(meta["image"]))
    text = text.replace("[-s]", str(sale_data["source"]))
    text = text.replace("[-b]", str(sale_data["blockTime"]))
    return text

#Sends a tweet based on sale data and NFT metadata
def send_tweet(api, client, sale_data, meta):
    image = requests.get(meta['image']).content
    with open('./tmp.png', 'wb') as handler:
        handler.write(image)
    mediaID = api.media_upload("tmp.png")
    client.create_tweet(text=convert_tweet(sale_data, meta), media_ids=[mediaID.media_id])



######################### DRIVER CODE #########################################

#Checking valid currency
if config['fiat_currency'] not in supported_fiat:
    print("INVALID FIAT_CURRENCY: CHECK CONFIG")

#Getting initial state of sales
activities = init_collections()

#Getting the last blocktime to ensure no repeat NFTs are tweeted
last_blockTime =  list(activities.values())[0]['blockTime'] if len(activities) > 0 else 0
last_activities = activities

print(f"LISTENING FOR {config['ME_symbol'].upper()} SALES")

#Bot loop
while True:
    #Getting hashmap
    try:
        activities = init_collections()
        time.sleep(delay)
    except:
        continue

    #Checking all activities (by signature, key values)
    for activity in activities.keys():
        #Checking if there is a new activity with a larger blockTime
        if activity not in last_activities.keys() and activities[activity]['blockTime'] >= last_blockTime:
            try:
                meta = get_meta_from_mint(activities[activity]['tokenMint'])
                time.sleep(delay)
                send_tweet(api, client, activities[activity], meta)
                print(f"Tweeting: {convert_tweet(activities[activity], meta)}")
            except:
                print(f"ERROR: with NFT that Sold for {str(activities[activity]['price'])} Not Tweeted")

    last_blockTime =  list(activities.values())[0]['blockTime'] if len(activities) > 0 else 0
    last_activities = dict(activities)
