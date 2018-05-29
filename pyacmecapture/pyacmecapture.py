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
import traceback
import sys
import os
import argparse
from time import time, localtime, strftime
from colorama import init, Fore, Style
import numpy as np
from mltrace import MLTrace
from iioacmecape import IIOAcmeCape


__app_name__ = "Python ACME Power Capture Utility"
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
        log(Fore.RED, "FAILED",
            "Script execution terminated with error code %d." % err)
    else:
        log(Fore.GREEN, "SUCCESS",
            "Script execution completed with success.")
    print("\n< There will be a 'Segmentation fault (core dumped)' error message after this one. >")
    print("< This is a kwown bug. Please ignore it. >\n")
    exit(err)


def main():
    """ Capture power measurements of selected ACME probe(s) over IIO link.

    Please refer to argparse code to learn about available commandline options.

    Returns:
        int: error code (0 in case of success, a negative value otherwise)

    """
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
    parser.add_argument('--ip', metavar='HOSTNAME',
                        default='baylibre-acme.local',
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
    parser.add_argument('--outdir', '-od', metavar='OUTPUT DIRECTORY',
                        default=None,
                        help='''Output directory (default: $HOME/pyacmecapture/''')
    parser.add_argument('--out', '-o', metavar='OUTPUT FILE', default=None,
                        help='''Output file name (default: date (yyyymmdd-hhmmss''')
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
        assert args.count <= max_rail_count
        assert args.count > 0
    except:
        log(Fore.RED, "FAILED", "Check user argument ('count')")
        exit_with_error(err)

    try:
        if args.names is not None:
            args.names = args.names.split(',')
            trace.trace(2, "args.names: %s" % args.names)
            assert args.count == len(args.names)
    except:
        log(Fore.RED, "FAILED", "Check user argument ('names')")
        exit_with_error(err)

    try:
        assert args.duration > 0
    except:
        log(Fore.RED, "FAILED", "Check user argument ('duration')")
        exit_with_error(err)
    err = err - 1
    log(Fore.GREEN, "OK", "Check user arguments")

    # Create output directory (if doesn't exist)
    prefix = strftime("%Y%m%d-%H%M%S", localtime())
    if args.outdir is None:
        outdir = os.path.join(os.path.expanduser('~/pyacmecapture'), prefix)
    else:
        outdir = args.outdir
    trace.trace(1, "Output directory: %s" % outdir)
    try:
        os.makedirs(outdir)
    except OSError as e:
        if e.errno == os.errno.EEXIST:
            trace.trace(1, "Directory '%s' already exists." % outdir)
        else:
            log(Fore.RED, "FAILED", "Create output directory")
            trace.trace(2, traceback.format_exc())
            exit_with_error(err)
    except:
        log(Fore.RED, "FAILED", "Create output directory")
        trace.trace(2, traceback.format_exc())
        exit_with_error(err)
    log(Fore.GREEN, "OK", "Create output directory")

    # Check ACME Cape is reachable
    if iio_acme_cape.is_up() != True:
        log(Fore.RED, "FAILED", "Ping ACME")
        exit_with_error(err)
    log(Fore.GREEN, "OK", "Ping ACME")
    err = err - 1

    # Init IIOAcmeCape instance
    if iio_acme_cape.init() != True:
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
    ts_capture_start = time()
    for i in range(1, args.count + 1):
        ret = iio_acme_cape.refill_capture_buffer(i)
        if ret != True:
            trace.trace(1, "Slot %u: failed to refill buffer!" % i)
            failed = True
            break
    ts_capture_end = time()
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
                break
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
    try:
        if args.out is None:
            summary_filename = os.path.join(outdir, prefix + ".txt")
        else:
            summary_filename = os.path.join(outdir, args.out + ".txt")

        trace.trace(1, "Summary file: %s" % summary_filename)
        of_summary = open(summary_filename, 'w')
    except:
        log(Fore.RED, "FAILED", "Create output summary file")
        trace.trace(2, traceback.format_exc())
        exit_with_error(err)
    print()
    s = "------------------ Power Measurement results ------------------"
    print(s)
    print(s, file=of_summary)
    s = "Power Rails: %u" % args.count
    print(s)
    print(s, file=of_summary)
    s = "Duration: %us" % args.duration
    print(s)
    print(s, file=of_summary)
    for i in range(args.count):
        slot = i + 1
        if args.names is not None:
            s = "%s (slot %u)" % (args.names[i], slot)
        else:
            s = "Slot %u" % slot
        print(s)
        print(s, file=of_summary)
        s = "  Voltage (%s): min=%d max=%d avg=%d" % (data[i]["Vbat"]["unit"],
                                                      data[i]["Vbat min"],
                                                      data[i]["Vbat max"],
                                                      data[i]["Vbat avg"])
        print(s)
        print(s, file=of_summary)
        s = "  Current (%s): min=%d max=%d avg=%d" % (data[i]["Ishunt"]["unit"],
                                                      data[i]["Ishunt min"],
                                                      data[i]["Ishunt max"],
                                                      data[i]["Ishunt avg"])
        print(s)
        print(s, file=of_summary)
        s = "  Power   (%s): min=%d max=%d avg=%d" % (data[i]["Power"]["unit"],
                                                      data[i]["Power min"],
                                                      data[i]["Power max"],
                                                      data[i]["Power avg"])
        print(s)
        print(s, file=of_summary)
        if i != args.count - 1:
            print()
            print("", file=of_summary)
    s = "---------------------------------------------------------------"
    print(s + "\n")
    print(s, file=of_summary)
    of_summary.close()
    log(Fore.GREEN, "OK",
        "Save Power Measurement results to '%s'." % summary_filename)

    # Save Power Measurement trace to file (CSV format)
    for i in range(args.count):
        slot = i + 1
        if args.out is None:
            trace_filename = prefix
        else:
            trace_filename = args.out
        trace_filename += "_"
        if args.names is not None:
            trace_filename += args.names[i]
        else:
            trace_filename += "Slot_%u" % slot
        trace_filename += ".csv"
        trace_filename = os.path.join(outdir, trace_filename)
        trace.trace(1, "Trace file: %s" % trace_filename)
        try:
            of_trace = open(trace_filename, 'w')
        except:
            log(Fore.RED, "FAILED", "Create output trace file")
            trace.trace(2, traceback.format_exc())
            exit_with_error(err)

        # Format trace header (name columns)
        if args.names is not None:
            s = "Time (%s),%s Voltage (%s),%s Current (%s),%s Power (%s)" % (
                data[i]["Time"]["unit"],
                args.names[i], data[i]["Vbat"]["unit"],
                args.names[i], data[i]["Ishunt"]["unit"],
                args.names[i], data[i]["Power"]["unit"])
        else:
            s = "Time (%s),Slot %u Voltage (%s),Slot %u Current (%s),Slot %u Power (%s)" % (
                data[i]["Time"]["unit"],
                slot, data[i]["Vbat"]["unit"],
                slot, data[i]["Ishunt"]["unit"],
                slot, data[i]["Power"]["unit"])
        print(s, file=of_trace)
        # Save samples in trace file
        for j in range(len(data[i]["Ishunt"]["samples"])):
            s = "%s,%s,%s,%s" % (
                data[i]["Time"]["samples"][j], data[i]["Vbat"]["samples"][j],
                data[i]["Ishunt"]["samples"][j], data[i]["Power"]["samples"][j])
            print(s, file=of_trace)
        of_trace.close()
        if args.names is not None:
            log(Fore.GREEN, "OK",
                "Save %s Power Measurement Trace to '%s'." % (
                    args.names[i], trace_filename))
        else:
            log(Fore.GREEN, "OK",
                "Save Slot %u Power Measurement Trace to '%s'." % (
                    slot, trace_filename))

    # Done
    exit_with_error(0)

if __name__ == '__main__':
    main()
