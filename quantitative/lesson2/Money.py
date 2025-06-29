"""
Author: Yiqian Qian
Description: Automated script to run jobs on time.
Date: 2022-03-02 10:02:27
LastEditors: Yiqian Qian
LastEditTime: 2022-03-03 09:45:22
FilePath: /Users/qyq/Library/Mobile Documents/com~apple~CloudDocs/Development/量化交易/quantitative/lesson2/Money.py
"""
# -*- coding:utf-8 -*-

import time

from apscheduler.schedulers.blocking import BlockingScheduler
from job import run_today_120

sched = BlockingScheduler()
sched.add_job(
    run_today_120,
    "cron",
    day_of_week="mon-fri",
    hour=9,
    minute=25,
    timezone="Asia/Shanghai",
)


sched.start()
