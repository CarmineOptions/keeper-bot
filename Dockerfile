FROM python:3.9.16-bullseye

WORKDIR /keeper

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY keeper.py expirer.py ./
COPY abi ./abi
COPY bin ./bin
