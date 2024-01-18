#!/bin/sh

set_checkpoints_mainnet () {
  python3 ./keeper.py \
    --node_url $MAINNET_RPC \
    --net mainnet \
    -wa $MAINNET_WALLET_ADDRESS \
    --pub_key $MAINNET_PRIVATE_KEY \
    --priv_key $MAINNET_PRIVATE_KEY \
    -ca $AMM_MAINNET_ADDRESS \
    --function_name set_pragma_required_checkpoints
}


# set_checkpoints_testnet () {
#   python3 ./keeper.py \
#     --node_url $TESTNET_RPC \
#     --net testnet \
#     -wa $TESTNET_WALLET_ADDRESS \
#     --pub_key $TESTNET_PRIVATE_KEY \
#     --priv_key $TESTNET_PRIVATE_KEY \
#     -ca $AMM_MAINNET_ADDRESS \
#     --function_name set_pragma_required_checkpoints
# }


set_checkpoints_mainnet 
# set_checkpoints_testnet
