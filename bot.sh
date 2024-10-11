#!/bin/bash

# Get today's date in YYYYMMDD format
DATE=$(date +%Y%m%d)
cd /home/colin/workspace/BinanceTrader
/home/colin/anaconda3/envs/BinanceTrader/bin/python main.py>>bot-$DATE.log
