from typing import List, Any
import argparse
import logging
import time
import asyncio
import requests
import os
from dataclasses import dataclass
import traceback

from starknet_py.contract import Contract
from starknet_py.net.signer.stark_curve_signer import KeyPair
from starknet_py.net.account.account import Account
from starknet_py.net.full_node_client import FullNodeClient
from starknet_py.net.models.chains import StarknetChainId
from starknet_py.net.client_models import TransactionExecutionStatus

from starknet_py.transaction_errors import (
    TransactionRejectedError,
    TransactionRevertedError,
)

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


def alert(msg: str, chat_id: str, api_key: str):
    # https://api.telegram.org/bot[BOT_API_KEY]/sendMessage?chat_id=[MY_CHANNEL_NAME]&text=[MY_MESSAGE_TEXT]
    params = {
        'chat_id': chat_id,
        'text': msg,
    }
    res = requests.get("https://api.telegram.org/bot" +
                       api_key + "/sendMessage", params=params)
    res.raise_for_status()

def setup_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='Carmine Expirer Bot',
        description='Expires Options on Carmine Options AMM',
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
        '--amm_address', type=str
    )

    return parser

def get_chain(args: argparse.Namespace) -> StarknetChainId:
    if args.net not in SUPPORTED_NETWORKS:
        raise ValueError(
            f'Unknown network, expected one of {SUPPORTED_NETWORKS}, got: {args.net}'
        )

    return StarknetChainId.MAINNET if 'mainnet' in args.node_url else StarknetChainId.TESTNET


async def main():
    
    # Logging setup
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%d-%b-%y %H:%M:%S',
        level=logging.INFO
    )

    # Get TG related ENVs
    enVars = parse_envs()
    
    # Parser
    parser = setup_parser()
    args = parser.parse_args()

    # Select chain
    chain = get_chain(args)
    
    # Log Network, chain
    logging.info(f"Selected network: {args.net}")
    logging.info(f"Selected chain: {chain}")

    # Setup client and account for interacting with chain
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

    # Create AMM contract instance from address
    contract = await Contract.from_address(
        address=args.amm_address,
        provider=account
    )

    # Get all lptokens and log them
    try: 
        lptokens = (await contract.functions['get_all_lptoken_addresses'].call())[0]
        logging.info(f"Fetched LPTokens: {lptokens}")
    except Exception as err:
        # Log the error if there is some
        err_msg = "".join(traceback.format_exception( err, value=err, tb=err.__traceback__))
        logging.error(f"Failed when fetching LPTokens: {err_msg}")
        
        # Send alert to Telegram
        alert(f"Expirer failed when fetching lptokens", enVars.tg_chat_id, enVars.tg_key)
        exit(420)
    
    for lptoken in lptokens:

        logging.info(f"Expirying options for lptoken: {lptoken}")

        # Fetch all the options for given lptoken
        try:
            opts = (await contract.functions['get_all_options'].call(lptoken))[0]
        except Exception as err:
            # Log the error if there is some
            err_msg = "".join(traceback.format_exception( err, value=err, tb=err.__traceback__))
            logging.error(f"Failed fetching options for lptoken: {lptoken}, errmsg: {err_msg}")

            # Send alert to Telegram
            alert(f"Expirer failed when fetching options for lptoken: {lptoken}", enVars.tg_chat_id, enVars.tg_key)
            continue

        relevant_opts = [
            i for i in opts 
            if i['maturity'] < time.time()  # Get expired options
            and i['maturity'] > (time.time() - 7*86400) # Limit to expired in last 7 days
        ]

        if len(relevant_opts) == 0:
            
            logging.info(f"No relevant options found for lptoken: {lptoken}")

            # Send alert to Telegram
            alert(f"Expirer found no relevant options for lptoken: {lptoken}", enVars.tg_chat_id, enVars.tg_key)
            
            continue
            
        
        try:
            calls = [
                contract.functions['expire_option_token_for_pool'].prepare(
                    lptoken_address = lptokens[0],
                    option_side = option['option_side'],
                    strike_price = option['strike_price'],
                    maturity = option['maturity']
                )
                for option in relevant_opts
            ]
            response = await account.execute(calls=calls, max_fee=MAX_FEE)
            logging.info(f"Executed calls for lptoken: {lptoken}")
        except Exception as err: 
            err_msg = "".join(traceback.format_exception( err, value=err, tb=err.__traceback__))
            logging.error(f"Failed preparing and executing calls for lptoken {lptoken}, errmsg: {err_msg}")

            alert(f"Expirer failed to prepare and execute for lptoken: {lptoken}", enVars.tg_chat_id, enVars.tg_key)
            continue

        
        try: 
            await account.client.wait_for_tx(response.transaction_hash)

        except TransactionRevertedError as err:
            err_msg = "".join(traceback.format_exception( err, value=err, tb=err.__traceback__))
            logging.error(f"Expiry tx reverted for lptoken: {lptoken}, errmsg: {err_msg}")

            alert(f"Expiry tx reverted for lptoken: {lptoken}", enVars.tg_chat_id, enVars.tg_key)
            continue
        
        except TransactionRejectedError as err:
            err_msg = "".join(traceback.format_exception( err, value=err, tb=err.__traceback__))
            logging.error(f"Expiry tx rejected for lptoken: {lptoken}, errmsg: {err_msg}")

            alert(f"Expiry tx rejected for lptoken: {lptoken}", enVars.tg_chat_id, enVars.tg_key)
            continue
        
        except Exception as err:
            err_msg = "".join(traceback.format_exception( err, value=err, tb=err.__traceback__))
            logging.error(f"Unable to wait for tx of lptoken: {lptoken}, errmsg: {err_msg}")
            # In this case the tx could still be alright, so proceed


        tx_status = await account.client.get_transaction_receipt(response.transaction_hash)

        if tx_status.execution_status == TransactionExecutionStatus.SUCCEEDED:
            logging.info(f"Successfully expired options for lptoken: {lptoken}")
            alert(f"Successfully expired options for lptoken: {lptoken}", enVars.tg_chat_id, enVars.tg_key)

        else: 
            logging.error(f"Failed to expire options for lptoken: {lptoken}, status: {tx_status}")
            alert(f"Failed to expire options for lptoken: {lptoken}", enVars.tg_chat_id, enVars.tg_key)

    time.sleep(10)

if __name__ == '__main__':
    asyncio.run(main())
