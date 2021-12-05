#!/usr/bin/env bash
# deploy.sh
mkdir package
pip3 install -r requirements.txt --target=./package
cp handler.py package/
cp dca_bot.py package/
cp settings-local.conf package/
cp sandbox_client_secret.json package/
$(cd package; zip -r ../package.zip .)
serverless deploy --config serverless-BTC.yml --verbose --stage sandbox