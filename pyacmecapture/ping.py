#!/usr/bin/env python
""" Python Network Ping Utility

Python function implementing network ping functionality.

Source: https://stackoverflow.com/questions/2953462/pinging-servers-in-python
"""


from platform import system as system_name # Returns the system/OS name
from os import system as system_call       # Execute a shell command

__app_name__ = "Ping"
__license__ = "MIT"
__copyright__ = "Copyright 2018, Baylibre SAS"
__date__ = "2018/03/01"
__author__ = "Patrick Titiano"
__email__ = "ptitiano@baylibre.com"
__contact__ = "ptitiano@baylibre.com"
__maintainer__ = "Patrick Titiano"
__status__ = "Development"
__version__ = "0.2"
__deprecated__ = False


def ping(host):
    """Return True if host (str) responds to a ping request.

    Send a ping request to 'host' and return True if a response is received,
    False otherwise.
    Remember that some hosts may not respond to a ping request even if the host
    name is valid.

    Args:
        host: hostname (e.g. 192.168.1.2 or myhost.mydomain)

    Returns:
        True if host (str) responds to a ping request, False otherwise.
    """

    # Ping parameters as function of OS
    parameters = "-n 1" if system_name().lower() == "windows" else "-c 1"

    # Pinging
    return system_call("ping " + parameters + " " + host + " > /dev/null") == 0
