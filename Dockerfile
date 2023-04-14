FROM python:3.9.16-bullseye

WORKDIR /keeper

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY keeper.py Oracle_abi.json ./
COPY bin ./bin
