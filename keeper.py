
import requests
import asyncio
import json
import os
import argparse
import logging
from typing import List
from dataclasses import dataclass
import traceback
import time

from starknet_py.contract import Contract
from starknet_py.net.signer.stark_curve_signer import KeyPair
from starknet_py.net.account.account import Account
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.models.chains import StarknetChainId
from starknet_py.net.client_models import TransactionExecutionStatus


MAX_FEE = int(1e16)
SUPPORTED_NETWORKS = ['testnet', 'mainnet']


@dataclass
class EnVars:
    tg_key: str
    tg_chat_id: str


def parse_envs() -> EnVars:
    TG_KEY = os.getenv("TG_KEY")
    TG_CHAT_ID = os.getenv("TG_CHAT_ID")

    if TG_KEY == None:
        raise ValueError("Missing TG_KEY ENV")

    if TG_CHAT_ID == None:
        raise ValueError("Missing TG_CHAT_ID ENV")

    return EnVars(
        tg_key=TG_KEY,
        tg_chat_id=TG_CHAT_ID
    )


def setup_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='Starknet Keeper bot',
        description='Periodically calls predefined function on Starknet',
    )

    parser.add_argument(
        '--net', type=str
    )
    parser.add_argument(
        '--node_url', type=str
    )

    parser.add_argument(
        '--wallet_address', '-wa', type=str
    )
    parser.add_argument(
        '--pub_key', type=str
    )
    parser.add_argument(
        '--priv_key', type=str
    )
    
    parser.add_argument(
        '--contract_address','-ca', type=str
    )
    parser.add_argument(
        '--function_name', '-fa', type=str
    )
    parser.add_argument(
        '--function_arguments', default=[], type=json.loads
    )

    parser.add_argument(
        '--proxy', action = 'store_true'
    )

    return parser


def alert(msg: str, chat_id: str, api_key: str):
    # https://api.telegram.org/bot[BOT_API_KEY]/sendMessage?chat_id=[MY_CHANNEL_NAME]&text=[MY_MESSAGE_TEXT]

    params = {
        'chat_id': chat_id,
        'text': msg,
    }
    res = requests.get("https://api.telegram.org/bot" +
                       api_key + "/sendMessage", params=params)
    res.raise_for_status()


def get_chain(args: argparse.Namespace) -> StarknetChainId:
    if args.net not in SUPPORTED_NETWORKS:
        raise ValueError(
            f'Unknown network, expected one of {SUPPORTED_NETWORKS}, got: {args.net}'
        )

    return StarknetChainId.MAINNET if 'mainnet' in args.node_url else StarknetChainId.TESTNET


async def main():

    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%d-%b-%y %H:%M:%S',
        level=logging.INFO
    )
    enVars = parse_envs()
    try:
        parser = setup_parser()
        args = parser.parse_args()

        chain = get_chain(args)

        logging.info(f"Selected network: {args.net}")
        logging.info(f"Selected chain: {chain}")

        client = FullNodeClient(node_url=args.node_url)
        account = Account(
            client=client,
            address=args.wallet_address,
            key_pair=KeyPair(
                private_key=int(args.priv_key, 16),
                public_key=int(args.pub_key, 16)
            ),
            chain=chain,
        )

        contract = await Contract.from_address(
            address=args.contract_address,
            provider=account,
            proxy_config=args.proxy
        )

        # Invoke function
        call = contract.functions[args.function_name].prepare(
            *args.function_arguments,
        )

        logging.info(f"Executing call: {call}")

        tracebacks = []

        for _ in range(3):
            response = await account.execute(calls=call, max_fee=MAX_FEE)
            logging.info(f"Sent transaction: {response}")
            try:
                await account.client.wait_for_tx(response.transaction_hash)
                break
            except Exception as err:
                logging.error(f"Transaction Rejected: {err}")
                tracebacks.append("".join(traceback.format_exception(
                    err, value=err, tb=err.__traceback__)))
                continue

        time.sleep(10)

        tx_status = await account.client.get_transaction_receipt(response.transaction_hash)

        if tx_status.execution_status == TransactionExecutionStatus.SUCCEEDED:
            logging.info(f"Tx SUCCESSFULL, receipt: {tx_status}")
        else:
            tracebacks.append(tx_status)
            logging.error(f"Tx NOT ACCEPTED: {tx_status}")

        if tracebacks:
            alert(f"Received {len(tracebacks)} errors:(( - \n {tracebacks}",
                  enVars.tg_chat_id, enVars.tg_key)
        else:
            alert(
                f"Update successfull: {tx_status} \n {call}", enVars.tg_chat_id, enVars.tg_key)

    except Exception as err:
        err_msg = "".join(traceback.format_exception(
            err, value=err, tb=err.__traceback__))
        logging.error(f"Execution failed: {err},\n {err_msg}")
        alert(f"COMPLETE FAIL: {err_msg}", enVars.tg_chat_id, enVars.tg_key)

if __name__ == '__main__':
    asyncio.run(main())
