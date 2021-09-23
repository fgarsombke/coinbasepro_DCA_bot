# dca_bot
A basic Coinbase Pro buying bot that completes trades in any of their available market pairings

Relies on https://github.com/danpaquin/coinbasepro-python.git.

Originally forked from https://github.com/kdmukai/gdax_bot. All credit due there. This cut is a cleanup with added functionality.

## Dollar Cost Averaging
Rather than trying to achieve the perfect timing for when to execute a purchase just set up your investment on a regular schedule. Buy X amount every Y days. Sometimes the market will be up, sometimes down. But over time your cache will more closely reflect the average market price with volatile peaks and valleys averaged out.

This approach is common for retirement accounts; you invest a fixed amount into your 401(k) every month and trust that the market trend will be overall up over time.

## Technical Details
### Basic approach
dca_bot submits a market price order for every coin pair.

### Setup
#### Create a Coinbase account

#### Install pip modules
```
pip install -r requirements.txt
```

#### Create Coinbase Pro API key
Try this out on Coinbase Pro's sandbox first. The sandbox is a test environment that is not connected to your actual fiat or crypto balances.

Log into your Coinbase/Coinbase Pro account in their test sandbox:
https://public.sandbox.pro.coinbase.com/

Find and follow existing guides for creating an API key. Only grant the "Trade" permission. Note the passphrase, the new API key, and API key's secret.

While you're in the sandbox UI, fund your fiat account by transferring from the absurd fake balance that sits in the linked Coinbase account (remember, this is all just fake test data; no real money or crypto goes through the sandbox).

#### Customize settings
Update `settings.conf.example` with your API key info in the "sandbox" section. I recommend saving your version as `settings-local.conf` as that is already in the `.gitignore` so you don't have to worry about committing your sensitive info to your forked repo.

#### (Optional) Create an AWS Simple Notification System topic
This is out of scope for this document, but generate a set of AWS access keys and a new SNS topic to enable the bot to send email reports.

Set these values in the `settings-local.conf` file if the SNS topic was created
```
SNS_TOPIC = arn:aws:sns:us-east-1:account_id:topicname
AWS_ACCESS_KEY_ID = access_key
AWS_SECRET_ACCESS_KEY = secret_key
AWS_REGION = us-east-1
```
#### (Optional) Create a Google Spreadsheet
To programmatically access your spreadsheet, you’ll need to create a service account and OAuth2 credentials from the Google API Console.
* Create a new spreadsheet in your Google Drive account. The DCA Bot will automatically create worksheets for each market name (i.e. BTC-USD, ETH-USD)
* Go to the Google APIs Console (https://console.developers.google.com/)
* Create a new project
  * Enable the Google Drive API and Google Sheets API
  * Create Credentials --> Service Account
    * Name the service account and grant it a Project Role of Editor
    * Add Key --> Create New Key
    * Download the JSON file and name it client_secret.json and put into your working script directory 
  * Find the client_email inside client_secret.json file. In your spreadsheet, click the "Share" button at the top right and share to the client_email with Editor privledges

* Set this value in the `settings-local.conf` with the key of the Google spreadsheet that was created

`GOOGLE_SPREADSHEET_KEY=key_of_google_spreadsheet (i.e. 1KArbyA-s2IJwxP6zqazZ3IzkLNFHBFzek9HLziB6ITw`

#### Try a basic test run
Run against the Coinbase Pro sandbox by including the `-sandbox` flag. Remember that the sandbox is just test data.

The sandbox only supports BTC trading.

Try a basic buy of $100 USD worth of BTC:

`python3 dca_bot.py BTC-USD BUY 100 USD -sandbox -c settings-local.conf -s client_secret.json (optional, for google spreadsheet only)`

Check the sandbox UI and you'll see your order listed.

### Usage
Run ```python3 dca_bot.py -h``` for usage information:

```
usage: dca_bot.py [-h] [-sandbox] [-warn_after WARN_AFTER] [-j]
                   [-c CONFIG_FILE]
                   market_name {BUY,SELL} amount amount_currency

        This is a basic Coinbase Pro DCA buying/selling bot.

        ex:
            BTC-USD BUY 14 USD          (buy $14 worth of BTC)
            BTC-USD BUY 0.00125 BTC     (buy 0.00125 BTC)
            ETH-BTC SELL 0.00125 BTC    (sell 0.00125 BTC worth of ETH)
            ETH-BTC SELL 0.1 ETH        (sell 0.1 ETH)
    

positional arguments:
  market_name           (e.g. BTC-USD, ETH-BTC, etc)
  {BUY,SELL}
  amount                The quantity to buy or sell in the amount_currency
  amount_currency       The currency the amount is denominated in

optional arguments:
  -h, --help            show this help message and exit
  -sandbox              Run against sandbox, skips user confirmation prompt
  -warn_after WARN_AFTER
                        secs to wait before sending an alert that an order isn't done
  -j, --job             Suppresses user confirmation prompt
  -c CONFIG_FILE, --config CONFIG_FILE
                        Override default config file location
  -s Google spreadsheet client secret file, --secret
                        Override default google spreadsheet client secret file location                        
```
### Scheduling your recurring buys
This is meant to be run as a crontab to make regular purchases on a set schedule. Here are some example cron jobs:

$50 USD of ETH every Monday at 17:23:
```
23 17 * * 1 /your/virtualenv/path/bin/python3 -u /your/dca_bot/path/src/dca_bot.py -j ETH-USD BUY 50.00 USD -c /your/settings/path/your_settings_file.conf -s /your/settings/path/client_secret.json (optional) >> /your/cron/log/path/cron.log
```
*The ```-u``` option makes python output ```stdout``` and ```stderr``` unbuffered so that you can watch the progress in real time by running ```tail -f cron.log```.*

#### Cron examples
Edit the crontab:
```
crontab -e
```
View the current crontab:
```
crontab -l
```
