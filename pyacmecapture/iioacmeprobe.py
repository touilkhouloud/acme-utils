#!/usr/bin/env python
""" Python ACME Capture Utility for NXP TPMP (Temperature-controlled Power Measurement Platform)

TBD description of the utility

Inspired by work done on the "iio-capture" tool done by:
    - Paul Cercueil <paul.cercueil@analog.com>,
    - Marc Titinger <mtitinger@baylibre.com>,
    - Fabrice Dreux <fdreux@baylibre.com>,
and the work done on "pyacmegraph" tool done by:
    - Sebastien Jan <sjan@baylibre.com>.
"""


from __future__ import print_function
import struct
import traceback
import numpy as np
import iio
from mltrace import MLTrace


__app_name__ = "IIO ACME Probe Python Library"
__license__ = "MIT"
__copyright__ = "Copyright 2018, Baylibre SAS"
__date__ = "2018/03/01"
__author__ = "Patrick Titiano"
__email__ = "ptitiano@baylibre.com"
__contact__ = "ptitiano@baylibre.com"
__maintainer__ = "Patrick Titiano"
__status__ = "Development"
__version__ = "0.1"
__deprecated__ = False


# Channels mapping: 'explicit naming' vs 'IIO channel IDs'
CHANNEL_DICT = {
    'Vshunt' : 'voltage0',
    'Vbat' : 'voltage1',
    'Time' : 'timestamp',
    'Ishunt' : 'current3',
    'Power' : 'power2'}

# Channels unit
CHANNEL_UNITS = {
    'Vshunt' : 'mV',
    'Vbat' : 'mV',
    'Time' : 'ms',
    'Ishunt' : 'mA',
    'Power' : 'mW'}


class IIOAcmeProbe(object):
    """ Represent Baylibre's ACME probe. Allow controlling it as an IIO device.

    This class is used to abstract Baylibre's ACME probe,
    controlling it as an IIO device.

    """
    def __init__(self, slot, probe_type, shunt, pwr_switch, iio_device,
                 verbose_level):
        """ Initialise IIOAcmeProbe class

        Args:
            slot (int): ACME cape slot, where the ACME probe is attached
                        (as labelled on the ACME cape)
            probe_type (string): probe type (use 'JACK', 'USB', or 'HE10')
            shunt (int): shunt resistor value (in micro-ohm)
            pwr_switch (bool): True if the probe is equipped with a power switch
                               False otherwise
            iio_device (object): IIO device to use to control the probe
            verbose_level (int): how much verbose the debug trace shall be

        Returns:
            None

        """
        self._slot = slot
        self._type = probe_type
        self._shunt = shunt
        self._pwr_switch = pwr_switch
        self._iio_device = iio_device
        self._iio_buffer = None
        self._trace = MLTrace(
            verbose_level, "Probe " + self._type + " Slot " + str(self._slot))

        self._trace.trace(2, "IIOAcmeProbe instance created with settings:")
        self._trace.trace(2, "Slot: " + str(self._slot) + " Type: " + self._type
                          + ", Shunt: " + str(self._shunt) + " uOhm" +
                          ", Power Switch: " + str(self._pwr_switch))
        if verbose_level >= 2:
            self._show_iio_device_attributes()

    def _show_iio_device_attributes(self):
        """ Print the attributes of the probe's IIO device.
            Private function to be used for debug purposes only.

        Args:
            None

        Returns:
            None

        """
        self._trace.trace(3, "======== IIO Device infos ========")
        self._trace.trace(3, "  ID: " +  self._iio_device.id)
        self._trace.trace(3, "  Name: " +  self._iio_device.name)
        if  self._iio_device is iio.Trigger:
            self._trace.trace(
                3, "  Trigger: yes (rate: %u Hz)" %  self._iio_device.frequency)
        else:
            self._trace.trace(3, "  Trigger: none")
        self._trace.trace(
            3, "  Device attributes found: %u" % len(self._iio_device.attrs))
        for attr in  self._iio_device.attrs:
            self._trace.trace(
                3, "    " + attr + ": " +  self._iio_device.attrs[attr].value)
        self._trace.trace(3, "  Device debug attributes found: %u" % len(
            self._iio_device.debug_attrs))
        for attr in  self._iio_device.debug_attrs:
            self._trace.trace(
                3, "    " + attr + ": " +  self._iio_device.debug_attrs[attr].value)
        self._trace.trace(3, "  Device channels found: %u" % len(
            self._iio_device.channels))
        for chn in  self._iio_device.channels:
            self._trace.trace(3, "    Channel ID: %s" % chn.id)
            if chn.name is None:
                self._trace.trace(3, "    Channel name: (none)")
            else:
                self._trace.trace(3, "    Channel name: %s" % chn.name)
            self._trace.trace(3, "    Channel direction: %s" % (
                "output" if chn.output else 'input'))
            self._trace.trace(
                3, "    Channel attributes found: %u" % len(chn.attrs))
            for attr in chn.attrs:
                self._trace.trace(
                    3, "      " + attr + ": " + chn.attrs[attr].value)
            self._trace.trace(3, "")
        self._trace.trace(2, "==================================")

    def get_slot(self):
        """ Return the slot number (int) in which the probe is attached.

        Args:
            None

        Returns:
            int: slot number

        """
        return self._slot

    def get_type(self):
        """ Return the probe type (string).

        Args:
            None

        Returns:
            string: probe type (use 'JACK', 'USB', or 'HE10')

        """
        return self._type

    def get_shunt(self):
        """ Return the shunt resistor value of the probe (int, in micro-ohm)

        Args:
            None

        Returns:
            int: shunt resistor value (in micro-ohm)

        """
        return self._shunt

    def has_power_switch(self):
        """ Return True if the probe is equipped with a power switch,
            False otherwise.

        Args:
            None

        Returns:
            bool: True if the probe is equipped with a power switch,
                  False otherwise.

        """
        return self._pwr_switch

    def enable_power(self, enable):
        """ Enable the power switch of the probe (i.e. let the current go
            through the probe and power the device).

        Args:
            enable (bool): True to power on the device,
                           False to power off the device.

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        if self.has_power_switch() is True:
            if enable is True:
                # TODO (ptitiano@baylibre.com): implement feature
                print("TODO enable power")
                self._trace.trace(1, "Power enabled.")
            else:
                # TODO (ptitiano@baylibre.com): implement feature
                print("TODO disable power")
                self._trace.trace(1, "Power disabled.")
        else:
            self._trace.trace(1, "No power switch on this probe!")
            return False
        return True

    def set_oversampling_ratio(self, oversampling_ratio):
        """ Set the capture oversampling ratio of the probe.

        Args:
            oversampling_ratio (int): oversampling ratio

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        try:
            self._iio_device.attrs["in_oversampling_ratio"].value = str(
                oversampling_ratio)
            self._trace.trace(1, "Oversampling ratio configured to %u." % (
                oversampling_ratio))
            return True
        except:
            self._trace.trace(1,
                              "Failed to configure oversampling ratio (%u)!" %
                              oversampling_ratio)
            self._trace.trace(2, traceback.format_exc())
            return False

    def enable_asynchronous_reads(self, enable):
        """ Enable asynchronous reads.

        Args:
            enable (bool): True to enable asynchronous reads,
                           False to disable asynchronous reads.

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        try:
            if enable is True:
                self._iio_device.attrs["in_allow_async_readout"].value = "1"
                self._trace.trace(1, "Asynchronous reads enabled.")
            else:
                self._iio_device.attrs["in_allow_async_readout"].value = "0"
                self._trace.trace(1, "Asynchronous reads disabled.")
            return True
        except:
            self._trace.trace(1, "Failed to configure asynchronous reads!")
            self._trace.trace(2, traceback.format_exc())
            return False

    def get_sampling_frequency(self):
        """ Return the capture sampling frequency (in Hertz).

        Args:
            None

        Returns:
            int: capture sampling frequency (in Hertz).
                 Return 0 in case of error.

        """
        try:
            freq = self._iio_device.attrs['in_sampling_frequency'].value
            self._trace.trace(1, "Sampling frequency: %sHz" % freq)
            return int(freq)
        except:
            self._trace.trace(1, "Failed to retrieve sampling frequency!")
            self._trace.trace(2, traceback.format_exc())
            return 0

    def allocate_capture_buffer(self, samples_count, cyclic=False):
        """ Allocate buffer to store captured data.

        Args:
            samples_count (int): amount of samples to hold in buffer (> 0).
            cyclic (bool): True to make the buffer act as a circular buffer,
                           False otherwise.

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        self._iio_buffer = iio.Buffer(self._iio_device, samples_count, cyclic)
        if self._iio_buffer != None:
            self._trace.trace(1, "Buffer (count=%d, cyclic=%s) allocated." % (
                samples_count, cyclic))
            return True
        self._trace.trace(1,
                          "Failed to allocate buffer! (count=%d, cyclic=%s)" % (
                              samples_count, cyclic))
        return False

    def enable_capture_channel(self, channel, enable):
        """ Enable/disable capture of selected channel.

        Args:
            enable (bool): True to enable capture, False to disable it.

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        try:
            iio_ch = self._iio_device.find_channel(CHANNEL_DICT[channel])
            if not iio_ch:
                self._trace.trace(1, "Channel %s (%s) not found!" % (
                    channel, CHANNEL_DICT[channel]))
                return False
            self._trace.trace(2, "Channel %s (%s) found." % (
                channel, CHANNEL_DICT[channel]))
            if enable is True:
                iio_ch.enabled = True
                self._trace.trace(1, "Channel %s (%s) capture enabled." % (
                    channel, CHANNEL_DICT[channel]))
            else:
                iio_ch.enabled = False
                self._trace.trace(1, "Channel %s (%s) capture disabled." % (
                    channel, CHANNEL_DICT[channel]))
        except:
            if enable is True:
                self._trace.trace(1,
                                  "Failed to enable capture on channel %s (%s)!")
            else:
                self._trace.trace(1,
                                  "Failed to disable capture on channel %s (%s)!")
            self._trace.trace(2, traceback.format_exc())
            return False
        return True

    def refill_capture_buffer(self):
        """ Fill capture buffer with new samples.

        Args:
            None

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        try:
            self._iio_buffer.refill()
        except:
            self._trace.trace(1, "Failed to refill buffer!")
            self._trace.trace(2, traceback.format_exc())
            return False
        self._trace.trace(1, "Buffer refilled.")
        return True

    def read_capture_buffer(self, channel):
        """ Return the samples stored in the capture buffer of selected channel.
            Take care of data scaling too.

        Args:
            channel (string): capture channel

        Returns:
            dict: a dictionary holding the scaled data, with the following keys:
                  "channel" (string): channel,
                  "unit" (string): data unit,
                  "samples" (int or float): scaled samples.

        """
        try:
            # Retrieve channel
            iio_ch = self._iio_device.find_channel(CHANNEL_DICT[channel])
            # Retrieve samples (raw)
            ch_buf_raw = iio_ch.read(self._iio_buffer)
            if CHANNEL_DICT[channel] != 'timestamp':
                # Retrieve channel scale
                scale = float(iio_ch.attrs['scale'].value)
                # Configure binary data format to unpack (16-bit signed integer)
                unpack_str = 'h' * (len(ch_buf_raw) / struct.calcsize('h'))
            else:
                # No scale attribute on 'timestamp' channel
                scale = 1.0
                # Configure binary data format to unpack (64-bit signed integer)
                unpack_str = 'q' * (len(ch_buf_raw) / struct.calcsize('q'))
            # Unpack data
            values = struct.unpack(unpack_str, ch_buf_raw)
            self._trace.trace(
                2, "Channel %s: %u samples read." % (channel, len(values)))
            self._trace.trace(
                3, "Channel %s samples       : %s" % (channel, str(values)))
            # Scale values
            self._trace.trace(3, "Scale: %f" % scale)
            if scale != 1.0:
                scaled_values = np.asarray(values) * scale
            else:
                scaled_values = np.asarray(values)
            self._trace.trace(
                3,
                "Channel %s scaled samples: %s" % (channel, str(scaled_values)))
        except:
            self._trace.trace(1, "Failed to read channel %s buffer!" % channel)
            self._trace.trace(2, traceback.format_exc())
            return None
        return {"channel": channel,
                "unit": CHANNEL_UNITS[channel],
                "samples": scaled_values}
