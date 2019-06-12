"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.
"""
import functools
from logging import getLogger

logger = getLogger('results')


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
