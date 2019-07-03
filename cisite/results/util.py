"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.
"""
import functools
from concurrent.futures.thread import ThreadPoolExecutor
from logging import getLogger

logger = getLogger('results')

# Used to share for set_public and set_private environments
# 1 worker so that set_private and set_public can't be executed at the same time
singleThreadedExecutor = ThreadPoolExecutor(max_workers=1)


def log_exception(fn):
    """A decorator that catches and logs uncaught exceptions.

    This is useful if the function is used in a thread and there is no call to
    result() or join(), since exceptions don't get raised to the parent thread
    unless getting the result or joining.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            logger.exception(f'Exception in function {fn.__name__}!')
    return wrapper
