#!/usr/bin/env python
""" Baylibre's ACME Cape Abstraction class

Baylibre's ACME Cape Abstraction class.

Inspired by work done on the "iio-capture" tool done by:
    - Paul Cercueil <paul.cercueil@analog.com>,
and the work done on "pyacmegraph" tool done by:
    - Sebastien Jan <sjan@baylibre.com>.
"""

from __future__ import print_function
import traceback
import xmlrpclib
import iio
from mltrace import MLTrace
from ping import ping
from iioacmeprobe import IIOAcmeProbe


__app_name__ = "IIO ACME Cape Python Library"
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


class IIOAcmeCape(object):
    """ Represent Baylibre's ACME cape.

    This class is used to abstract Baylibre's ACME cape.

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
        self._trace = MLTrace(verbose_level, "ACME Cape")
        self._iioctx = None
        self._slots = []
        # Hard-coded value until exported by ACME FW via IIO or XMLRPC service
        self._slots_count = 8

    def is_up(self):
        """ Check if the ACME cape is up and running.

        Args:
            None

        Returns:
            bool: True if ACME cape is operational, False otherwise.

        """
        return ping(self._ip)

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
        acme_server_address = "%s:%d" % (self._ip, 8000)

        # Use ACME XMLRPC service
        try:
            proxy = xmlrpclib.ServerProxy("http://%s/acme" % acme_server_address)
        except:
            self._trace.trace(1,
                              "Failed to use ACME XMLRPC service! (\"" +
                              acme_server_address + "\")")
            self._trace.trace(2, traceback.format_exc())
            return False
        self._trace.trace(1, "ACME XMLRPC service ready.")
        # Browse ACME slots one by one to find which ones are populated
        iio_device_idx = 0
        for i in range(1, self._slots_count + 1):
            try:
                info = proxy.info("%s" % i)
                self._trace.trace(2, info)
            except:
                self._trace.trace(1, "No XMLRPC service found for slot %d." % i)
                continue
            if info.find('Failed') != -1:
                # Slot no used
                self._trace.trace(1, "XMLRPC: ACME Cape slot %d is empty." % i)
                self._slots.append(None)
            else:
                self._trace.trace(1, "XMLRPC: ACME Cape slot %d is used." % i)
                # Retrieve probe type
                if info.find("JACK") != -1:
                    probe_type = "JACK"
                elif info.find("USB") != -1:
                    probe_type = "USB"
                elif info.find("HE10") != -1:
                    probe_type = "HE10"
                else:
                    self._trace.trace(1, "XMLRPC: probe type not found?!")
                    self._slots.append(None)
                    continue
                self._trace.trace(2, "Probe type: " + probe_type)

                # Retrieve shunt resistor value
                pos1 = info.find("R_Shunt:")
                if pos1 != -1:
                    pos2 = info.find("uOhm")
                    if pos2 != -1:
                        shunt = info[pos1 + 9: pos2 - 1]
                        self._trace.trace(2, "Probe shunt: " + shunt)
                    else:
                        self._trace.trace(1, "XMLRPC: probe shunt not found?!")
                        continue
                else:
                    self._trace.trace(1, "XMLRPC: probe shunt not found?!")
                    continue

                # Retrieve power switch capability
                if info.find("Has Power Switch") != -1:
                    pwr_switch = True
                else:
                    pwr_switch = False
                self._trace.trace(2, "Probe power switch: " + str(pwr_switch))

                # Create IIOAcmeProbe instance
                self._slots.append(IIOAcmeProbe(i, probe_type,
                                                int(shunt), pwr_switch,
                                                self._iioctx.devices[iio_device_idx],
                                                self._verbose_level))
                iio_device_idx = iio_device_idx + 1
        return True

    def _show_iio_context_attributes(self):
        """ Display IIO contect attributes, for debug purposes.
            Private function, not to be used outside of the module.

        Args:
            None

        Returns:
            None

        """
        self._trace.trace(3, "======== IIO context infos ========")
        self._trace.trace(3, "  Name: " + self._iioctx.name)
        self._trace.trace(3, "  Library version: %u.%u (git tag: %s)" % self._iioctx.version)
        self._trace.trace(3, "  Backend version: %u.%u (git tag: %s)" % self._iioctx.version)
        self._trace.trace(3, "  Backend description string: " + self._iioctx.description)
        if len(self._iioctx.attrs) > 0:
            self._trace.trace(3, "  Attributes: %u" % len(self._iioctx.attrs))
            for attr, value in self._iioctx.attrs.items():
                self._trace.trace(3, "    " + attr + ": " + value)
        self._trace.trace(3, "===================================")

    def init(self):
        """ Configure IIOAcmeCape. Create IIO context, detect attached probes.

        Args:
            None

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        # Connecting to ACME
        try:
            self._trace.trace(1, "Connecting to %s..." % self._ip)
            self._iioctx = iio.Context("ip:" + self._ip)
        except OSError:
            self._trace.trace(1, "Connection timed out!")
            return False
        except:
            self._trace.trace(2, traceback.format_exc())
            return False

        if self._verbose_level >= 2:
            self._show_iio_context_attributes()

        # There is not yet an attribute in the IIO device to indicate in which
        # ACME Cape slot the IIO device is attached. Hence, need to first find
        # the populated ACME Cape slot(s), and then save this info.
        try:
            self._find_probes()
        except:
            self._trace.trace(2, traceback.format_exc())
            return False

        return True

    def probe_is_attached(self, slot):
        """ Return True if a probe is attached to selected slot, False otherwise.

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0).

        Returns:
            bool: True if a probe is attached to selected slot, False otherwise.

        """
        try:
            # ACME slots are labelled from 1 to 8 on cape,
            # but handled from 0 to 7 in SW.
            if self._slots[slot - 1] is None:
                self._trace.trace(1, "Slot %d not populated." % slot)
                return False
            self._trace.trace(1, "Slot %d populated." % slot)
            return True
        except:
            self._trace.trace(1, "Failed to determine slot %d status!" % slot)
            self._trace.trace(2, traceback.format_exc())
            return False

    def enable_capture_channel(self, slot, channel, enable):
        """ Enable/disable capture of selected channel.

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0).
            channel (string): channel to capture.
            enable (bool): True to enable capture, False to disable it.

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        try:
            # ACME slots are labelled from 1 to 8 on cape,
            # but handled from 0 to 7 in SW.
            return self._slots[slot - 1].enable_capture_channel(channel, enable)
        except AttributeError:
            self._trace.trace(1, "No probe in slot %d" % slot)
            return False
        except:
            self._trace.trace(1, "Failed to configure capture channel (slot %d)!" % slot)
            self._trace.trace(2, traceback.format_exc())
            return False

    def set_oversampling_ratio(self, slot, oversampling_ratio):
        """ Set the capture oversampling ratio of the selected probe.

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0).
            oversampling_ratio (int): oversampling ratio

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        try:
            # ACME slots are labelled from 1 to 8 on cape,
            # but handled from 0 to 7 in SW.
            return self._slots[slot - 1].set_oversampling_ratio(oversampling_ratio)
        except AttributeError:
            self._trace.trace(1, "No probe in slot %d" % slot)
            return False
        except:
            self._trace.trace(1, "Failed to configure oversampling ratio (slot %d)!" % slot)
            self._trace.trace(2, traceback.format_exc())
            return False

    def enable_asynchronous_reads(self, slot, enable):
        """ Enable asynchronous reads.

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0).
            enable (bool): True to enable asynchronous reads,
                           False to disable asynchronous reads.

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        try:
            # ACME slots are labelled from 1 to 8 on cape,
            # but handled from 0 to 7 in SW.
            return self._slots[slot - 1].enable_asynchronous_reads(enable)
        except AttributeError:
            self._trace.trace(1, "No probe in slot %d" % slot)
            return False
        except:
            self._trace.trace(1, "Failed to configure asynchronous reads (slot %d)!" % slot)
            self._trace.trace(2, traceback.format_exc())
            return False

    def get_sampling_frequency(self, slot):
        """ Return the capture sampling frequency (in Hertz).

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0).

        Returns:
            int: capture sampling frequency (in Hertz).
                 Return 0 in case of error.

        """
        try:
            # ACME slots are labelled from 1 to 8 on cape,
            # but handled from 0 to 7 in SW.
            return self._slots[slot - 1].get_sampling_frequency()
        except AttributeError:
            self._trace.trace(1, "No probe in slot %d" % slot)
            return False
        except:
            self._trace.trace(1, "Failed to retrieve sampling frequency (slot %d)!" % slot)
            self._trace.trace(2, traceback.format_exc())
            return False

    def get_shunt(self, slot):
        """ Return the shunt resistor value of the probe in selected slot

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0)

        Returns:
            int: shunt resistor value (in micro-ohm) in case of success,
                 False otherwise.

        """
        try:
            # ACME slots are labelled from 1 to 8 on cape,
            # but handled from 0 to 7 in SW.
            return self._slots[slot - 1].get_shunt()
        except AttributeError:
            self._trace.trace(1, "No probe in slot %d" % slot)
            return False
        except:
            self._trace.trace(1, "Failed to retrieve shunt value (slot %d)!" % slot)
            self._trace.trace(2, traceback.format_exc())
            return False

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
        try:
            # ACME slots are labelled from 1 to 8 on cape,
            # but handled from 0 to 7 in SW.
            return self._slots[slot - 1].allocate_capture_buffer(samples_count, cyclic)
        except AttributeError:
            self._trace.trace(1, "No probe in slot %d" % slot)
            return False
        except:
            self._trace.trace(1, "Failed to allocate capture buffer (slot %d)!" % slot)
            self._trace.trace(2, traceback.format_exc())
            return False

    def refill_capture_buffer(self, slot):
        """ Fill capture buffer with new samples.

        Args:
            slot (int): ACME cape slot, as labelled on the cape (>0)

        Returns:
            bool: True if operation is successful, False otherwise.

        """
        try:
            # ACME slots are labelled from 1 to 8 on cape,
            # but handled from 0 to 7 in SW.
            return self._slots[slot - 1].refill_capture_buffer()
        except AttributeError:
            self._trace.trace(1, "No probe in slot %d" % slot)
            return False
        except:
            self._trace.trace(1, "Failed to refill capture buffer (slot %d)!" % slot)
            self._trace.trace(2, traceback.format_exc())
            return False

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
        try:
            # ACME slots are labelled from 1 to 8 on cape,
            # but handled from 0 to 7 in SW.
            return self._slots[slot - 1].read_capture_buffer(channel)
        except AttributeError:
            self._trace.trace(1, "No probe in slot %d" % slot)
            return False
        except:
            self._trace.trace(1, "Failed to read capture buffer (slot %d)!" % slot)
            self._trace.trace(2, traceback.format_exc())
            return False
