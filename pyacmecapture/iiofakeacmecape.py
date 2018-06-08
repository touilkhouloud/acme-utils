#!/usr/bin/env python
""" Baylibre's ACME Cape Simulation class.

Simulate Baylibre's ACME Cape, for debug purposes only.
Return valid hard-coded data as if it was a real ACME Cape.
Allow offline application development (without real HW or network connection).

Todo:
    * Replace hard-coded data with configuration file

"""

from __future__ import print_function
from time import sleep
from mltrace import MLTrace


__app_name__ = "IIO Fake ACME Cape Python Module"
__license__ = "MIT"
__copyright__ = "Copyright 2018, Baylibre SAS"
__date__ = "2018/06/05"
__author__ = "Patrick Titiano"
__email__ = "ptitiano@baylibre.com"
__contact__ = "ptitiano@baylibre.com"
__maintainer__ = "Patrick Titiano"
__status__ = "Development"
__version__ = "0.1"
__deprecated__ = False


# Channels unit
CHANNEL_UNITS = {
    'Vshunt' : 'mV',
    'Vbat' : 'mV',
    'Time' : 'ns',
    'Ishunt' : 'mA',
    'Power' : 'mW'}


class IIOFakeAcmeCape(object):
    """ Simulate Baylibre's ACME cape.

    This class is used to abstract and simulate Baylibre's ACME cape.

    """
    def __init__(self, ip, verbose_level):
        """ Initialise IIOAcmeCape module.

        Args:
            ip (string): network IP address of the ACME cape. May be either
            of format '192.168.1.2' or 'baylibre-acme.local'.
            verbose_level (int): how much verbose the debug trace shall be.

        Returns:
            None

        """
        self._ip = ip
        self._verbose_level = verbose_level
        self._trace = MLTrace(verbose_level, "Fake ACME Cape")
        self._slots_count = 8
        self._channels = []
        self._samples_count = 0
        self._time_start = 0

    def is_up(self):
        """ Check if the ACME cape is up and running.

        Args:
            None

        Returns:
            bool: True if ACME cape is operational, False otherwise.

        """
        return True

    def get_slot_count(self):
        """ Return the number of slots available on the cape.

        Args:
            None

        Returns:
            int: number of slots available on the cape (> 0).

        """
        self._trace.trace(1, "Slot count: %u" % self._slots_count)
        return self._slots_count

    def _find_probes(self):
        """ Enumerate ACEM probes attached to the ACME cape,
            retrieving probe details.
            Private function, not to be used outside of the module.

        Args:
            None

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        return True

    def init(self):
        """ Configure IIOAcmeCape. Create IIO context, detect attached probes.

        Args:
            None

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        return True

    def probe_is_attached(self, slot):
        """ Return True if a probe is attached to selected slot, False otherwise.

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0).

        Returns:
            bool: True if a probe is attached to selected slot, False otherwise.

        """
        self._trace.trace(1, "Slot %d populated." % slot)
        return True

    def enable_capture_channel(self, slot, channel, enable):
        """ Enable/disable capture of selected channel.

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0).
            channel (string): channel to capture.
            enable (bool): True to enable capture, False to disable it.

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        if enable is True:
            self._channels.append(channel)
        else:
            if channel in self._channels:
                self._channels.remove(channel)
        self._trace.trace(
            1, "Slot %d enabled channels: %s" % (slot, self._channels))
        return True

    def set_oversampling_ratio(self, slot, oversampling_ratio):
        """ Set the capture oversampling ratio of the selected probe.

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0).
            oversampling_ratio (int): oversampling ratio

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        return True

    def enable_asynchronous_reads(self, slot, enable):
        """ Enable asynchronous reads.

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0).
            enable (bool): True to enable asynchronous reads,
                           False to disable asynchronous reads.

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        return True

    def get_sampling_frequency(self, slot):
        """ Return the capture sampling frequency (in Hertz).

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0).

        Returns:
            int: capture sampling frequency (in Hertz).
                 Return 0 in case of error.

        """
        return 500

    def get_shunt(self, slot):
        """ Return the shunt resistor value of the probe in selected slot

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0)

        Returns:
            int: shunt resistor value (in micro-ohm) in case of success,
                 False otherwise.

        """
        return 1000 * slot

    def allocate_capture_buffer(self, slot, samples_count, cyclic=False):
        """ Allocate buffer to store captured data.

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0)
            samples_count (int): amount of samples to hold in buffer (> 0).
            cyclic (bool): True to make the buffer act as a circular buffer,
                           False otherwise.

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        self._samples_count = samples_count
        return True

    def refill_capture_buffer(self, slot):
        """ Fill capture buffer with new samples.

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0)

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        sleep(0.5)
        return True

    def read_capture_buffer(self, slot, channel):
        """ Return the samples stored in the capture buffer of selected channel.
            Take care of data scaling too.

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0)
            channel (string): capture channel

        Returns:
            dict: a dictionary holding the scaled data, with the following keys:
                  "channel" (string): channel,
                  "unit" (string): data unit,
                  "samples" (int or float): scaled samples.

        """
        if channel == "Time":
            buff = {"channel": channel,
                    "unit": CHANNEL_UNITS[channel],
                    "samples": range(self._time_start,
                                     self._time_start +
                                     (1000000 * self._samples_count),
                                     1000000)}
            self._time_start += 1000000 * self._samples_count
        elif channel == "Vbat":
            buff = {"channel": channel,
                    "unit": CHANNEL_UNITS[channel],
                    "samples": [1000 * float(slot)] * self._samples_count}
        else:
            buff = {"channel": channel,
                    "unit": CHANNEL_UNITS[channel],
                    "samples": [float(slot)] * self._samples_count}
        return buff
