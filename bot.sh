#!/bin/bash

# Get today's date in YYYYMMDD format
DATE=$(date +%Y%m%d)
TIME=$(date +%Y%m%d-%H%M%S)
cd /home/colin/workspace/BinanceTrader
echo "执行时间:$TIME">>bot-$DATE.log
/home/colin/anaconda3/envs/BinanceTrader/bin/python main.py>>bot-$DATE.log
