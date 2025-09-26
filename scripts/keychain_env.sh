#!/usr/bin/env bash
set -euo pipefail

if [[ -f ".env" ]]; then
  export $(grep -v '^#' .env | xargs || true)
fi

if [[ "$OSTYPE" == "darwin"* ]]; then
  KEY=$(security find-generic-password -a "default" -s "crypto-bot-exchange-key" -w 2>/dev/null || true)
  SEC=$(security find-generic-password -a "default" -s "crypto-bot-exchange-secret" -w 2>/dev/null || true)
  if [[ -n "${KEY:-}" && -n "${SEC:-}" ]]; then
    export EXCHANGE_API_KEY="$KEY"
    export EXCHANGE_API_SECRET="$SEC"
    # Refresh .env each time
    {
      echo "EXCHANGE_API_KEY=$EXCHANGE_API_KEY"
      echo "EXCHANGE_API_SECRET=$EXCHANGE_API_SECRET"
      echo "TRADING_MODE=${TRADING_MODE:-paper}"
      echo "EXCHANGE_ID=${EXCHANGE_ID:-coinbasepro}"
      echo "SYMBOL=${SYMBOL:-BTC/USDT}"
      echo "TIMEFRAME=${TIMEFRAME:-1h}"
      echo "TRADE_QTY=${TRADE_QTY:-0.001}"
    } > .env
    echo "✅ Keys loaded from Keychain and written to .env"
  fi
fi

# Execute the rest of the command line
exec "$@"
