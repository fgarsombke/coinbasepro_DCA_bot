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

    # Execute purchase  
    args['market_name'] = os.environ['MARKET_NAME']
    args['amount'] = Decimal(os.environ['AMOUNT'])
    args['amount_currency'] = os.environ['AMOUNT_CURRENCY']

    btc_response = executePurchase(args)

    response = {
        "statusCode": 200,
        "body": json.dumps(btc_response)
    }

    return response