#!/bin/sh

set_checkpoint_mainnet () {
  python3 ./keeper.py \
    --net mainnet \
    -ca $PRAGMA_CONTRACT_ADDRESS \
    -wa $MAINNET_WALLET_ADDRESS \
    --pub_key $MAINNET_PRIVATE_KEY \
    --priv_key $MAINNET_PRIVATE_KEY \
    --function_name set_checkpoint \
    --function_arguments "$1"\
    --proxy
}

set_checkpoints_testnet () {
  python3 ./keeper.py \
    --net testnet \
    -wa $TESTNET_WALLET_ADDRESS \
    --pub_key $TESTNET_PRIVATE_KEY \
    --priv_key $TESTNET_PRIVATE_KEY \
    -ca $AMM_TESTNET_ADDRESS \
    --function_name set_pragma_required_checkpoints
}


set_checkpoint_mainnet "[19514442401534788, 0]"
set_checkpoint_mainnet "[6148332971638477636, 0]"
set_checkpoints_testnet
