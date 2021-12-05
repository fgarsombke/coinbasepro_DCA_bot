import json
from dca_bot import executePurchase
import os
from decimal import Decimal

def buy(event, context):
    # python3 dca_bot.py BTC-USD BUY 100 USD -sandbox -c settings-local.conf -s client_secret.json
    # parser.add_argument(market_name, help="(e.g. BTC-USD, ETH-BTC, etc)")

    # parser.add_argument('amount',
    #                     type=Decimal,
    #                     help="The quantity to buy or sell in the amount_currency")

    # parser.add_argument('amount_currency',
    #                     help="The currency the amount is denominated in")

    args = {
        'order_side': "BUY",
        'sandbox_mode': os.environ['ENV'] != 'prod',
        'warn_after': 300,
        'job_mode': True,
        'config_file': "settings-local.conf",
        'google_sheet_client_secret': f"{os.environ['ENV']}_client_secret.json"
    }

    # Execute BTC purchase  
    print('!!!!!!!!')
    print(os.environ['MARKET_NAME'])
    args['market_name'] = os.environ['MARKET_NAME']
    args['amount'] = Decimal(os.environ['AMOUNT'])
    args['amount_currency'] = os.environ['AMOUNT_CURRENCY']

    btc_response = executePurchase(args)

    response = {
        "statusCode": 200,
        "body": json.dumps(btc_response)
    }

    return response