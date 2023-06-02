#!/bin/sh

set_checkpoint () {
  python ./keeper.py --net mainnet -wa $WALLET_ADDRESS --contract_address $CONTRACT_ADDRESS --abi_path ./abi/oracle_abi.json --function_name set_checkpoint --function_arguments "$1"
}

set_checkpoint "[19514442401534788, 0]"
set_checkpoint "[6148332971638477636, 0]"
