import json
from dca_bot import executePurchase
import os
from decimal import Decimal

def buy(event, context):
    args = {
        'order_side': "BUY",
        'sandbox_mode': os.environ['ENV'] != 'prod',
        'warn_after': 300,
        'job_mode': True,
        'config_file': "settings-local.conf",
        'google_sheet_client_secret': f"{os.environ['ENV']}_client_secret.json"
    }
    print ("event json input", json.dumps(event))
    # Iterate through the purchases
    for item in event:
      print ("executing purchase for market name ", item['market_name'])
      args['market_name'] = item['market_name']
      args['amount'] = Decimal(item['amount'])
      args['amount_currency'] = item['amount_currency']
      btc_response = executePurchase(args)
      print("executed purchase response", json.dumps(btc_response))

    response = {
        "statusCode": 200
    }

    return response