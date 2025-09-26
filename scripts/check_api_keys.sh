#!/usr/bin/env bash
set -euo pipefail

if [[ -f ".env" ]]; then
  if grep -q "EXCHANGE_API_KEY=" .env && grep -q "EXCHANGE_API_SECRET=" .env; then
    echo "✅ .env has API keys."
    exit 0
  fi
fi

if [[ "$OSTYPE" == "darwin"* ]]; then
  if security find-generic-password -a "default" -s "crypto-bot-exchange-key" >/dev/null 2>&1 \
  && security find-generic-password -a "default" -s "crypto-bot-exchange-secret" >/dev/null 2>&1; then
    echo "✅ Keys found in Keychain."
    exit 0
  fi
fi

echo "❌ Missing API keys. Run: make setup"
exit 1
