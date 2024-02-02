#!/bin/sh

expire_options_mainnet() {
 python3 ./expirer.py \
  --node_url $MAINNET_RPC \
  --net mainnet \
  -wa $MAINNET_WALLET_ADDRESS \
  --pub_key $MAINNET_PRIVATE_KEY \
  --priv_key $MAINNET_PRIVATE_KEY \
  --amm_address $AMM_MAINNET_ADDRESS
}

expire_options_mainnet