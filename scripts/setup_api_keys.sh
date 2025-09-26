#!/usr/bin/env bash
set -euo pipefail

if [[ "$OSTYPE" == "darwin"* ]]; then
  read -p "Exchange API KEY: " EXCHANGE_API_KEY
  read -p "Exchange API SECRET: " EXCHANGE_API_SECRET

  security add-generic-password -a "default" -s "crypto-bot-exchange-key" -U -w "$EXCHANGE_API_KEY"
  security add-generic-password -a "default" -s "crypto-bot-exchange-secret" -U -w "$EXCHANGE_API_SECRET"
  echo "✅ Keys saved to macOS Keychain."

  # Also write a local .env for Docker Compose
  echo "EXCHANGE_API_KEY=$EXCHANGE_API_KEY" > .env
  echo "EXCHANGE_API_SECRET=$EXCHANGE_API_SECRET" >> .env
  echo "TRADING_MODE=paper" >> .env
  echo "EXCHANGE_ID=coinbasepro" >> .env
  echo "SYMBOL=BTC/USDT" >> .env
  echo "TIMEFRAME=1h" >> .env
  echo "TRADE_QTY=0.001" >> .env
  echo "✅ .env created."
else
  echo "Non-macOS: creating .env"
  read -p "Exchange API KEY: " EXCHANGE_API_KEY
  read -p "Exchange API SECRET: " EXCHANGE_API_SECRET
  echo "EXCHANGE_API_KEY=$EXCHANGE_API_KEY" > .env
  echo "EXCHANGE_API_SECRET=$EXCHANGE_API_SECRET" >> .env
  echo "TRADING_MODE=paper" >> .env
  echo "EXCHANGE_ID=coinbasepro" >> .env
  echo "SYMBOL=BTC/USDT" >> .env
  echo "TIMEFRAME=1h" >> .env
  echo "TRADE_QTY=0.001" >> .env
  echo "✅ .env created."
fi
