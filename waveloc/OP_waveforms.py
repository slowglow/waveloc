#!/usr/bin/env python
# encoding: utf-8

"""
The :mod:`OP_waveforms` module provides the :class:`Waveform` class through
which most time-series manipulation is carried out, as well as several
useful functions.

.. note::
   Requires **scikits.samplerate** for full functionality (on linux systems
   install with ``easy_install scikits.samplerate`` after having installed the
   ``libsamplerate0`` libraries using e.g. ``apt-get install libsamplerate0``).
   **scikits.samplerate** is used to provide high-fidelity resampling when
   standard decimation is not possible (e.g. to pass from 125Hz sampling to
   100Hz sampling).

"""

import os
import glob
import numpy as np
import logging

import matplotlib.pyplot as plt

from .filters import sw_kurtosis1, smooth, rec_kurtosis_old

from obspy.core import read, utcdatetime, stream, Stream
from obspy.signal import filter, trigger
from obspy.signal.invsim import cosine_taper

class Waveform(object):
    """
    Wrapper class for obspy streams. Adds many convenience functions, and
    functionality specific to WaveLoc processing.

    **Attributes**

    .. attribute:: stream

        An :class:`obspy.core.Stream` object.  Can be accessed directly.
        Initialises to ``None``.
        If you set this attribute directly, you should also set :attr:`.trace`
        to :attr:`.stream`.traces[0]

    .. attribute:: trace

        An obspy.Trace object.  Can be accessed directly.
        Initialises to ``None``.
        If you set this directly, make sure it points to
        :attr:`.stream`.traces[0]

    .. attribute:: proc

        Text string indicating processing type.  Can be accessed directly.
        Initialises to ``None``.

    **Methods**

  """

    def __init__(self):
        """
        Initialises Waveform to have empty stream, trace and proc
        (they are all set to None).

        """
        self.stream = None
        self.trace = None
        self.proc = None

    def _get_npts_(self):
        """Number of points in :attr:`trace` (read-only). """
        return self.trace.stats.npts

    def _get_delta_(self):
        """Time step between data points in :attr:`trace` (read-only). """
        return self.trace.stats.delta

    def _get_station_(self):
        """Station name from ``self.trace`` (read-only). """
        return self.trace.stats.station

    def _get_channel_(self):
        """Channel name from ``self.trace`` (read-only). """
        return self.trace.stats.channel

    def _get_t_array_(self):
        """A ``numpy.array`` containing times in seconds from
        ``self.trace.stats.starttime`` for data points in ``self.trace``
        (read-only). """
        return np.arange(0, self.trace.stats.npts * self.trace.stats.delta,
                         self.trace.stats.delta)

    def _get_values_(self):
        """Values of ``self.trace.data`` (read-only). """
        return self.trace.data

    def _get_starttime_(self):
        """Start time of ``self.trace`` (read-only). """
        return self.trace.stats.starttime

    npts = property(_get_npts_)
    delta = property(_get_delta_)
    dt = property(_get_delta_)
    station = property(_get_station_)
    channel = property(_get_channel_)
    comp = property(_get_channel_)
    t_array = property(_get_t_array_)
    values = property(_get_values_)
    starttime = property(_get_starttime_)

    def read_from_SDS(self, sds_root, net_name, sta_name, comp_name,
                      starttime=None, endtime=None, rmean=False, taper=False,
                      pad_value=None):
        """
        Read waveform data from an SDS structured archive.  Simple overlaps and
        adjacent traces are merged if possile.

        :param sds_root: root of the SDS archive
        :param net_name: network name
        :param sta_name: station name
        :param comp_name: component name
        :param starttime: Start time of data to be read.
        :param endtime: End time of data to be read.
        :param rmean: If ``True`` removes the mean from the data upon reading.
            If data are segmented, the mean will be removed from all segments
            individually.
        :param taper: If ``True`` applies a cosine taper to the data upon
            reading.  If data are segmented, tapers are applied to all segments
            individually.
        :param pad_value: If this parameter is set, points between
            ``starttime`` and the first point in the file, and points between
            the last point in the file and ``endtime``, will be set to
            ``pad_value``.  You may want to also use the ``rmean`` and
            ``taper`` parameters, depending on the nature of the data.

        :type sds_root: string
        :type net_name: string
        :type sta_name: string
        :type comp_name: string
        :type starttime: ``obspy.core.utcdatetime.UTCDateTime`` object,
            optional
        :type endtime: ``obspy.core.utcdatetime.UTCDateTime`` object, optional
        :type rmean: boolean, optional
        :type taper: boolean, optional
        :type pad_value: float, optional

        :raises UserWarning: If there are no data between ``starttime`` and
            ``endtime``

        """

        logging.info("Reading from SDS structure %s %s %s ..." %
                     (net_name, sta_name, comp_name))

        # Get the complete file list. If a directory, get all the filenames.
        filename = os.path.join(sds_root, net_name, sta_name,
                                "%s.D" % comp_name, "*")
        logging.debug("Reading %s between %s and %s" %
                      (filename, starttime.isoformat(), endtime.isoformat()))
        if os.path.isdir(glob.glob(filename)[0]):
            filename = os.path.join(filename, "*")
        file_glob = glob.glob(filename)

        # read header from all files to keep only those within the time limits
        fnames_within_times = []
        for fname in file_glob:
            st_head = stream.read(fname, headonly=True)
            # retrieve first_start and last_end time for the stream
            # without making any assumptions on order of traces
            first_start = st_head[0].stats.starttime
            last_end = st_head[0].stats.endtime
            # find earliest start time and latest end time in stream
            for tr in st_head:
                if tr.stats.starttime < first_start:
                    first_start = tr.stats.starttime
                if tr.stats.endtime > last_end:
                    last_end = tr.stats.endtime
            # add to list if start or end time are within our requested limits
            if (first_start < endtime and last_end > starttime):
                fnames_within_times.append(fname)

        logging.debug("Found %d files to read" % len(fnames_within_times))

        # now read the full data only for the relevant files
        st = Stream()
        for fname in fnames_within_times:
            st_tmp = read(fname, starttime=starttime, endtime=endtime)
            for tr in st_tmp:
                st.append(tr)
        # and merge nicely
        st.merge(method=-1)

        if st.count() > 1:  # There are gaps after sensible cleanup merging
            logging.info("File contains gaps:")
            st.printGaps()

        # apply rmean if requested
        if rmean:
            logging.info("Removing the mean from single traces.")
            st = stream_rmean(st)

        # apply rmean if requested
        if taper:
            logging.info("Tapering single traces.")
            st = stream_taper(st)

        if not pad_value is None:
            try:
                first_tr = st.traces[0]
                # save delta (to save typing)
                delta = first_tr.stats.delta
                if (not starttime is None) and \
                   ((first_tr.stats.starttime - starttime) > delta):
                    logging.debug("Padding with value %f from %s to first\
                                   point in file at %s." %
                                  (pad_value,
                                   starttime.isoformat(),
                                   first_tr.stats.starttime.isoformat()))
                    # find the number of points from starttime to
                    # end of the first trace
                    npts_full_trace = \
                        int(np.floor((first_tr.stats.endtime -
                                      starttime) / delta))+1
                    # find the number of points of the padding section
                    n_pad = npts_full_trace-first_tr.stats.npts
                    # fill the full time range with padd value
                    tr_pad = np.zeros(npts_full_trace)+pad_value
                    # substitute in the data
                    tr_pad[n_pad:] = first_tr.data[:]
                    first_tr.data = tr_pad
                    first_tr.stats.starttime = starttime
                    first_tr.stats.npts = npts_full_trace
                    st.traces[0] = first_tr

                last_tr = st.traces[-1]
                # save delta (to save typing)
                delta = last_tr.stats.delta
                if (not endtime is None) and \
                   ((endtime - last_tr.stats.endtime) > delta):
                    logging.debug("Padding with value %f from last point\
                                   in file at %s to %s." %
                                  (pad_value,
                                   last_tr.stats.endtime.isoformat(),
                                   endtime.isoformat()))
                    # find the number of points from endtime to
                    # start of the last trace
                    npts_full_trace = \
                        int(np.floor((endtime -
                                      last_tr.stats.starttime) / delta))+1
                    # fill the full time range with padd value
                    tr_pad = np.zeros(npts_full_trace)+pad_value
                    # substitute in the data
                    tr_pad[0:last_tr.stats.npts] = last_tr.data[:]
                    last_tr.data = tr_pad
                    last_tr.stats.npts = npts_full_trace
                    st.traces[-1] = last_tr

            except IndexError:
                logging.warning('No data within time limits requested')
                raise UserWarning('No data within time limits requested.')

        try:
            self.stream = st
            self.trace = st.traces[0]
            self.proc = "None"
        except IndexError:
            raise UserWarning('No data within time limits requested.')

    def read_from_file(self, filename, format=None, starttime=None,
                       endtime=None, rmean=False, taper=False, pad_value=None):
        """
        Read waveform data from file.  Multiple traces are merged if they
        overlap exactly or are adjacent.

        :param filename: Waveform filename
        :param format: ``obspy`` format type (e.g. 'SAC', 'mseed'...)
        :param starttime: Start time of data to be read.
        :param endtime: End time of data to be read.
        :param rmean: If ``True`` removes the mean from the data upon reading.
            If data are segmented, the mean will be removed from all segments
            individually.
        :param taper: If ``True`` applies a cosine taper to the data upon
            reading.  If data are segmented, tapers are applied to all segments
            individually.
        :param pad_value: If this parameter is set, points between
            ``starttime`` and the first point in the file, and points between
            the last point in the file and ``endtime``, will be set to
            ``pad_value``.  You may want to also use the ``rmean`` and
            ``taper`` parameters, depending on the nature of the data.

        :type format: string
        :type starttime: ``obspy.core.utcdatetime.UTCDateTime`` object
        :type endtime: ``obspy.core.utcdatetime.UTCDateTime`` object
        :type rmean: boolean
        :type taper: boolean
        :type pad_value: float

        :raises UserWarning: If there are no data between ``starttime`` and
            ``endtime``

        """

        logging.debug("Reading from %s..." % filename)
        if format is not None:
            st = stream.read(filename, format, starttime=starttime,
                             endtime=endtime)
        else:
            st = stream.read(filename, starttime=starttime, endtime=endtime)

        st.merge(method=-1)

        if st.count() > 1:  # There are gaps after intelligent merge
            logging.info("File contains gaps:")
            st.printGaps()

        if rmean:
            st = stream_rmean(st)

        if taper:
            st = stream_taper(st)

        if not pad_value is None:
            try:

                first_tr = st.traces[0]
                # save delta (to save typing)
                delta = first_tr.stats.delta
                if (not starttime is None) and \
                   ((first_tr.stats.starttime - starttime) > delta):
                    logging.debug("Padding with value %f from %s to first\
                        point in file at %s." % (pad_value,
                        starttime.isoformat(),
                        first_tr.stats.starttime.isoformat()))
                    # find the number of points from starttime to
                    # end of the first trace
                    npts_full_trace = \
                        int(np.floor((first_tr.stats.endtime -
                                      starttime) / delta))+1
                    # find the number of points of the padding section
                    n_pad = npts_full_trace-first_tr.stats.npts
                    # fill the full time range with padd value
                    tr_pad = np.zeros(npts_full_trace)+pad_value
                    # substitute in the data
                    tr_pad[n_pad:] = first_tr.data[:]
                    first_tr.data = tr_pad
                    first_tr.stats.starttime = starttime
                    first_tr.stats.npts = npts_full_trace
                    st.traces[0] = first_tr

                last_tr = st.traces[-1]
                # save delta (to save typing)
                delta = last_tr.stats.delta
                if (not endtime is None) and \
                   ((endtime - last_tr.stats.endtime) > delta):
                    logging.debug("Padding with value %f from last point \
                    in file at %s to %s." % (pad_value,
                                             last_tr.stats.endtime.isoformat(),
                                             endtime.isoformat()))
                    # find the number of points from endtime to
                    # start of the last trace
                    npts_full_trace = \
                        int(np.floor((endtime -
                                      last_tr.stats.starttime) / delta))+1
                    # fill the full time range with pad value
                    tr_pad = np.zeros(npts_full_trace)+pad_value
                    # substitute in the data
                    tr_pad[0:last_tr.stats.npts] = last_tr.data[:]
                    last_tr.data = tr_pad
                    last_tr.stats.npts = npts_full_trace
                    st.traces[-1] = last_tr

            except IndexError:
                logging.warning('No data within time limits requested')
                raise UserWarning('No data within time limits requested.')

        try:
            self.stream = st
            self.trace = st.traces[0]
            self.proc = "None"
        except IndexError:
            raise UserWarning('No data within time limits requested.')

    def write_to_file_filled(self, filename, format=None, fill_value=0,
                             rmean=False, taper=False):
        """
        Write waveform to file, after merging and filling blanks with
            ``fill_value``.

        :param filename: Output filename.
        :param format: ``obspy`` format type (e.g. 'SAC', 'mseed'...)
        :param fill_value: Value used to fill in gaps
        :param rmean: Remove the mean before merging.
        :param taper: Apply taper before merging.

        :type filename: string
        :type filename: string
        :type fill_value: float, optional
        :type rmean: bool, optional
        :type taper: bool, optional

        """

        logging.info("Merging traces before writing file %s\n" % filename)
        # make a copy and write that, so as not to merge the file in memory
        st = self.stream.copy()
        if rmean:
            logging.info("Removing mean before merging.")
            st.rmean()
        if taper:
            logging.info("Applying taper before merging.")
            st.taper()
        st.merge(method=1, fill_value=fill_value)
        for tr in st:
            tr.data = tr.data.astype('float32')
            tr.stats.mseed.encoding = 'FLOAT32'

        st.write(filename, format)

    def write_to_file(self, filename, format=None):
        """
        Write waveform to file.

        :param filename: Output filename.
        :param format: ``obspy`` format type (e.g. 'SAC', 'mseed'...)

        :type filename: string
        :type format: string

        """
        st = self.stream

        for tr in st:
            tr.data = tr.data.astype('int32')
            tr.stats.mseed.encoding = 'INT32'
        self.stream.write(filename, format)

    def rmean(self):
        """
        Removes the mean of the stream (iterates over all traces).

        :raises UserWarning: if no data in stream.

        """

        self.stream = stream_rmean(self.stream)
        try:
            self.trace = self.stream[0]
        except IndexError:
            raise UserWarning('No data in stream for rmean')

    def taper(self):
        """
        Applies a cosine taper the stream (iterates over all traces).

        :raises UserWarning: if no data in stream.

        """
        self.stream = stream_taper(self.stream)
        try:
            self.trace = self.stream[0]
        except IndexError:
            raise UserWarning('No data in stream for taper')

    def display(self, title="", filename=""):
        """
        Makes a quick and dirty plot of the waveform.
        If filename is given (and is different from "") then the plot of the
        waveform is written to file, otherwise it is shown on the screen.

        :param title: Title for the plot.
        :param filename: Filename for the plot (format defined by the file
            extension).

        :type title: string
        :type filename: string

        """

        plt.clf()

        plt.title(title)

        # set the axis labels
        plt.xlabel("Time / s")
        if self.proc == "None":
            plt.ylabel("Raw data")
        elif self.proc == "StaLta":
            plt.ylabel("STA/LTA")
        elif self.proc == "Envelope":
            plt.ylabel("Envelope")
        elif self.proc == "Skewness":
            plt.ylabel("Absolute value Skewness")
        elif self.proc == "Kurtosis":
            plt.ylabel("Kurtosis")
        else:
            plt.ylabel("")

        # plot the waveform
        plt.plot(self.t_array, self.values)

        # save to file or display to screen
        if not filename == "":
            plt.savefig(filename)
        else:
            plt.show()

    def bp_filter(self, freqmin, freqmax, zerophase=False,
                  rmean=False, taper=False):
        """
        Apply a band-pass filter to the data.  If data are segmented into
        multiple traces, apply the same filter to all traces.  Calls
        :func:`obspy.signal.filter` to do the filtering.

        :param freqmin: Low frequency corner
        :param freqmax: High frequency corner
        :param zerophase: If ``True`` applies a non-causal bandpass filter.  If
            ``False`` applies a causal bandpass filter.
        :param rmean: If ``True`` remove mean before filtering.
        :param taper: If ``True`` apply taper before filtering.

        :type freqmin: float
        :type freqmax: float
        :type zerophase: bool
        :type rmean: bool
        :type taper: bool

        :raises UserWarning: if no data in stream.

        """

        if zerophase:
            logging.info("Non-causal band-pass filtering single traces : \
                          %.2fHz - %.2fHz\n" % (freqmin, freqmax))
        else:
            logging.info("Causal band-pass filtering single traces : \
                          %.2fHz - %.2fHz\n" % (freqmin, freqmax))

        if rmean:
            self.rmean()

        if taper:
            self.taper()

        for itr in range(self.stream.count()):
            tr = self.stream.traces[itr]
            xs = filter.bandpass(tr.data, freqmin, freqmax,
                                 tr.stats.sampling_rate, zerophase=zerophase)
            tr.data = xs
            self.stream.traces[itr] = tr

        try:
            self.trace = self.stream.traces[0]
        except IndexError:
            raise UserWarning('No data in stream at bp_filter.')

    def resample(self, new_samplerate, resample_type='sinc_best'):
        """
        Applies audio-quality resampling in place. Requires installation of
        ``scikits.samplerate``.

        :param new_samplerate: New sample rate.
        :param resample_type: Can be ``'sinc_best'``, ...

        :type new_samplerate: float
        :type resample_type: string

        """
        old_samplerate = 1/np.float(self.delta)
        ratio = new_samplerate/old_samplerate
        try:
            from scikits.samplerate import resample as sci_resample
            logging.info('Resampling from %.2f to %.2f by ratio %.2f' %
                         (old_samplerate, new_samplerate, ratio))
            for itr in range(self.stream.count()):
                tr = self.stream.traces[itr]
                xs = sci_resample(tr.data, ratio, resample_type, verbose=True)
                tr.data = xs
                tr.stats.sampling_rate = new_samplerate
                self.stream.traces[itr] = tr

        except ImportError:
            logging.warn('Cannot import scikits.samlerate.resample - using\
                          obsy.downsample instead')
            factor = np.int(np.round(1/ratio))
            logging.info('Downsampling from %.2f to %.2f by factor %d' %
                         (old_samplerate, new_samplerate, factor))
            self.stream.decimate(factor=factor, no_filter=True)

    def decimate(self, factor=1):
        """
        Applies ``obspy`` decimation, after applying an anti-aliasing,
        non-causal filter of 0.4*(new sample rate).

        :param factor: Decimation factor.
        :type factor: integer

        """
        self.trace.filter('lowpass',
                          freq=0.4*self.trace.stats.sampling_rate /
                          float(factor), zerophase=True)
        self.trace.downsample(decimation_factor=factor,
                              strict_length=False, no_filter=True)

    def get_snr(self, o_time, left_time, right_time):
        """
        Returns signal-to-noise ratio, where signal = max(abs(signal between
        left_time and right_time)) and noise = median(abs(signal between
        left_time- and otime)).

        :param o_time: center time for SNR calculation
        :param left_time: left time for SNR calculation
        :param right_time: right time for SNR calculation

        :type o_time: UTCDateTime
        :type left_time: UTCDateTime
        :type right_time: UTCDateTime

        """
        tr_signal = self.trace.slice(left_time, right_time)
        signal_value = np.max(np.abs(tr_signal.data))

        tr_noise = self.trace.slice(left_time, o_time)
        noise_value = np.median(np.abs(tr_noise.data))

        if noise_value == 0.0:
            snr = 0
        else:
            snr = signal_value / noise_value

        return snr

    def compute_signature(self):
        """
        Computes a signature for a waveform, made up by the maximum of the
        trace and its sum.

        :rtype: tuple of floats
        :returns: maximum, datasum

        """
        maximum = np.max(self.trace.data)
        datasum = np.sum(self.trace.data)
        return (maximum, datasum)

    def process_envelope(self):
        """
        Runs envelope processing on a waveform. Replaces self.trace and sets
        self.proc to "Envelope'.

        """
        xs = filter.envelope(self.values)
        self.trace.data = xs
        self.proc = "Envelope"

    def process_none(self):
        """
        No processing on a waveform.  Sets self.proc to "None"

        """
        self.proc = "None"

    def process_sta_lta(self, stawin, ltawin):
        """
        Runs classic short to long term average ratio processing on waveform.
        Replaces self.trace and sets self.proc to StaLta.

        :param stawin: length of the short term average window in seconds
        :param ltawin: length of the long term average window in seconds

        """

        nsta = int(stawin/self.delta)
        nlta = int(ltawin/self.delta)
        xs = trigger.classicSTALTA(self.values, nsta, nlta)
        self.trace.data = xs
        self.proc = 'StaLta'

    def take_positive_derivative(self, pre_rmean=False, pre_taper=False,
                                 post_taper=True):
        """
        Takes positive derivative of a stream (used to calculate the positive
        kurtosis gradient).

        :param pre_mean: If ``True`` then remove the mean before taking
            positive gradient
        :param pre_taper: If ``True`` then apply a taper before taking positive
        gradient
        :param post_taper: If ``True`` then apply a taper after taking positive
        gradient.

        :type pre_mean: boolean, optional
        :type pre_taper: boolean, optional
        :type post_taper: boolean, optional

        :raises UserWarning: if no data in stream.

        """

        if pre_rmean:
            self.rmean()

        if pre_taper:
            self.taper()

        self.stream = stream_positive_derivative(self.stream)
        try:
            self.trace = self.stream[0]
        except IndexError:
            raise UserWarning('No data in stream for positive_derivative')

        if post_taper:
            self.taper()

    def process_kurtosis(self, win, recursive=False, pre_rmean=False,
                         pre_taper=False, post_taper=True):
        """
        Processing waveform using kurtosis (from statlib package).
        Calls filters.sw_kurtosis1(), and overwrites the waveform.
        Sets self.prof to 'Kurtosis'

        :param win: length of the window (in seconds) on which to calculate the
                kurtosis
        :param recursive: If ``True`` applies recursive kurtosis calculation
        :param pre_rmean: If ``True`` removes mean of signal before processing.
        :param pre_taper: If ``True`` applies taper to signal before
            processing.
        :param post_taper: If ``True`` applies taper to signal after
            processing.

        :type recursive: boolean, optional
        :type pre_rmean: boolean, optional
        :type pre_taper: boolean, optional
        :type post_taper: boolean, optional

        """

        logging.info("Applying kurtosis to single traces, window = %.2f s\n" %
                     win)

        dt = self.dt

        if pre_rmean:
            self.rmean()

        if pre_taper:
            self.taper()

        # process each trace independently
        for itr in range(self.stream.count()):
            tr = self.stream.traces[itr]
            starttime = tr.stats.starttime
            x = tr.data

            npts = len(tr.data)

            xs = np.zeros(npts)

            if recursive:
                C = 1-dt/float(win)
                xs = rec_kurtosis_old(x, C)
                # Chassande-Mottin style kurtosis
                #C1=dt/float(win)
                #xs=rec_kurtosis(x,C1)
                # smooth xs
                try:
                    xs_filt = smooth(xs)
                except ValueError:
                    xs_filt = xs

            else:
                # run the sliding window kurtosis
                nwin = int(win/dt)
                if len(x) > 3*nwin:
                    xs = sw_kurtosis1(x, nwin)
                    xs_filt = smooth(xs)
                    # fix up the starttime of the trace
                    tr.stats.starttime = starttime + (nwin-1)*dt
                else:
                    xs_filt = xs

            # Save xs values as waveform
            tr.data = xs_filt

            # put trace back into stream
            self.stream.traces[itr] = tr

        # apply taper after kurtosis calculation if required
        if post_taper:
            self.taper()

        # set the process flag
        self.proc = 'Kurtosis'

    def process_gaussian(self, threshold, mu=0.0, sigma=0.1):
        """
        Replace local maxima by a series of dirac and convolve them with a
        gaussian distribution. Overwrites the waveform. Sets self.proc to
        'Gaussian'

        :param threshold: value over which the convolution is applied
        :param mu: expected value of the gaussian distribution
        :param sigma: variance of the gaussian distribution

        :type threshold: float
        :type mu: float
        :type sigma: float

        """

        logging.info("Convolving traces with a gaussian distribution\n")

        dt = self.dt

        y = compute_gauss(dt, mu, sigma)

        # process each trace independently
        for itr in range(self.stream.count()):
            tr = self.stream.traces[itr]

            tr_dirac = np.zeros(len(tr))

            trigs = trigger.triggerOnset(tr.data, threshold, threshold)
            trig_prec = [0, 0]

            for trig in trigs:
                if trig[-1]-trig_prec[0] < 50:
                    trig = [trig_prec[0], trig[-1]]

                istart = trig[0]
                iend = trig[-1]
                if istart != iend:
                    imax = np.argmax(tr.data[istart:iend+1])+istart
                else:
                    imax = istart
                tr_dirac[istart:iend] = 0
                tr_dirac[imax] = np.max(tr.data[imax])

                trig_prec = trig

            try:
                tr.data = np.append(np.convolve(tr_dirac, y, mode='same')[1:],
                                    0)
            except ValueError:
                logging.warn('Empty data segment in gaussian convolution')

            self.stream.traces[itr] = tr

        self.proc = 'Gaussian'


#########################
# Functions
#########################


def stream_rmean(st):
    """
    Removes mean from a stream (iterates over all available traces).

    :param st: Input stream, processed in place
    :type st: An obspy.stream object

    """
    for tr in st:
        t_tr = (tr.data-np.mean(tr.data))
        tr.data = t_tr
    return st


def stream_positive_derivative(st):
    """
    Takes first time derivative of a stream (iterates over all available
    traces) and keep only positive values (set negative values to zero).

    :param st: Input stream, processed in place
    :type st: An obspy.stream object

    """
    for tr in st:
        xs = tr.data
        dt = tr.stats.delta
        try:
            xtemp = np.gradient(xs, dt)
            for i in range(len(xtemp)):
                if xtemp[i] < 0:
                    xtemp[i] = 0
            xs = xtemp
        except IndexError:
            logging.warn('Zero length data segment')
        tr.data = xs
    return st


def stream_taper(st):
    """
    Applies cosine taper to a stream (iterates over all available traces).

    :param st: Input stream, processed in place
    :type st: An obspy.stream object

    """
    for tr in st:
        try:
            # mytaper = cosTaper(tr.stats.npts) # BS
            mytaper = invsim.cosine_taper(tr.stats.npts) # BS
            t_tr = mytaper*(tr.data)
        except ValueError:
            logging.warn('Trace is too short for tapering - multiplying by 0\
            instead')
            t_tr = 0.0*(tr.data)
        tr.data = t_tr
    return st


def read_data_compatible_with_time_dict(filenames, time_dict, starttime,
                                        endtime):
    """
    Reads data that have the same station names as those used as keys to a
    given time dictionary

    :param filename: list of filenames
    :param time_dict: dictionary indexed by station names
    :param starttime: start-time to read data
    :param endtime: end-time to read data

    :type filename: list of strings
    :type time_dict: dictionary
    :type starttime: UTCDateTime
    :type endtime: UTCDateTime

    :raises UserWarning: if sampling is different between the files

    """
    data = {}
    deltas = []

    for filename in filenames:

        st = read(filename, headonly=True)

        delta = st[0].stats.delta
        deltas.append(delta)

        wf_id = st[0].stats.station

        if wf_id in time_dict:
            try:
                wf = Waveform()
                wf.read_from_file(filename, starttime=starttime,
                                  endtime=endtime, pad_value=0)
                # just put the bare data into the data dictionary
                data[wf_id] = wf.values
            except UserWarning:
                logging.warn("No data data found between limits for file %s.\
                              Ignoring station %s." % (filename, wf_id))
        else:
            logging.warn('Station %s not present in time_grid.  Ignoring \
                          station %s.' % (wf_id, wf_id))

    # cheque uniqueness of delta
    u = np.unique(np.array(deltas))
    if len(u) > 1:
        logging.error('Sampling frequency differs between stations.  Fix this\
                       before migrating.')
        for i in range(len(deltas)):
            logging.error('Delta %.4f for file %s' % (deltas[i], filenames[i]))
        raise UserWarning

    return data, u[0]


def compute_gauss(dt, mu, sig):
    """
    Given a time-step, a mean and sigma, returns an array with a Gaussian
    signal from -4*sigma to +4*sigma around the mean.

    :param dt: time-step in seconds
    :param mu: mean of the Gaussian
    :param sig: half-width sigma of the Gaussian

    :type dt: float
    :type mu: float
    :type sig: float

    :rtype: numpy array
    :returns: array with Gaussian signal

    """
    win = 4*sig
    x = np.array(np.arange(-win, win, dt))
    y = 1/(sig*np.sqrt(2*np.pi))*np.exp(-(x-mu)**2/(2*sig**2))
    return y/np.max(y)
