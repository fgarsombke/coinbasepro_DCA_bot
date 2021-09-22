#!/usr/bin/env python

import argparse
import boto3
import botocore
import binascii
import configparser
import datetime
import json
import sys
import time
from decimal import Decimal

import cbpro
import gspread
from oauth2client.service_account import ServiceAccountCredentials

DEFAULT_ROWS = "1000"
DEFAULT_COLUMNS = "11"
DONE_REASON_FILLED = "filled"

SANDBOX_URL = "https://api-public.sandbox.pro.coinbase.com"

def get_timestamp():
  ts = time.time()
  return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

def add_worksheet(client, google_spreadsheet_key, worksheet_name):
  # add the worksheet
  sheet = client.open_by_key(google_spreadsheet_key).add_worksheet(title=worksheet_name, rows=DEFAULT_ROWS, cols=DEFAULT_COLUMNS)
  # add the header row
  row = ["product_id","specified_funds","funds","fill_fees","filled_size","market_price","side","done_reason","environment","status","created_at"]
  append_res = sheet.append_row(row)
  print(append_res)
  # Freeze the first rpw
  sheet.freeze(1);
  return sheet

"""
    Basic Coinbase Pro DCA buy/sell bot that executes a market order.
    * Market orders can be issued for as little as $5 of value versus limit orders which
        must be 0.001 BTC (e.g. $50 min if btc is at $50k). BTC-denominated market
        orders must be at least 0.0001 BTC.

    This is meant to be run as a crontab to make regular buys/sells on a set schedule.
"""
parser = argparse.ArgumentParser(
    description="""
        This is a basic Coinbase Pro DCA buying/selling bot.

        ex:
            BTC-USD BUY 14 USD          (buy $14 worth of BTC)
            BTC-USD BUY 0.00125 BTC     (buy 0.00125 BTC)
            ETH-BTC SELL 0.00125 BTC    (sell 0.00125 BTC worth of ETH)
            ETH-BTC SELL 0.1 ETH        (sell 0.1 ETH)
    """,
    formatter_class=argparse.RawTextHelpFormatter
)

# Required positional arguments
parser.add_argument('market_name', help="(e.g. BTC-USD, ETH-BTC, etc)")

parser.add_argument('order_side',
                    type=str,
                    choices=["BUY", "SELL"])

parser.add_argument('amount',
                    type=Decimal,
                    help="The quantity to buy or sell in the amount_currency")

parser.add_argument('amount_currency',
                    help="The currency the amount is denominated in")

# Additional options
parser.add_argument('-sandbox',
                    action="store_true",
                    default=False,
                    dest="sandbox_mode",
                    help="Run against sandbox, skips user confirmation prompt")

parser.add_argument('-warn_after',
                    default=300,
                    action="store",
                    type=int,
                    dest="warn_after",
                    help="secs to wait before sending an alert that an order isn't done")

parser.add_argument('-j', '--job',
                    action="store_true",
                    default=False,
                    dest="job_mode",
                    help="Suppresses user confirmation prompt")

parser.add_argument('-c', '--config',
                    default="settings.conf",
                    dest="config_file",
                    help="Override default config file location")

parser.add_argument('-s', '--secret',
                    default="client_secret.json",
                    dest="google_sheet_client_secret",
                    help="Override default google sheet client secret location")

if __name__ == "__main__":
    args = parser.parse_args()
    print(f"{get_timestamp()}: STARTED: {args}")

    market_name = args.market_name
    order_side = args.order_side.lower()
    amount = args.amount
    amount_currency = args.amount_currency

    sandbox_mode = args.sandbox_mode
    job_mode = args.job_mode
    warn_after = args.warn_after

    if not sandbox_mode and not job_mode:
        if sys.version_info[0] < 3:
            # python2.x compatibility
            response = raw_input("Production purchase! Confirm [Y]: ")  # noqa: F821
        else:
            response = input("Production purchase! Confirm [Y]: ")
        if response != 'Y':
            print("Exiting without submitting purchase.")
            exit()

    # Read settings
    config = configparser.ConfigParser()
    config.read(args.config_file)

    config_section = 'production'
    if sandbox_mode:
        config_section = 'sandbox'
    key = config.get(config_section, 'API_KEY')
    passphrase = config.get(config_section, 'PASSPHRASE')
    secret = config.get(config_section, 'SECRET_KEY')
    aws_access_key_id = config.get(config_section, 'AWS_ACCESS_KEY_ID')
    aws_secret_access_key = config.get(config_section, 'AWS_SECRET_ACCESS_KEY')
    sns_topic = config.get(config_section, 'SNS_TOPIC')
    aws_region = config.get(config_section, 'AWS_REGION')
    google_spreadsheet_key = config.get(config_section, 'GOOGLE_SPREADSHEET_KEY')

    # Instantiate public and auth API clients
    auth = cbpro.Auth(key, secret, passphrase)
    # Use the sandbox API (requires a different set of API access credentials)
    messenger = cbpro.Messenger(auth=auth, url=SANDBOX_URL if args.sandbox_mode else None)
    public_client = cbpro.PublicClient(messenger)
    private_client = cbpro.PrivateClient(messenger)

    # Retrieve dict of trading pair info https://docs.pro.coinbase.com/#get-single-product
    try:
        product = public_client.products.get(market_name)
    except binascii.Error as e:
        raise ValueError(f'Did you set your API secrets?') from e

    if product.get('message') == 'NotFound':
        raise KeyError(
            f"{market_name} not found. Available markets: {[prod['id'] for prod in public_client.products.list()]}"
            f""
            f"this can be normal if you are running in sandbox mode.")

    print(product)
    assert product['id'] == market_name
    base_currency = product.get("base_currency")
    quote_currency = product.get("quote_currency")
    base_min_size = Decimal(product.get("base_min_size")).normalize()
    base_increment = Decimal(product.get("base_increment")).normalize()
    quote_increment = Decimal(product.get("quote_increment")).normalize()
    if amount_currency == product.get("quote_currency"):
        amount_currency_is_quote_currency = True
    elif amount_currency == product.get("base_currency"):
        amount_currency_is_quote_currency = False
    else:
        raise Exception(f"amount_currency {amount_currency} not in market {market_name}")
    print(json.dumps(product, indent=2))

    print(f"base_min_size: {base_min_size}")
    print(f"quote_increment: {quote_increment}")

    # Prep boto SNS client for email notifications
    if sns_topic:
      sns = boto3.client(
         "sns",
         aws_access_key_id=aws_access_key_id,
         aws_secret_access_key=aws_secret_access_key,
         region_name=aws_region
      )

    model = cbpro.PrivateModel()
    # construct order request
    if amount_currency_is_quote_currency:
        request = model.orders.market(side=order_side, product_id=market_name,
                                      funds=float(amount.quantize(quote_increment))
                                      )
    else:
        request = model.orders.market(side=order_side, product_id=market_name,
                                      size=float(amount.quantize(base_increment))
                                      )

    # make order
    response = private_client.orders.post(request)

    print(json.dumps(response, sort_keys=True, indent=4))

    if "message" in response:
        # Something went wrong if there's a 'message' field in response
        if sns:
          sns.publish(
             TargetArn=sns_topic,
             Subject=f"Could not place {market_name} {order_side} order",
             Message=json.dumps(result, sort_keys=True, indent=4)
          )
        exit()

    if response and "status" in response and response["status"] == "rejected":
        print(f"{get_timestamp()}: {market_name} Order rejected")

    order = response
    order_id = response["id"]
    print(f"order_id: {order_id}")

    '''
        Wait to see if the order was fulfilled.
    '''
    wait_time = 5
    total_wait_time = 0
    while "status" in order and \
            (order["status"] == "pending" or order["status"] == "open"):
        if total_wait_time > warn_after:
            if sns:
              sns.publish(
                 TargetArn=sns_topic,
                 Subject=f"{market_name} {order_side} order of {amount} {amount_currency} OPEN/UNFILLED",
                 Message=json.dumps(order, sort_keys=True, indent=4)
              )
            exit()

        print(
            f"{get_timestamp()}: Order {order_id} still {order['status']}. Sleeping for {wait_time} (total {total_wait_time})")
        time.sleep(wait_time)
        total_wait_time += wait_time
        order = private_client.orders.get(order_id)
        # print(json.dumps(order, sort_keys=True, indent=4))

        if "message" in order and order["message"] == "NotFound":
            # Most likely the order was manually cancelled in the UI
            if sns:
              sns.publish(
                 TargetArn=sns_topic,
                 Subject=f"{market_name} {order_side} order of {amount} {amount_currency} CANCELLED",
                 Message=json.dumps(result, sort_keys=True, indent=4)
              )
            exit()

    # Order status is no longer pending!
    print(json.dumps(order, indent=2))
    done_reason = order["done_reason"]
    if done_reason != DONE_REASON_FILLED:
      print('Coinbase Pro order failed due to done reason ' + done_reason)
      # send email and fast fail
      if sns:
       try:
        sns.publish(
           TargetArn=sns_topic,
           Subject='Coinbase Pro order failed due to done reason ' + done_reason,
           Message=json.dumps(order, sort_keys=True, indent=4)
          )
       except botocore.exceptions.ClientError as e:
         print("Unexpected error: %s" % e)
      exit()

    market_price = (Decimal(order["executed_value"]) / Decimal(order["filled_size"])).quantize(quote_increment)

    subject = f"{market_name} {order_side} order of {amount} {amount_currency} {order['status']} @ {market_price} {quote_currency}"
    print(subject)
    if sns:
      try:
        sns.publish(
         TargetArn=sns_topic,
         Subject=subject,
         Message=json.dumps(order, sort_keys=True, indent=4)
        )
      except botocore.exceptions.ClientError as e:
        print("Unexpected error: %s" % e)
   
    if google_spreadsheet_key:
      print('writing to google spreadsheet') 
      # use creds to create a client to interact with the Google Drive API
      DEFAULT_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
      ]
      try: 
        creds = ServiceAccountCredentials.from_json_keyfile_name(args.google_sheet_client_secret, DEFAULT_SCOPES)
        client = gspread.authorize(creds)
        # find all of the worksheets and make sure there is one with the market_name (buy/pair)
        # if we find one append, if we do not then create a new worksheet with the buy/pair
        worksheet_list = client.open_by_key(google_spreadsheet_key).worksheets()
        # iterate through the worksheets and try to find market_name
        match_found = False
        if len(worksheet_list):
          for worksheet in worksheet_list:
            print(f"worksheet.title {worksheet.title}, market_name {market_name}")
            if worksheet.title == market_name:
              match_found = True

        if match_found:
          print('worksheet match found, appending row')
          sheet = worksheet
        else:
          print('worksheet match not found, creating worksheet')
          sheet = add_worksheet(client,google_spreadsheet_key, market_name)

        row = [order["product_id"],order["specified_funds"],order["funds"],order["fill_fees"],order["filled_size"],market_price,order["side"],order["done_reason"],config_section,order["status"],order["created_at"]]
        append_res = sheet.append_row(row)
        print(append_res)
      except Exception as e:
        print("Unexpected error: %s" % e)