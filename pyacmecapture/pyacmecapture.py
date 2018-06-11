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

"""


from __future__ import print_function
import traceback
import sys
import os
import argparse
import threading
from time import time, localtime, strftime
from colorama import init, Fore, Style
import numpy as np
from mltrace import MLTrace
from iioacmecape import IIOAcmeCape
from iiofakeacmecape import IIOFakeAcmeCape
from iiodevicecapturethread import IIODeviceCaptureThread


__app_name__ = "Python ACME Power Capture Utility"
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


_OVERSAMPLING_RATIO = 1
_ASYNCHRONOUS_READS = False
_CAPTURED_CHANNELS = ["Time", "Vbat", "Ishunt"]

_REPORT_1ST_COL_WIDTH = 13
_REPORT_COLS_WIDTH_MIN = 7
_REPORT_COL_PAD = 2


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
    print()
    if err != 0:
        log(Fore.RED,
            "FAILED", "Script execution terminated with error code %d." % err)
    else:
        log(Fore.GREEN,
            "SUCCESS", "Script execution completed with success.")
    print("\n< There will be a 'Segmentation fault (core dumped)' error message after this one. >")
    print("< This is a kwown bug. Please ignore it. >\n")
    exit(err)


def main():
    """ Capture power measurements of selected ACME probe(s) over IIO link.

    Refer to argparse code to learn about available commandline options.

    Returns:
        int: error code (0 in case of success, a negative value otherwise)

    """
    err = -1

    # Print application header
    print(__app_name__ + " (version " + __version__ + ")\n")

    # Colorama: reset style to default after each call to print
    init(autoreset=True)

    # Parse user arguments
    parser = argparse.ArgumentParser(
        description='TODO',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=
        '''This tool captures min, max, and average values of selected
           power rails (voltage, current, power).
           These power measurements are performed using Baylibre's
           ACME cape and probes, over the network using IIO lib.

           Example usage:
           $ ''' + sys.argv[0] +
        ''' --ip baylibre-acme.local --duration 5 -c 2 -n VDD_1,VDD_2

           Note it is assumed that slots are populated from slot 1 and
           upwards, with no hole.''')
    parser.add_argument(
        '--ip', metavar='HOSTNAME',
        default='baylibre-acme.local',
        help='ACME hostname (e.g. 192.168.1.2 or baylibre-acme.local)')
    parser.add_argument('--count', '-c', metavar='COUNT', type=int, default=8,
                        help='Number of power rails to capture (> 0))')
    parser.add_argument('--slots', '-s', metavar='SLOTS', default=None,
                        help='''List of ACME slot(s) to be captured
                        (comma-separated list, without any whitespace,
                        as labelled on the cape,
                        starting from ACME Cape slot 1 and upwards,
                        option '--count' ignored when '--slots' is used).
                        E.g. 1,2,4,7''')
    parser.add_argument('--names', '-n', metavar='LABELS', default=None,
                        help='''List of names for the captured power rails
                        (comma-separated list without any whitespace,
                        one name per power rail,
                        starting from ACME Cape slot 1 and upwards).
                        E.g. VDD_BAT,VDD_ARM''')
    parser.add_argument('--duration', '-d', metavar='SEC', type=int,
                        default=10, help='Capture duration in seconds (> 0)')
    parser.add_argument('--bufsize', '-b', metavar='BUFFER SIZE', type=int,
                        default=127, help='Capture duration in seconds (> 0)')
    parser.add_argument(
        '--outdir', '-od', metavar='OUTPUT DIRECTORY',
        default=None,
        help='''Output directory (default: $HOME/pyacmecapture/yyyymmdd-hhmmss/''')
    parser.add_argument(
        '--out', '-o', metavar='OUTPUT FILE', default=None,
        help='''Output file name (default: date (yyyymmdd-hhmmss''')
    parser.add_argument('--nofile', '-x', action="store_true", default=False,
                        help='''Do not export report and trace files''')
    parser.add_argument('--fake', '-f', action="store_true", default=False,
                        help='''Use a fake cape (SW-simulated,
                        no real HW access).
                        Use for development purposes only.''')
    parser.add_argument('--verbose', '-v', action='count',
                        help='print debug traces (various levels v, vv, vvv)')

    args = parser.parse_args()
    log(Fore.GREEN, "OK", "Parse user arguments")

    # Use MLTrace to log execution details
    trace = MLTrace(args.verbose)
    trace.trace(2, "User args: " + str(args)[10:-1])
    err = err - 1

    # Create an IIOAcmeCape instance
    if args.fake is False:
        iio_acme_cape = IIOAcmeCape(args.ip, args.verbose)
    else:
        iio_acme_cape = IIOFakeAcmeCape(args.ip, args.verbose)
    max_rail_count = iio_acme_cape.get_slot_count()

    # Check arguments are valid
    try:
        assert args.count <= max_rail_count
        assert args.count > 0
    except:
        log(Fore.RED, "FAILED", "Check user argument ('count')")
        exit_with_error(err)

    try:
        if args.slots is not None:
            args.slots = args.slots.split(',')
            for index, item in enumerate(args.slots):
                args.slots[index] = int(item)
                assert args.slots[index] <= max_rail_count
                assert args.slots[index] > 0
            args.count = len(args.slots)
        else:
            args.slots = range(1, args.count + 1)
    except:
        log(Fore.RED, "FAILED", "Check user argument ('slots')")
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
    now = strftime("%Y%m%d-%H%M%S", localtime())
    if args.nofile is False:
        if args.outdir is None:
            outdir = os.path.join(os.path.expanduser('~/pyacmecapture'), now)
        else:
            outdir = args.outdir
        trace.trace(1, "Output directory: %s" % outdir)

        if args.out is None:
            report_filename = os.path.join(outdir, now + "-report.txt")
        else:
            report_filename = os.path.join(outdir, args.out + "-report.txt")
        trace.trace(1, "Report filename: %s" % report_filename)

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
    for i in args.slots:
        attached = iio_acme_cape.probe_is_attached(i)
        if attached is not True:
            log(Fore.RED, "FAILED", "Detect probe in slot %u" % i)
            failed = True
        else:
            log(Fore.GREEN, "OK", "Detect probe in slot %u" % i)
    if failed is True:
        exit_with_error(err)
    err = err - 1

    # Create and configure capture threads
    threads = []
    failed = False
    for i in args.slots:
        try:
            thread = IIODeviceCaptureThread(
                iio_acme_cape, i, _CAPTURED_CHANNELS, args.bufsize,
                args.duration, args.verbose)
            ret = thread.configure_capture(
                _OVERSAMPLING_RATIO, _ASYNCHRONOUS_READS)
        except:
            log(Fore.RED, "FAILED", "Configure capture thread for probe in slot #%u" % i)
            trace.trace(2, traceback.format_exc())
            exit_with_error(err)
        if ret is False:
            log(Fore.RED, "FAILED", "Configure capture thread for probe in slot #%u" % i)
            exit_with_error(err)
        threads.append(thread)
        log(Fore.GREEN, "OK", "Configure capture thread for probe in slot #%u" % i)
    err = err - 1

    # Start capture threads
    try:
        for thread in threads:
            thread.start()
    except:
        log(Fore.RED, "FAILED", "Start capture")
        trace.trace(2, traceback.format_exc())
        exit_with_error(err)
    log(Fore.GREEN, "OK", "Start capture")
    err = err - 1

    # Wait for capture threads to complete
    for thread in threads:
        thread.join()
    log(Fore.GREEN, "OK", "Capture threads completed")

    if args.verbose >= 1:
        for thread in threads:
            thread.print_runtime_stats()

    # Retrieve captured data
    slot = 0
    data = []
    for thread in threads:
        samples = thread.get_samples()
        trace.trace(3, "Slot %u captured data: %s" % (samples['slot'], samples))
        data.append(samples)
    log(Fore.GREEN, "OK", "Retrieve captured samples")

    # Process samples
    for i in range(args.count):
        slot = data[i]['slot']

        # Make time samples relative to fist sample
        first_timestamp = data[i]["Time"]["samples"][0]
        data[i]["Time"]["samples"] -= first_timestamp
        timestamp_diffs = np.ediff1d(data[i]["Time"]["samples"])
        timestamp_diffs_ms = timestamp_diffs / 1000000
        trace.trace(3, "Slot %u timestamp_diffs (ms): %s" % (
            slot, timestamp_diffs_ms))
        timestamp_diffs_min = np.amin(timestamp_diffs_ms)
        timestamp_diffs_max = np.amax(timestamp_diffs_ms)
        timestamp_diffs_avg = np.average(timestamp_diffs_ms)
        trace.trace(1, "Slot %u Time difference between 2 samples (ms): "
                       "min=%u max=%u avg=%u" % (slot,
                                                 timestamp_diffs_min,
                                                 timestamp_diffs_max,
                                                 timestamp_diffs_avg))
        real_capture_time_ms = data[i]["Time"]["samples"][-1] / 1000000
        sample_count = len(data[i]["Time"]["samples"])
        real_sampling_rate = sample_count / (real_capture_time_ms / 1000.0)
        trace.trace(1,
                    "Slot %u: real capture duration: %u ms (%u samples)" % (
                        slot, real_capture_time_ms, sample_count))
        trace.trace(1,
                    "Slot %u: real sampling rate: %u Hz" % (
                        slot, real_sampling_rate))

        # Compute Power (P = Vbat * Ishunt)
        data[i]["Power"] = {}
        data[i]["Power"]["unit"] = "mW" # FIXME
        data[i]["Power"]["samples"] = np.multiply(
            data[i]["Vbat"]["samples"], data[i]["Ishunt"]["samples"])
        data[i]["Power"]["samples"] /= 1000.0
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

    # Generate report
    # Use a dictionary to map table cells with data elements
    table = {}
    table['rows'] = ['Slot', 'Shunt (mohm)',
                     'Voltage', ' Min (mV)', ' Max (mV)', ' Avg (mV)',
                     'Current', ' Min (mA)', ' Max (mA)', ' Avg (mA)',
                     'Power', ' Min (mW)', ' Max (mW)', ' Avg (mW)']
    table['data_keys'] = {}
    table['data_keys']['Voltage'] = None
    table['data_keys'][' Min (mV)'] = 'Vbat min'
    table['data_keys'][' Max (mV)'] = 'Vbat max'
    table['data_keys'][' Avg (mV)'] = 'Vbat avg'
    table['data_keys']['Current'] = None
    table['data_keys'][' Min (mA)'] = 'Ishunt min'
    table['data_keys'][' Max (mA)'] = 'Ishunt max'
    table['data_keys'][' Avg (mA)'] = 'Ishunt avg'
    table['data_keys']['Power'] = None
    table['data_keys'][' Min (mW)'] = 'Power min'
    table['data_keys'][' Max (mW)'] = 'Power max'
    table['data_keys'][' Avg (mW)'] = 'Power avg'

    report = []
    # Add misc details to report header
    report.append("Date: %s" % now)
    report.append("Pyacmecapture version: %s" % __version__)
    report.append("Captured Channels: %s" % _CAPTURED_CHANNELS)
    report.append("Oversampling ratio: %u" % _OVERSAMPLING_RATIO)
    report.append("Asynchronous reads: %s" % _ASYNCHRONOUS_READS)
    report.append("Power Rails: %u" % args.count)
    report.append("Duration: %us\n" % args.duration)

    # Adjust column width with name so that it's never truncated
    cols_width = []
    for i in range(args.count):
        if args.names is not None:
            cols_width.append(_REPORT_COL_PAD + max(
                _REPORT_COLS_WIDTH_MIN, len(args.names[i])))
        else:
            cols_width.append(_REPORT_COL_PAD + _REPORT_COLS_WIDTH_MIN)

    # Generate report
    for r in table['rows']:
        s = r.ljust(_REPORT_1ST_COL_WIDTH)
        for i in range(args.count):
            slot = data[i]['slot']
            if r == 'Slot':
                if args.names is not None:
                    s += args.names[i].rjust(cols_width[i])
                else:
                    s += str(slot).rjust(cols_width[i])
            elif r == 'Shunt (mohm)':
                s += str(iio_acme_cape.get_shunt(slot) / 1000).rjust(
                    cols_width[i])
            elif table['data_keys'][r] is not None:
                s += format(data[i][table['data_keys'][r]], '.1f').rjust(
                    cols_width[i])
        report.append(s)

    # Add output filenames to report
    trace_filenames = []
    if args.nofile is False:
        report.append("\nReport file: %s" % report_filename)
        for i in range(args.count):
            slot = data[i]['slot']
            if args.out is None:
                trace_filename = now
            else:
                trace_filename = args.out
            trace_filename += "_"
            if args.names is not None:
                trace_filename += args.names[i]
            else:
                trace_filename += "Slot_%u" % slot
            trace_filename += ".csv"
            trace_filename = os.path.join(outdir, trace_filename)
            if args.names is not None:
                report.append("%s Trace file: %s" % (
                    args.names[i], trace_filename))
            else:
                report.append("Slot %s Trace file: %s" % (
                    slot, trace_filename))
            trace_filenames.append(trace_filename)
    report_max_length = len(max(report, key=len))
    dash_count = (report_max_length - len(" Power Measurement Report ")) / 2

    # Add dashlines at beginning and end of report
    if report_max_length % 2 == 0:
        report.insert(0,
                      "-" * dash_count +
                      " Power Measurement Report " +
                      "-" * dash_count)
    else:
        report.insert(0,
                      "-" * dash_count +
                      " Power Measurement Report " +
                      "-" * (dash_count + 1))
    report.append("-" * report_max_length)

    # Save report to file
    if args.nofile is False:
        try:
            of_report = open(report_filename, 'w')
            for line in report:
                print(line, file=of_report)
            of_report.close()
        except:
            log(Fore.RED, "FAILED", "Save Power Measurement report")
            trace.trace(2, traceback.format_exc())
            exit_with_error(err)
        log(Fore.GREEN, "OK",
            "Save Power Measurement report")

    # Save Power Measurement trace to file (CSV format)
    if args.nofile is False:
        for i in range(args.count):
            slot = data[i]['slot']
            trace.trace(1, "Trace file: %s" % trace_filenames[i])
            try:
                of_trace = open(trace_filenames[i], 'w')
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
                    data[i]["Time"]["samples"][j],
                    data[i]["Vbat"]["samples"][j],
                    data[i]["Ishunt"]["samples"][j],
                    data[i]["Power"]["samples"][j])
                print(s, file=of_trace)
            of_trace.close()
            if args.names is not None:
                log(Fore.GREEN, "OK",
                    "Save %s Power Measurement Trace" % args.names[i])
            else:
                log(Fore.GREEN, "OK",
                    "Save Slot %u Power Measurement Trace" % slot)

    # Display report
    print()
    for line in report:
        print(line)

    # Done
    exit_with_error(0)

if __name__ == '__main__':
    main()
