# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware modules for Swabian Instruments Time Tagger.
Implemented interface:
    - slow_counter_interface

=====================================================================================
README

In the case of Swabian Instruments TimeTagger device, each measurement instance
(TT.CountBetweenMarkers, TT.Counter, and so on) can analyze data stream from the same physical device
without interfering with each other. That is, there can be several 'virtual' qudi.hardware modules using
the same physical device.

To implement this, all hardware modules are subclasses of the base class SITimeTaggerBase.

The base class contains protected dictionary
    __device_ref_dict={'physical_device_seria_number': reference_to device}
containing references to each physical device (qudi instance can host multiple SI TimeTaggers simultaneously)
    This dictionary should never be accessed directly from inside an instance to avoid overwriting the references
    and non-local inter-module errors.
    Instead, use self.connect_to_device() method and self._tagger property (see below).

METHODS DESCRIPTION:

    -- Module Activation

    During activation [inside on_activate()], the a specific qudi.hardware module should call
        self.connect_to_device()
    which will take instance's self._serial_str and will check if a reference to a device with this serial number
    is already present in the cls.__device_ref_dict. If is not, this module is the first to use this deice and
    class method cls.add_device(serial_str) will be automatically called to add the device.

    If only one SI TimeTagger device is used within qudi instance, the _cfg_serial_str ConfigOption is optional and can
    be omitted: cls.add_device() will automatically detect the device and self.connect_to_device() will automatically
    update self._serial_str and self._model with the actual values, obtained from the device.

    If multiple SI TimeTagger devices are used within the same qudi instance, config for each hardware module MUST
    specify device's serial number in _cfg_serial_str ConfigOption. If it is not specified, cls.add_device() and
    self.connect_to_device() will add/connect-to the first device they found, thus it is unpredictable which device
    the module will be connected to.


    -- Measurement Initialization

    To create measurement instance, use self._tagger property, which implements read-only access to the device reference
=====================================================================================

Qudi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Qudi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Qudi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

from core.module import Base, Connector, ConfigOption
from interface.slow_counter_interface import SlowCounterInterface, SlowCounterConstraints, CountingMode
import TimeTagger as TT
import time
import copy


class SITimeTaggerSlowCounter(Base, SlowCounterInterface):

    _modclass = 'SITimeTaggerSlowCounter'
    _modtype = 'hardware'

    # Connector to SITimeTagger hardware module
    timetagger = Connector(interface='DoesNotMatterWhenThisIsString')

    # Configuration options
    _cfg_channel_list = ConfigOption(name='click_channel_list', missing='error')
    _cfg_clock_frequency = ConfigOption('clock_frequency', 50, missing='info')
    _cfg_buffer_size = ConfigOption('buffer_size', 100, missing='info')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        # References to the device and to TT.Counter measurement
        self._tagger = None
        self._counter = None

        # Counter parameters
        self._bin_width = 0
        self._bin_width_sec = 0
        self._channel_list = []
        self._buffer_size = 0

    def on_activate(self):

        # Pull device reference in from underlying SITimeTagger hardware module
        self._tagger = self.timetagger().reference

        # Log device ID information to demonstrate that connection indeed works
        serial = self._tagger.getSerial()
        model = self._tagger.getModel()
        self.log.info('Got reference to Swabian Instruments TimeTagger device \n'
                      'Serial number: {0}, Model: {1}'
                      ''.format(serial, model))

        # Set cfg counter channels
        self.set_counter_channels(self._cfg_channel_list)

    def on_deactivate(self):
        self.close_clock()
        self.close_counter()

    def set_up_clock(self, clock_frequency=None, clock_channel=None):
        """
        Sets sample clock frequency for the Counter measurement.


        :param clock_frequency: (float) sample clock frequency. If not given,
                                configuration value is used
        :param clock_channel: ignored (internal timebase is used to generate
                              sample clock signal)

        :return: (int) operation status code: 0 - OK
                                             -1 - Error
        """

        # Use config value, if no clock_frequency is specified
        if clock_frequency is None:
            clock_frequency = self._cfg_clock_frequency

        # Sanity check
        constraints = self.get_constraints()
        if clock_frequency < constraints.min_count_frequency:
            self.log.error('set_up_clock(): too low clock frequency: {0} Hz. \n '
                           'Hardware-defined minimum: {1} Hz'
                           ''.format(clock_frequency, constraints.min_count_frequency))
            return -1
        elif clock_frequency > constraints.max_count_frequency:
            self.log.error('set_up_clock(): too high clock frequency: {0} Hz. \n '
                           'Hardware-defined maximum: {1} Hz'
                           ''.format(clock_frequency, constraints.max_count_frequency))
            return -1

        # Calculate final bin width
        bin_width = int(1e12/clock_frequency)  # in picoseconds, for device
        bin_width_sec = bin_width * 1e-12      # is seconds, for software timing

        # Set new values param to internal variables
        self._bin_width = bin_width
        self._bin_width_sec = bin_width_sec

        return 0

    def set_up_counter(self,
                       counter_channels=None,
                       sources=None,
                       clock_channel=None,
                       counter_buffer=None):
        """
        Configures the actual counter with a given clock.


         (list of int) [optional] list of channels
                     to count clicks on. If not given, config value is used.

        :param counter_buffer: (int) [optional] size of the memory buffer.
                               If not given, config value is used.

        :param counter_channels: ignored
            This argument should not be used. Counter GUI initializes set of plot curves
            self.curves during its on_activate() method. It basically calls
            counter_hardware.get_counter_channels() and uses this list to init self.curves
            Only after that user can click "Start" button, which will call set_up_counter().
            And since GUI already has inited set of curves, set of channels must not be
            modified here! It will case GUI to fail.

        :param sources: ignored
        :param clock_channel: ignored

        :return: (int) operation status code: 0 - OK
                                             -1 - Error
        """

        # Set counter channels
        if counter_channels is not None:
            channel_list = counter_channels
        else:
            channel_list = self._cfg_channel_list
        # apply counter channel change
        self.set_counter_channels(channel_list=channel_list)

        # Set buffer size
        if counter_buffer is not None:
            buffer_size = counter_buffer
        else:
            buffer_size = self._cfg_buffer_size
        # sanity check:
        if not isinstance(buffer_size, int) or buffer_size<=0:
            self.log.error('set_up_counter(): invalid parameter value counter_buffer = {}.'
                           'This parameter must be a positive integer.'
                           ''.format(buffer_size))
            return -1
        # apply buffer size change
        self._buffer_size = buffer_size

        # Create instance of Counter measurement
        try:
            self._counter = TT.Counter(
                tagger=self._tagger,
                channels=self._channel_list,
                binwidth=self._bin_width,
                n_values=self._buffer_size
            )
        # handle initialization error (TT functions always produce NotImplementedError)
        except NotImplementedError:
            self._counter = None
            self.log.error('set_up_counter(): failed to instantiate TT.Counter measurement')
            return -1

        # Start Counter
        # (TT.Counter measurement starts running immediately after instantiation,
        # so it is necessary to erase all counts collected since instantiation)
        self._counter.stop()
        self._counter.clear()
        self._counter.start()

        return 0

    def close_clock(self):
        """
        Closes the clock.

        :return: (int) error code: 0 - OK
                                  -1 - Error
        """

        self._bin_width = 0
        self._bin_width_sec = 0

        return 0

    def close_counter(self):
        """
        Closes the counter and cleans up afterwards.

        :return: (int) error code: 0 - OK
                                  -1 - Error
        """

        # Try stopping and clearing TT.Counter measurement
        try:
            self._counter.stop()
            self._counter.clear()
        # Handle the case of exception in TT function call (NotImplementedError)
        # and the case of self._counter = None (AttributeError)
        except (NotImplementedError, AttributeError):
            pass

        # Remove reference to the counter
        self._counter = None

        # Clear counter parameters
        self._buffer_size = []

        # Do not clear channel list:
        # Counter GUI inits its list of curves self.curves
        # by calling counter_hardware.get_counter_channels() before
        # calling counter_hardware.set_up_counter()
        # If one clears _channel_list here, GUI will fail at the next
        # "Start" button click after reloading.
        #
        # self._channel_list = []

        return 0

    def get_counter(self, samples=1):
        """
        Returns the current counts per second of the counter.

        :param samples: (int) [optional] number of samples to read in one go
                        (default is one sample)

        :return: numpy.array((samples, uint32), dtype=np.uint32)
        array of count rate [counts/second] arrays of length samples for each click channel
        Empty array [] is returned in the case of error.
        """

        # Sanity check: samples has valid value
        if samples != 1:
            if not isinstance(samples, int) or samples <= 0:
                self.log.error('get_counter(): invalid argument samples={0}. This argument must be a positive integer'
                               ''.format(samples))
                return []

        # MORE SOPHISTICATED VERSION
        # (WORKS TOO SLOWLY: PROBABLY BECAUSE OF SLOW INTEGER DIVISION OF LARGE INTEGERS)
        #
        # start_time = time.time()
        # while time.time() - start_time < self._timeout:
        #     new_complete_bins = self._counter.getCaptureDuration() // self._bin_width - self._last_read_bin
        #
        #     self._overflow = new_complete_bins
        #     # self.log.error('new_complete_bins = {}'.format(new_complete_bins))
        #
        #     if new_complete_bins < samples:
        #         time.sleep(self._bin_width_sec/2)
        #         continue
        #     elif new_complete_bins == samples:
        #         self._last_read_bin += new_complete_bins
        #         break
        #     else:
        #         # self.log.warn('Counter is overflowing. \n'
        #         #               'Software pulls data in too slowly and counter bins are too short, '
        #         #               'such that some bins are lost. \n'
        #         #               'Try reducing sampling rate or increasing oversampling')
        #         self._last_read_bin += new_complete_bins
        #         break

        # Wait for specified number of samples (samples parameter) to be accumulated
        #
        # This approach is very naive and is more or less accurate for
        # clock frequency below 50 Hz.
        #
        # For higher frequencies, the actual time sampling interval is determined
        # by software delays (about 1 ms). Counter measurement overflows
        # (most of the samples are over-written before software reads them in)
        # but does not fail. The only problem here is that time axis on the count-trace
        # graph is no longer accurate:
        # the difference between consecutive tick labels is much smaller than the actual
        # time interval between measured samples (about 1 ms)
        time.sleep(samples * self._bin_width_sec)

        # read-in most recent 'samples' samples
        try:
            count_array = self._counter.getData()[:, -samples:]
        except NotImplementedError:
            self.log.error('get_counter() reading operation failed')
            return []
        except AttributeError:
            self.log.error('get_counter(): counter was not initialized')
            return []

        # Calculate count rate [count/sec]
        count_rate_array = count_array / self._bin_width_sec

        return count_rate_array

    def get_constraints(self):
        """
        Retrieve the hardware constrains from the counter device.

        :return: (SlowCounterConstraints) object with constraints for the counter
        """

        constraints = SlowCounterConstraints()
        # TODO: check values
        constraints.min_count_frequency = 1
        constraints.max_count_frequency = 10e9
        constraints.max_detectors = 8
        constraints.counting_mode = [CountingMode.CONTINUOUS]

        return constraints

    def get_counter_channels(self):
        """
        Returns the list of click channel numbers.

        :return: (list of int) list of click channel numbers
        """

        return copy.deepcopy(self._channel_list)

    def set_counter_channels(self, channel_list=None):
        """
        Set click channel list.

        Notice that this method only modifies internal variable _channel_list.
        To apply the change to the counter, one has to call set_up_counter() again.


        :param channel_list: (list of int) list of channels to count clicks on

        :return: (list of int) actual list of click channels
        """

        if channel_list is None:
            return self.get_counter_channels()

        # Sanity check:
        all_channels = self._get_all_channels()
        if not set(channel_list).issubset(set(all_channels)):
            self.log.error('set_counter_channels(): requested list of channels is invalid: '
                           'some channels are not present on the device.'
                           'requested list: {0} \n'
                           'available channels: {1}'
                           ''.format(channel_list, all_channels))
            return self.get_counter_channels()

        # Apply changes to internal variable self._channel_list
        self._channel_list = channel_list
        # Sort channel numbers, such that channel order does not depend
        # on order of numbers in the config file
        self._channel_list.sort()

        return self.get_counter_channels()

    def _get_all_channels(self):
        """
        Return list of all channels available on the device.

        Positive/negative values correspond to rising/falling edge detection.
        For example:
            1 means 'rising edge on connector 1'
            -1 means 'falling edge on connector 1


        :return: (list of int) list of all available channel numbers,
                               including edge sign.
        """

        try:
            available_channel_tuple = list(
                self._tagger.getChannelList(TT.TT_CHANNEL_RISING_AND_FALLING_EDGES)
            )
        # handle exception in the call (TT functions normally produce NotImplementedError)
        except NotImplementedError:
            self.log.error('_get_all_channels(): communication with the device failed')
            return []
        # handle the case of self._tagger = None
        except AttributeError:
            self.log.error('_get_all_channels(): _tagger is None. Initialize device first')
            return []

        return list(available_channel_tuple)
