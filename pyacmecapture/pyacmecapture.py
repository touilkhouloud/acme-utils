#!/usr/bin/env python
""" Python ACME Power Capture Utility

This utility is designed to capture voltage, current and power samples with
Baylibre's ACME Power Measurement solution (www.baylibre.com/acme).

The following assumption(s) were made:
    - ACME Cape slots are populated with probes starting from slot 1,
      with no 'holes' in between (e.g. populating slots 1,2,3 is valid,
                                       populating slots 1,2 4 is not)

Inspired by work done on the "iio-capture" tool done by:
    - Paul Cercueil <paul.cercueil@analog.com>,
    - Marc Titinger <mtitinger@baylibre.com>,
    - Fabrice Dreux <fdreux@baylibre.com>,
and the work done on "pyacmegraph" tool done by:
    - Sebastien Jan <sjan@baylibre.com>.

Leveraged IIOAcmeCape and IIOAcmeProbe classes abstracting IIO/ACME details.

Todo:
    * Fix Segmentation fault at end of script
    * Find a way to remove hard-coded power unit (uW)
    * Save logs to file

"""


from __future__ import print_function
import sys
import argparse
import time
from colorama import init, Fore, Style
import traceback
import numpy as np
from mltrace import MLTrace
from iioacmecape import IIOAcmeCape


__app_name__ = "Python ACME Power Capture Utility"
__license__ = "MIT"
__copyright__ = "Copyright 2018, Baylibre SAS"
__date__ = "2018/03/01"
__author__ = "Patrick Titiano"
__email__ =  "ptitiano@baylibre.com"
__contact__ = "ptitiano@baylibre.com"
__maintainer__ = "Patrick Titiano"
__status__ = "Development"
__version__ = "0.1"
__deprecated__ = False


def log(color, flag, msg):
    """ Format messages as follow: "['color'ed 'flag'] 'msg'"

    Args:
        color (str): the color of the flag (e.g. Fore.RED, Fore.GREEN, ...)
        flag (str): a custom flag (e.g. 'OK', 'FAILED', 'WARNING', ...)
        msg (str): a custom message (e.g. 'this is my great custom message')

    Returns:
        None

    """
    print("[" + color + flag + Style.RESET_ALL + "] " + msg)


def exit_with_error(err):
    """ Display completion message with error code before terminating execution.

    Args:
        err (int): an error code

    Returns:
        None

    """
    if err != 0:
        print("\nScript execution terminated with error code %d." % err)
    else:
        print("\nScript execution completed with success.")
    print("\n< There will be a 'Segmentation fault (core dumped)' error message after this one. >")
    print("< This is a kwown bug. Please ignore it. >\n")
    exit(err)


def main():
    err = -1
    channels_to_capture = ["Time", "Vbat", "Ishunt"]

    # Print application header
    print(__app_name__ + " (version " + __version__ + ")\n")

    # Colorama: reset style to default after each call to print
    init(autoreset=True)

    # Parse user arguments
    parser = argparse.ArgumentParser(description='TODO',
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog='''
    This tool captures min, max, and average values of selected power rails (voltage, current, power).
    These power measurements are performed using Baylibre's ACME cape and probes, over the network using IIO lib.
    Example usage:
        ''' + sys.argv[0] + ''' --ip baylibre-acme.local --duration 5 -c 2 -n VDD_1,VDD_2

    Note it is assumed that slots are populated from slot 1 and upwards, with no hole.''')
    parser.add_argument('--ip', metavar='HOSTNAME', default='baylibre-acme.local',# add default hostname here
                        help='ACME hostname (e.g. 192.168.1.2 or baylibre-acme.local)')
    parser.add_argument('--count', '-c', metavar='COUNT', type=int, default=8,
                        help='Number of power rails to capture (> 0))')
    parser.add_argument('--names', '-n', metavar='LABELS',
                        help='''List of names for the captured power rails
                        (comma separated list, one name per power rail,
                        always start from ACME Cape slot 1).
                        E.g. VDD_BAT,VDD_ARM,...''')
    parser.add_argument('--duration', '-d', metavar='SEC', type=int,
                        default=10, help='Capture duration in seconds (> 0)')
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help='print debug traces (various levels v, vv, vvv)')

    args = parser.parse_args()
    log(Fore.GREEN, "OK", "Parse user arguments")

    # Use MLTrace to log execution details
    trace = MLTrace(args.verbose)
    trace.trace(2, "User args: " + str(args)[10:-1])
    err = err - 1

    # Create an IIOAcmeCape instance
    iio_acme_cape = IIOAcmeCape(args.ip, args.verbose)
    max_rail_count = iio_acme_cape.get_slot_count()

    # Check arguments are valid
    try:
        assert (args.count <= max_rail_count)
        assert (args.count > 0)
    except:
        log(Fore.RED, "FAILED", "Check user argument ('count')")
        exit_with_error(err)

    try:
        if args.names is not None:
            args.names = args.names.split(',')
            trace.trace(2, "args.names: %s" % args.names)
            assert (args.count == len(args.names))
    except:
        log(Fore.RED, "FAILED", "Check user argument ('names')")
        exit_with_error(err)

    try:
        assert (args.duration > 0)
    except:
        log(Fore.RED, "FAILED", "Check user argument ('duration')")
        exit_with_error(err)
    err = err - 1
    log(Fore.GREEN, "OK", "Check user arguments")

    # Check ACME Cape is reachable
    if iio_acme_cape.is_up() != True:
        log(Fore.RED, "FAILED", "Ping ACME")
        exit_with_error(err)
    log(Fore.GREEN, "OK", "Ping ACME")
    err = err - 1

    # Init IIOAcmeCape instance
    if (iio_acme_cape.init() != True):
        log(Fore.RED, "FAILED", "Init ACME IIO Context")
        exit_with_error(err)
    log(Fore.GREEN, "OK", "Init ACME Cape instance")
    err = err - 1

    # Check all probes are attached
    failed = False
    for i in range(1, args.count + 1):
        attached = iio_acme_cape.probe_is_attached(i)
        if attached is not True:
            log(Fore.RED, "FAILED", "Detect probe in slot %u" % i)
            failed = True
        else:
            log(Fore.GREEN, "OK", "Detect probe in slot %u" % i)
    if failed is True:
        exit_with_error(err)
    err = err - 1

    # Configure capture
    failed = False
    exception_raised = False
    for i in range(1, args.count + 1):
        try:
            # Set oversampling for max perfs (4 otherwise)
            if iio_acme_cape.set_oversampling_ratio(i, 1) is False:
                trace.trace(1, "Slot %u: failed to set oversampling ratio!" % i)
                failed = True
                break
            trace.trace(1, "Slot %u: oversampling ratio set to 1." % i)
            # Disable asynchronous reads
            if iio_acme_cape.enable_asynchronous_reads(i, False) is False:
                trace.trace(1, "Slot %u: failed to configure asynchronous reads!" % i)
                failed = True
                break
            trace.trace(1, "Slot %u: asynchronous reads disabled." % i)
            # Enable selected channels ("Time", "Vbat", "Ishunt")
            for ch in channels_to_capture:
                ret = iio_acme_cape.enable_capture_channel(i, ch, True)
                if ret is False:
                    trace.trace(1, "Slot %u: failed to enable %s capture!" % (i, ch))
                    failed = True
                    break
                else:
                    trace.trace(1, "Slot %u: %s capture enabled." % (i, ch))
            # Allocate capture buffer
            freq = iio_acme_cape.get_sampling_frequency(i)
            if freq == 0:
                trace.trace(1, "Slot %u: failed to retrieve sampling frequency!" % i)
                failed = True
                break
            trace.trace(1, "Slot %u: sampling frequency: %uHz" % (i, freq))
            buffer_size = freq * args.duration
            trace.trace(1, "Slot %u: buffer size: %u" % (i, buffer_size))
            if iio_acme_cape.allocate_capture_buffer(i, buffer_size) is False:
                trace.trace(1, "Slot %u: failed to allocate capture buffer!" % i)
                failed = True
                break
            else:
                trace.trace(1, "Slot %u: capture buffer allocated." % i)
        except:
            exception_raised = True
            failed = True
        log(Fore.GREEN, "OK", "Configure capture for probe in slot #%u" % i)
    if failed is True:
        log(Fore.RED, "FAILED", "Configure capture for probe in slot #%u" % i)
        if exception_raised is True:
            trace.trace(2, traceback.format_exc())
        exit_with_error(err)
    err = err - 1

    # Refill capture buffers
    failed = False
    ts_capture_start = time.time()
    for i in range(1, args.count + 1):
        ret = iio_acme_cape.refill_capture_buffer(i)
        if ret != True:
            trace.trace(1, "Slot %u: failed to refill buffer!" % i)
            failed = True
            break
    ts_capture_end = time.time()
    ts_buffer_refill = ts_capture_end - ts_capture_start
    trace.trace(1, "Time spent refilling buffer: %u" % ts_buffer_refill)
    if failed is True:
        log(Fore.RED, "FAILED", "Refill capture buffers")
        exit_with_error(err)
    log(Fore.GREEN, "OK", "Refill capture buffers")
    err = err - 1

    # Read captured samples
    data = []
    failed = False
    for i in range(1, args.count + 1):
        slot_dict = {}
        slot_dict["slot"] = i
        slot_dict["duration"] = args.duration
        slot_dict["channels"] = channels_to_capture
        for ch in channels_to_capture:
            s = iio_acme_cape.read_capture_buffer(i, ch)
            if s is None:
                trace.trace(
                    1, "Slot %u: error during %s buffer read!" % (i, ch))
                failed = True
                break;
            slot_dict[ch] = {}
            slot_dict[ch]["samples"] = s["samples"]
            slot_dict[ch]["unit"] = s["unit"]
        data.append(slot_dict)
    trace.trace(3, "Read data: %s" %data)
    if failed is True:
        log(Fore.RED, "FAILED", "Read capture buffers")
        exit_with_error(err)
    log(Fore.GREEN, "OK", "Read capture buffers")
    err = err - 1

    # Process samples
    for i in range(args.count):
        slot = i + 1
        # Make time samples relative to fist sample
        first_timestamp = data[i]["Time"]["samples"][0]
        data[i]["Time"]["samples"] -= first_timestamp
        if args.verbose >= 2:
            timestamp_diffs = np.ediff1d(data[i]["Time"]["samples"])
            timestamp_diffs_ms = timestamp_diffs / 1000000
            trace.trace(3, "Slot %u timestamp_diffs (ms): %s" % (
                slot, timestamp_diffs_ms))
            timestamp_diffs_min = np.amin(timestamp_diffs_ms)
            timestamp_diffs_max = np.amax(timestamp_diffs_ms)
            timestamp_diffs_avg = np.average(timestamp_diffs_ms)
            trace.trace(2, "Slot %u Time difference between 2 samples (ms): "
                           "min=%u max=%u avg=%u" % (slot,
                                                     timestamp_diffs_min,
                                                     timestamp_diffs_max,
                                                     timestamp_diffs_avg))
            trace.trace(2, "Slot %u Real capture duration: %u ms" % (
                slot, data[i]["Time"]["samples"][-1] / 1000000))

        # Compute P (P = Vbat * Ishunt)
        data[i]["Power"] = {}
        data[i]["Power"]["unit"] = "uW" # FIXME
        data[i]["Power"]["samples"] = np.multiply(
            data[i]["Vbat"]["samples"], data[i]["Ishunt"]["samples"])
        trace.trace(3, "Slot %u power samples: %s" % (
            slot, data[i]["Power"]["samples"]))

        # Compute min, max, avg values for Vbat, Ishunt and Power
        data[i]["Vbat min"] = np.amin(data[i]["Vbat"]["samples"])
        data[i]["Vbat max"] = np.amax(data[i]["Vbat"]["samples"])
        data[i]["Vbat avg"] = np.average(data[i]["Vbat"]["samples"])
        data[i]["Ishunt min"] = np.amin(data[i]["Ishunt"]["samples"])
        data[i]["Ishunt max"] = np.amax(data[i]["Ishunt"]["samples"])
        data[i]["Ishunt avg"] = np.average(data[i]["Ishunt"]["samples"])
        data[i]["Power min"] = np.amin(data[i]["Power"]["samples"])
        data[i]["Power max"] = np.amax(data[i]["Power"]["samples"])
        data[i]["Power avg"] = np.average(data[i]["Power"]["samples"])
    log(Fore.GREEN, "OK", "Process samples")

    # Save data to file and display report
    print("\n------------------ Measurement results ------------------")
    print("Power Rails: %u" % args.count)
    print("Duration: %us" % args.duration)
    for i in range(args.count):
        slot = i + 1
        if args.names is not None:
            print("%s (slot %u)" % (args.names[i], slot))
        else:
            print("Slot %u" % slot)
        print("  Voltage (%s): min=%d max=%d avg=%d" % (data[i]["Vbat"]["unit"],
                                                        data[i]["Vbat min"],
                                                        data[i]["Vbat max"],
                                                        data[i]["Vbat avg"]))
        print("  Current (%s): min=%d max=%d avg=%d" % (data[i]["Ishunt"]["unit"],
                                                        data[i]["Ishunt min"],
                                                        data[i]["Ishunt max"],
                                                        data[i]["Ishunt avg"]))
        print("  Power   (%s): min=%d max=%d avg=%d" % (data[i]["Power"]["unit"],
                                                        data[i]["Power min"],
                                                        data[i]["Power max"],
                                                        data[i]["Power avg"]))
        if i != args.count - 1:
            print()
    print("---------------------------------------------------------")

    # Done
    exit_with_error(0)

if __name__ == '__main__':
    main()