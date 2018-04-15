#!/usr/bin/env python3.6

"""Run instacron.py every day between 8AM-9AM, 2PM-3PM, and 5PM-6PM.

By adding the following line after executing `crontab -e`:
* 8-9,14-15,17-18 * * * $HOME/instacron/cronjob.py
(Modify the path of `instacron` in the above line.)
"""

import os.path
import time

if time.time() - os.path.getmtime('uploaded.txt') > 24 * 3600:
    import instacron
    instacron.main()
