from typing import List, Any
import time
import asyncio
import requests
import os
import json
from dataclasses import dataclass
import traceback

from starknet_py.contract import Contract
from starknet_py.net.signer.stark_curve_signer import KeyPair
from starknet_py.net.client_models import TransactionStatus
from starknet_py.net.account.account import Account
from starknet_py.net.gateway_client import GatewayClient
from starknet_py.net.models.chains import StarknetChainId


MAX_FEE = int(1e16)
OPTIONS_ENDPOINT = 'https://api.carmine.finance/api/v1/mainnet/option-volatility'
AMM_ADDR = 0x076dbabc4293db346b0a56b29b6ea9fe18e93742c73f12348c8747ecfc1050aa  # mainnet
CLIENT = GatewayClient(net="mainnet")
CHAIN = StarknetChainId.MAINNET


@dataclass
class EnVars:
    private_key: int
    public_key: int
    address: str
    tg_key: str
    tg_chat_id: str


def parse_envs() -> EnVars:
    PRIVATE_KEY = os.getenv('PRIVATE_KEY')
    PUBLIC_KEY = os.getenv('PUBLIC_KEY')
    ADDRESS = os.getenv('WALLET_ADDRESS')
    TG_KEY = os.getenv("TG_KEY")
    TG_CHAT_ID = os.getenv("TG_CHAT_ID")

    if PRIVATE_KEY == None:
        raise ValueError("Missing PRIVATE_KEY ENV")

    if PUBLIC_KEY == None:
        raise ValueError("Missing PUBLIC_KEY ENV")

    if ADDRESS == None:
        raise ValueError("Missing ADDRESS ENV")

    if TG_KEY == None:
        raise ValueError("Missing TG_KEY ENV")

    if TG_CHAT_ID == None:
        raise ValueError("Missing TG_CHAT_ID ENV")

    return EnVars(
        private_key=int(PRIVATE_KEY, 16),
        public_key=int(PUBLIC_KEY, 16),
        address=ADDRESS,
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


async def main():

    try:

        enVars = parse_envs()

        # Fetch all options from API and create list of them with latest pool position in given option
        # pool position is stored under key volatilities
        options = requests.get(OPTIONS_ENDPOINT)
        options_with_position = []
        for option in options.json()['data']:
            options_with_position.append({
                'option_side': option['option_side'],
                'maturity': option['maturity'],
                'strike_price': option['strike_price'],
                'lp_address': option['lp_address'],
                **sorted(option['volatilities'], key=lambda x: x['block_number'])[-1]
            })

        # Get only options that are past their maturity
        now = int(time.time())
        options_past_maturity = [
            option for option in options_with_position if option['maturity'] < now
        ]

        # Get only options that are past their maturity and with pool position > 0
        options_past_maturity_non_zero_position = [
            option for option in options_past_maturity if int(option['option_position'] or '0x0', 16) > 0
        ]

        # Create account instance
        account = Account(
            client=CLIENT,
            address=enVars.address,
            key_pair=KeyPair(private_key=enVars.private_key,
                             public_key=enVars.public_key),
            chain=CHAIN
        )

        # Load abi
        with open("abi/amm_abi.json") as f:
            abi = json.load(f)

        # Create AMM contract instance
        contract = Contract(
            address=AMM_ADDR,
            abi=abi,
            provider=account,
        )

        # Prepare calls
        calls = [
            contract.functions['expire_option_token_for_pool'].prepare(
                lptoken_address=int(option['lp_address'], 16),
                option_side=option['option_side'],
                strike_price=int(option['strike_price'], 16),
                maturity=option['maturity']
            )
            for option in options_past_maturity_non_zero_position
        ]

        tracebacks = []
        # Execute calls - try 3 times
        for i in range(3):
            response = await account.execute(calls=calls, max_fee=MAX_FEE)
            try:
                await account.client.wait_for_tx(response.transaction_hash)
                tx_status = await account.client.get_transaction_receipt(response.transaction_hash)

                if (tx_status.status == TransactionStatus.ACCEPTED_ON_L1) or (tx_status.status == TransactionStatus.ACCEPTED_ON_L2):
                    alert(f"Expiration successfull: {tx_status}: ".upper(
                    ), enVars.tg_chat_id, enVars.tg_key)
                    for call in calls:
                        alert(f"{call}", enVars.tg_chat_id, enVars.tg_key)
                    break
                else:
                    tracebacks.append(tx_status)
                    continue

            except Exception as err:
                tracebacks.append("".join(traceback.format_exception(
                    err, value=err, tb=err.__traceback__)))
                continue

        if tracebacks:
            alert(f'Expiration received {len(tracebacks)} errors:(('.upper(
            ), enVars.tg_chat_id, enVars.tg_key)
            for errmsg in tracebacks:
                alert(errmsg, enVars.tg_chat_id, enVars.tg_key)

    except Exception as err:
        err_msg = "".join(traceback.format_exception(
            err, value=err, tb=err.__traceback__))
        alert(f"EXPIRATION COMPLETE FAIL: {err_msg}",
              enVars.tg_chat_id, enVars.tg_key)

if __name__ == '__main__':
    asyncio.run(main())
