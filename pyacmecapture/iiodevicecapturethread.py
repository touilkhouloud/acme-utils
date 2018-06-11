#!/usr/bin/env python
""" Implement a thread to capture samples from an IIO device.

This class is used to abstract the capture of multiple channels of a single
ACME probe / IIO device.

Inspired by work done on  "pyacmegraph" tool done by:
    - Sebastien Jan <sjan@baylibre.com>.
"""


from __future__ import print_function
import threading
from time import time
import numpy as np
from mltrace import MLTrace


class IIODeviceCaptureThread(threading.Thread):
    """ IIO ACME Capture thread

    This class is used to abstract the capture of multiple channels of a single
    ACME probe / IIO device.

    """
    def __init__(self, cape, slot, channels, bufsize, duration, verbose_level):
        """ Initialise IIODeviceCaptureThread class

        Args:
            slot (int): ACME cape slot
            channels (list of strings): channels to capture
                        Supported channels: 'Vshunt', 'Vbat', 'Ishunt', 'Power'
            bufsize (int): capture buffer size (in samples)
            duration (int): capture duration (in seconds)
            verbose_level (int): how much verbose the debug trace shall be

        Returns:
            None

        """
        threading.Thread.__init__(self)
        # Init internal variables
        self._cape = cape
        self._slot = slot
        self._channels = channels
        self._bufsize = bufsize
        self._duration = duration
        self._timestamp_thread_start = None
        self._thread_execution_time = None
        self._refill_start_times = None
        self._refill_end_times = None
        self._read_start_times = None
        self._read_end_times = None
        self._failed = None
        self._samples = None
        self._verbose_level = verbose_level
        self._trace = MLTrace(verbose_level, "Thread Slot %u" % self._slot)
        self._trace.trace(
            2,
            "Thread params: slot=%u channels=%s buffer size=%u duration=%us" % (
                self._slot, self._channels, self._bufsize, self._duration))

    def configure_capture(self, oversampling_ratio, asynchronous_reads):
        """ Configure capture parameters (enable channel(s),
            configure internal settings, ...)

        Args:
            oversampling_ratio (int): oversampling ratio
            asynchronous_reads (bool): set to True to enable asynchronous read,
                                       False to disable it

        Returns:
            bool: True if successful, False otherwise.

        """
        # Set oversampling for max perfs (4 otherwise)
        if self._cape.set_oversampling_ratio(self._slot, oversampling_ratio) is False:
            self._trace.trace(1, "Failed to set oversampling ratio!")
            return False
        self._trace.trace(1, "Oversampling ratio set to 1.")

        # Disable asynchronous reads
        if self._cape.enable_asynchronous_reads(self._slot, asynchronous_reads) is False:
            self._trace.trace(1, "Failed to configure asynchronous reads!")
            return False
        self._trace.trace(1, "Asynchronous reads disabled.")

        # Enable selected channels
        for ch in self._channels:
            ret = self._cape.enable_capture_channel(self._slot, ch, True)
            if ret is False:
                self._trace.trace(1, "Failed to enable %s capture!" % ch)
                return False
            else:
                self._trace.trace(1, "%s capture enabled." % ch)

        # Allocate capture buffer
        if self._cape.allocate_capture_buffer(self._slot, self._bufsize) is False:
            self._trace.trace(1, "Failed to allocate capture buffer!")
            return False
        self._trace.trace(1, "Capture buffer allocated.")
        return True

    def run(self):
        """ Capture samples for the selected duration. Save samples in a
            dictionary as described in get_samples() docstring.

        Args:
            None

        Returns:
            True when operation is completed.

        """
        self._failed = False
        self._samples = {}
        self._refill_start_times = []
        self._refill_end_times = []
        self._read_start_times = []
        self._read_end_times = []
        for ch in self._channels:
            self._samples[ch] = None
            self._samples["slot"] = self._slot
            self._samples["channels"] = self._channels
            self._samples["duration"] = self._duration

        self._timestamp_thread_start = time()
        elapsed_time = 0
        while elapsed_time < self._duration:
            # Capture samples
            self._refill_start_times.append(time())
            ret = self._cape.refill_capture_buffer(self._slot)
            self._refill_end_times.append(time())
            if ret != True:
                self._trace.trace(1, "Warning: error during buffer refill!")
                self._failed = True
            # Read captured samples
            self._read_start_times.append(time())
            for ch in self._channels:
                s = self._cape.read_capture_buffer(self._slot, ch)
                if s is None:
                    self._trace.trace(
                        1,
                        "Warning: error during %s buffer read!" % ch)
                    self._failed = True
                if self._samples[ch] is not None:
                    self._samples[ch]["samples"] = np.append(
                        self._samples[ch]["samples"], s["samples"])
                else:
                    self._samples[ch] = {}
                    self._samples[ch]["failed"] = False
                    self._samples[ch]["unit"] = s["unit"]
                    self._samples[ch]["samples"] = s["samples"]
                self._trace.trace(
                    3,
                    "self._samples[%s] = %s" % (ch, str(self._samples[ch])))
            self._read_end_times.append(time())
            elapsed_time = time() - self._timestamp_thread_start
        self._thread_execution_time = time() - self._timestamp_thread_start
        self._samples[ch]["failed"] = self._failed
        self._trace.trace(1, "Thread done.")
        return True

    def print_runtime_stats(self):
        """ Print various capture runtime-collected stats.
            Since printing traces from multiple threads causes mixed and
            confusing trace, it is preferable to collect data and print it
            afterwards. For debug purpose only.

        Args:
            None

        Returns:
            None

        """
        self._trace.trace(1, "------------- Thread Runtime Stats -------------")
        self._trace.trace(
            1,
            "Thread execution time: %s" % self._thread_execution_time)
        # Convert list to numpy array
        self._refill_start_times = np.asarray(self._refill_start_times)
        self._refill_end_times = np.asarray(self._refill_end_times)
        self._read_start_times = np.asarray(self._read_start_times)
        self._read_end_times = np.asarray(self._read_end_times)
        # Make timestamps relative to first one, and convert to ms
        first_refill_start_time = self._refill_start_times[0]
        self._refill_start_times -= first_refill_start_time
        self._refill_start_times *= 1000
        self._refill_end_times -= first_refill_start_time
        self._refill_end_times *= 1000

        first_read_start_time = self._read_start_times[0]
        self._read_start_times -= first_read_start_time
        self._read_start_times *= 1000
        self._read_end_times -= first_read_start_time
        self._read_end_times *= 1000
        # Compute refill and read durations
        refill_durations = np.subtract(
            self._refill_end_times, self._refill_start_times)
        read_durations = np.subtract(
            self._read_end_times, self._read_start_times)

        # Print time each time buffer was getting refilled
        self._trace.trace(
            2,
            "Buffer Refill start times (ms): %s" % self._refill_start_times)
        self._trace.trace(
            2,
            "Buffer Refill end times (ms): %s" % self._refill_end_times)
        # Print time spent refilling buffer
        self._trace.trace(
            2,
            "Buffer Refill duration (ms): %s" % refill_durations)
        if len(self._refill_start_times) > 1:
            # Print buffer refill time stats
            refill_durations_min = np.amin(refill_durations)
            refill_durations_max = np.amax(refill_durations)
            refill_durations_avg = np.average(refill_durations)
            self._trace.trace(
                1,
                "Buffer Refill Duration (ms): min=%s max=%s avg=%s" % (
                    refill_durations_min,
                    refill_durations_max,
                    refill_durations_avg))
            # Print delays between 2 consecutive buffer refills
            refill_delays = np.ediff1d(self._refill_start_times)
            self._trace.trace(
                2,
                "Delay between 2 Buffer Refill (ms): %s" % refill_delays)
            # Print buffer refill delay stats
            refill_delays_min = np.amin(refill_delays)
            refill_delays_max = np.amax(refill_delays)
            refill_delays_avg = np.average(refill_delays)
            self._trace.trace(
                1,
                "Buffer Refill Delay (ms): min=%s max=%s avg=%s" % (
                    refill_delays_min,
                    refill_delays_max,
                    refill_delays_avg))

        # Print time each time buffer was getting read
        self._trace.trace(
            2,
            "Buffer Read start times (ms): %s" % self._read_start_times)
        self._trace.trace(
            2,
            "Buffer Read end times (ms): %s" % self._read_end_times)
        # Print time spent reading buffer
        self._trace.trace(2, "Buffer Read duration (ms): %s" % read_durations)
        if len(self._read_start_times) > 1:
            # Print buffer read time stats
            read_durations_min = np.amin(read_durations)
            read_durations_max = np.amax(read_durations)
            read_durations_avg = np.average(read_durations)
            self._trace.trace(
                1,
                "Buffer Read Duration (ms): min=%s max=%s avg=%s" % (
                    read_durations_min,
                    read_durations_max,
                    read_durations_avg))
            # Print delays between 2 consecutive buffer reads
            read_delays = np.ediff1d(self._read_start_times)
            self._trace.trace(
                2,
                "Delay between 2 Buffer Read (ms): %s" % read_delays)
            # Print buffer read delay stats
            read_delays_min = np.amin(read_delays)
            read_delays_max = np.amax(read_delays)
            read_delays_avg = np.average(read_delays)
            self._trace.trace(
                1,
                "Buffer Read Delay (ms): min=%s max=%s avg=%s" % (
                    read_delays_min,
                    read_delays_max,
                    read_delays_avg))
        self._trace.trace(1, "------------------------------------------------")

    def get_samples(self):
        """ Return collected samples. To be called once thread completed.

        Args:
            None

        Returns:
            dict: a dictionary (one per channel) containing following key/data:
                "slot" (int): ACME cape slot
                "channels" (list of strings): channels captured
                "duration" (int): capture duration (in seconds)
                For each captured channel:
                "capture channel name" (dict): a dictionary containing following key/data:
                    "failed" (bool): False if successful, True otherwise
                    "samples" (array): captured samples
                    "unit" (str): captured samples unit}}
            E.g:
                {'slot': 1, 'channels': ['Vbat', 'Ishunt'], 'duration': 3,
                 'Vbat': {'failed': False, 'samples': array([ 1, 2, 3 ]), 'unit': 'mV'},
                 'Ishunt': {'failed': False, 'samples': array([4, 5, 6 ]), 'unit': 'mA'}}

        """
        return self._samples
