# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware modules for Swabian Instruments Time Tagger.
Implemented interfaces:
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

from core.module import Base, ConfigOption
from interface.slow_counter_interface import SlowCounterInterface, SlowCounterConstraints, CountingMode
from interface.gated_counter_interface import GatedCounterInterface
import TimeTagger as TT
import time
import numpy as np
import copy


class SITimeTaggerBase(Base):

    # Set the following channel numbering scheme:
    #   rising edge channels: 1, ..., 8
    #   falling edges channels: -1, ..., -8
    #   For details see Time Tagger documentation: "Channel Number Schema 0 and 1"
    TT.setTimeTaggerChannelNumberScheme(TT.TT_CHANNEL_NUMBER_SCHEME_ONE)

    # Class-wide dictionary, containing references to all SI TimeTagger devices, used by any of the modules
    #   keys are serial number strings, values - references to device objects
    _device_ref_dict = dict()

    # Config Options
    # Serial number of the device
    _cfg_serial_str = ConfigOption(name='serial_number_string', missing='error')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.log.debug('SITimeTaggerBase.__init__()')

        # Internal variables
        self._serial_str = ''  # serial number of the device, to which this module is connected

    def on_activate(self):
        # Populate serial number string attribute
        self._serial_str = self._cfg_serial_str

        self.log.debug('on_activate(): self._tagger = {}'.format(self._tagger))
        self.log.debug('on_activate(): SITimeTaggerBase._device_ref_dict = {}'.format(SITimeTaggerBase._device_ref_dict))

        # Connect to the device with serial number self._serial_str
        op_status = self.connect_to_device()
        if op_status < 0:
            self.log.error('on_activate(): connection to device with serial "{0}" failed'
                           ''.format(self._serial_str))
            return

        # Log device ID information to demonstrate that connection indeed works
        serial = self._tagger.getSerial()
        model = self._tagger.getModel()
        self.log.info('Successfully connected to Swabian Instruments TimeTagger device \n'
                      'Serial number: {0}, Model: {1}'
                      ''.format(serial, model))

    def on_deactivate(self):
        self._serial_str = ''

    @property
    def _tagger(self):
        """
        This property implements read-only access to the class-wide __device_ref_dict
        (more specifically, only to the reference of the device, to which this module is connected).

        To understand which device is the module connected to, the property accesses self._serial_str attribute.

        Device reference is returned if self._serial_str is on the dictionary key list. Otherwise None is returned.
        """

        serial_str = self._serial_str
        if serial_str in SITimeTaggerBase._device_ref_dict.keys():
            return SITimeTaggerBase._device_ref_dict[serial_str]
        else:
            return None

    # @classmethod
    @staticmethod
    def add_device(serial_str):
        """
        Connect to device with serial number serial_str.

        :param serial_str: serial number of the device

        :return: (int) operation_status: 0 - OK
                                        -1 - Error
        """

        tagger = TT.createTimeTagger(serial_str)

        if tagger is None:
            # TODO: add actual error check. Test in Jupyter notebook showed that the above function call
            # TODO: just freezes if invalid serial number string is passed
            return -1
        else:
            # Add the reference to the class-wide dictionary
            SITimeTaggerBase._device_ref_dict[serial_str] = tagger
            # Reset device
            tagger.reset()

            return 0

    @staticmethod
    def test_add_something_to_class_dict(name, value):
        SITimeTaggerBase._device_ref_dict[name] = value

    def connect_to_device(self):
        """
        Connect to tagger is necessary.

        This method determines if __device_ref_dict contains a reference
        to the device with serial number self._serial_str. If not,
        class method cls.add_device() is called to connect to the new device.

        Always call this method in the very beginning of on_activate()


        :return: (int) operation status: 0 - OK
                                        -1 - Error
        """

        # Check if the device is already present in the class-wide dictionary by calling self._tagger property
        # If not, call cls.add_device()
        if self._tagger is None:
            op_status = self.add_device(serial_str=self._serial_str)

            # Handle possible errors
            if op_status < 0:
                self.log.error('connect_to_device(): failed to connect to the device [self._serial_str={0}]'
                               ''.format(self._serial_str))
                return -1

        return 0


class SITimeTaggerSlowCounter(SITimeTaggerBase, SlowCounterInterface):

    _modclass = 'SITimeTaggerSlowCounter'
    _modtype = 'hardware'

    _cfg_channel_list = ConfigOption(name='click_channel_list', missing='error')
    _cfg_clock_frequency = ConfigOption('clock_frequency', 200, missing='info')
    _cfg_buffer_size = ConfigOption('buffer_size', 100, missing='info')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        self._counter = None

        self._bin_width = 0
        self._bin_width_sec = 0
        self._channel_list = []
        self._buffer_size = 0

        self._timeout = 10

        self._last_read_bin = 0
        self._overflow = 0

    def on_activate(self):

        super().on_activate()

        # Counter channels
        # sanity check:
        if not set(self._cfg_channel_list).issubset(set(self._get_all_channels())):
            self.log.error('')
            return
        self._channel_list = self._cfg_channel_list

    def on_deactivate(self):
        super().on_deactivate()
        self.close_clock()
        self.close_counter()

    def set_up_clock(self, clock_frequency=None, clock_channel=None):
        """ Sets sample clock frequency for the Counter measurement.

        @param float clock_frequency: if defined, this sets the frequency of the clock
        @param string clock_channel: ignored (internal timebase is used to generate sample clock signal)

        @return int: error code (0:OK, -1:error)
        """

        # Bin_width
        if clock_frequency is None:
            clock_frequency = self._cfg_clock_frequency
        # sanity check
        constraints = self.get_constraints()
        if clock_frequency < constraints.min_count_frequency:
            self.log.error('set_up_clock(): too low count frequency: {0} Hz. \n '
                           'Hardware-defined minimum: {1} Hz'
                           ''.format(clock_frequency, constraints.min_count_frequency))
            return -1
        elif clock_frequency > constraints.max_count_frequency:
            self.log.error('set_up_clock(): too high count frequency: {0} Hz. \n '
                           'Hardware-defined maximum: {1} Hz'
                           ''.format(clock_frequency, constraints.max_count_frequency))
            return -1
        bin_width = int(1e12/clock_frequency)

        # Store new param values into main param dictionary
        self._bin_width = bin_width
        self._bin_width_sec = bin_width * 1e-12

        return 0

    def set_up_counter(self,
                       counter_channels=None,
                       sources=None,
                       clock_channel=None,
                       counter_buffer=None):
        """ Configures the actual counter with a given clock.

        @param list(str) counter_channels: optional, physical channel of the counter

        @param int counter_buffer: optional, a buffer of specified integer
                                   length, where in each bin the count numbers
                                   are saved.

        Ignored arguments:
        @param list(str) sources:
        @param str clock_channel:

        @return int: error code (0:OK, -1:error)

        There need to be exactly the same number sof sources and counter channels and
        they need to be given in the same order.
        All counter channels share the same clock.
        """

        # Handle parameters
        # Counter channels
        if counter_channels is not None:
            channel_list = counter_channels
        else:
            channel_list = self._cfg_channel_list
        # sanity check:
        if not set(channel_list).issubset(set(self._get_all_channels())):
            self.log.error('')
            return -1

        # Buffer size
        if counter_buffer is not None:
            buffer_size = counter_buffer
        else:
            buffer_size = self._cfg_buffer_size
        # sanity check:
        if buffer_size <= 0:
            self.log.error('')
            return -1

        # Create instance of Counter measurement
        counter_ref = TT.Counter(
            tagger=self._tagger,
            channels=channel_list,
            binwidth=self._bin_width,
            n_values=buffer_size
        )
        if counter_ref is None:
            self.log.error('')
            return -1

        # Save reference and parameters
        self._counter = counter_ref
        self._channel_list = channel_list
        self._buffer_size = buffer_size

        # Start Counter, set current time mark to 0
        self._counter.start()
        self._last_read_bin = 0
        self._counter.clear()

        return 0

    def close_clock(self):
        """ Closes the clock and cleans up afterwards.

        @return int: error code (0:OK, -1:error)
        """
        if self._counter is not None:
            self._counter.stop()
            self._counter.clear()

        self._bin_width = 0
        self._bin_width_sec = 0
        self._last_read_bin = 0

        return 0

    def close_counter(self):
        """ Closes the counter and cleans up afterwards.

        @return int: error code (0:OK, -1:error)
        """
        if self._counter is not None:
            self._counter.stop()
            self._counter.clear()

        self._channel_list = []
        self._buffer_size = []
        self._last_read_bin = 0
        self._counter = None

        return 0

    def get_counter(self, samples=1):
        """ Returns the current counts per second of the counter.

        @param int samples: if defined, number of samples to read in one go

        @return numpy.array((n, uint32)): the photon counts per second for n channels
        """

        # Sanity checks
        if samples != 1:
            if not isinstance(samples, int) or samples <= 0:
                self.log.error('get_counter(): invalid argument samples={0}. This argument must be a positive integer'
                               ''.format(samples))
                return np.zeros(
                    shape=(
                        len(self._channel_list),
                        samples
                    ),
                    dtype=np.uint32
                )

        if self._counter is None:
            self.log.error('get_counter(): Counter is not running')
            return np.zeros(
                shape=(
                    len(self._channel_list),
                    samples
                ),
                dtype=np.uint32
            )

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

        time.sleep(samples * self._bin_width_sec)

        return self._counter.getData()[:, -samples:] / self._bin_width_sec

    def get_constraints(self):
        """ Retrieve the hardware constrains from the counter device.

        @return SlowCounterConstraints: object with constraints for the counter
        """
        constraints = SlowCounterConstraints()
        # TODO: check values
        constraints.min_count_frequency = 1
        constraints.max_count_frequency = 10e9
        constraints.max_detectors = 8
        constraints.counting_mode = [CountingMode.CONTINUOUS]

        return constraints

    def get_counter_channels(self):
        """ Returns the list of counter channel names.

        @return list(str): channel names

        Most methods calling this might just care about the number of channels, though.
        """

        return copy.deepcopy(self._channel_list)

    def _get_all_channels(self):

        return list(
            self._tagger.getChannelList(
                TT.TT_CHANNEL_RISING_AND_FALLING_EDGES
            )
        )


class SITimeTaggerGatedCounter(SITimeTaggerBase, GatedCounterInterface):

    _modclass = 'SITimeTaggerGatedCounter'
    _modtype = 'hardware'

    # Config Options

    # Serial number string
    # [defined in SITimeTaggerBase]

    # Click channel
    # [list can be passed - clicks on all specified channels will be summed into one logical channel]
    _cfg_click_channel = ConfigOption(name='click_channel', missing='error')

    # Gate channel
    # [positive/negative channel number - count while gate is high/low]
    _cfg_gate_channel = ConfigOption(name='gate_channel', missing='error')

    _test_dict = {}
    _test_class_var = 0

    def __init__(self, config, **kwargs):

        self.log.debug('SITimeTaggerGatedCounter.__init__()')

        super().__init__(config=config, **kwargs)

        # Reference to the TT.CountBetweenMarkers measurement instance
        self._counter = None

        # Channel assignments
        self._click_channel = 0
        self._gate_channel = 0

        # Number of count bins:
        #   length of returned 1D count array, the expected number of gate pulses,
        #   the size of allocated memory buffer.
        # Must be given as argument of init_counter() call
        self._bin_number = 0

        # Module status code
        #  -1 "void"
        #   0 "idle"
        #   1 "in_progress"
        #   2 "finished"
        self._status = -1

    @staticmethod
    def edit_test_dict(name, value):
        SITimeTaggerGatedCounter._test_dict[name] = value
        # self.__class__._test_dict[name] = value

    @classmethod
    def test_method(cls, value):
        cls._test_class_var = value

    def on_activate(self):
        super().on_activate()

        # Reset internal variables
        self._counter = None  # reference to the TT.CountBetweenMarkers measurement instance
        self._set_status(-1)  # set counter status to "void"
        self._bin_number = 0  # number of count bins

        # Set channel assignment
        self.set_channel_assignment(
            click_channel=self._cfg_click_channel,
            gate_channel=self._cfg_gate_channel
        )

        # Once on_activate() call is complete,
        # the counter is ready to be initialized by the above-lying logic though init_counter() call

    def on_deactivate(self):
        super().on_deactivate()

        # Close TT.CountBetweenMarkers instance
        self.close_counter()

        # Reset internal variables
        self._bin_number = 0

        self._click_channel = 0
        self._gate_channel = 0

    # ------------------------------------------------------

    def init_counter(self, bin_number):
        # Close existing counter, if it was initialized before
        # (this method will not fail even if there is nothing to close)
        self.close_counter()

        # Instantiate counter measurement
        # handle NotImplementedError (typical error, produced by TT functions)
        try:
            self._counter = TT.CountBetweenMarkers(
                tagger=self._tagger,
                click_channel=self._click_channel,
                begin_channel=self._gate_channel,
                end_channel=-self._gate_channel,
                n_values=bin_number
            )
            # set status to "idle"
            self._set_status(0)

        except NotImplementedError:
            self.log.error('init_counter(): instantiation of CountBetweenMarkers measurement failed')

            # remove reference to the counter measurement
            self._counter = None
            # set status to "void"
            self._set_status(-1)

            return -1

        # save bin_number in internal variable
        self._bin_number = bin_number

        # Prepare counter to be started by start_counting()
        # (CountBetweenMarkers measurement starts running immediately after instantiation,
        # so it is necessary to stop it and erase all counts collected between instantiation and stop() call)
        self._counter.stop()
        self._counter.clear()

        return 0

    def start_counting(self):

        if self.get_status() == -1:
            self.log.error('start_counting(): counter is in "void state - it ether was not initialized '
                           'or was closed. Initialize it by calling init_counter()"')
            return -1

        # Try stopping and restarting counter measurement
        # handle NotImplementedError (typical error, produced by TT functions)
        try:
            self._counter.stop()  # does not fail even if the measurement is not running
            self._counter.clear()
            self._counter.start()

            # set status to "in_progress"
            self._set_status(1)

            return 0

        except NotImplementedError:
            # Since stop() and clear() methods are very robust,
            # this part is only executed it two cases:
            #   -- self._counter is None
            #   -- counter is totally broken
            #
            # If reference is broken, it makes sense to close counter and
            # if reference is None, close_counter() does not fail anyways
            # That is why close_counter() is called.
            self.close_counter()

            self.log.error('start_counting(): call failed. Counter was closed. \n'
                           'Re-initialize counter by calling init_counter() again')
            return -1

    def terminate_counting(self):

        # Try stopping and clearing counter measurement
        # handle NotImplementedError (typical error, produced by TT functions)
        try:
            # stop counter, clear count array
            self._counter.stop()
            self._counter.clear()

            # set status to "idle"
            self._set_status(0)
            return 0

        except:
            # Since stop() and clear() methods are very robust,
            # this part is only executed it two cases:
            #   -- self._counter is None
            #   -- counter is totally broken
            #
            # If reference is broken, it makes sense to close counter and
            # if reference is None, close_counter() does not fail anyways
            # That is why close_counter() is called.
            self.close_counter()

            self.log.error('terminate_counting(): call failed. Counter was closed')
            return -1

    def get_status(self):

        # Check that counter measurement was initialized and that the connection works
        # by calling isRunning()
        #  -- if self._counter is None or if connection is broken, call will rise some exception
        #     in this case "void" status should be set
        #  -- if counter was initialized and connection works, it will return successfully
        #     and further choice between "idle" and "in_progress" should be made
        try:
            self._counter.isRunning()
        except:
            # status will be set to "void" during close_counter() call
            # in addition, this cleanup is needed if connection is broken
            self.close_counter()

        # Handle "in_progress" status
        #   This status means that measurement was started before.
        #   Now one needs to check if it is already finished or not.
        #   If measurement is complete, change status to "finished".
        if self._status == 1:
            if self._counter.ready():
                self._status = 2

        return copy.deepcopy(self._status)

    def get_count_array(self, timeout=-1):

        # If current status is "in_progress",
        # wait for transition to some other state:
        #   "finished" if measurement completes successfully,
        #   "idle" if measurement is terminated,
        #   "void" if counter breaks
        start_time = time.time()
        sleep_time = timeout/100
        while self.get_status() == 1:
            # stop waiting if timeout elapses
            if time.time()-start_time > timeout:
                break
            time.sleep(sleep_time)

        # Analyze current status and return correspondingly
        status = self.get_status()

        # return data only in the case of "finished" state
        if status == 2:
            count_array = np.array(
                self._counter.getData(),
                dtype=np.uint32
            )
            return count_array

        # return empty list for all other states ("in_progress", "idle", and "void")
        else:
            if status == 1:
                self.log.warn('get_count_array(): operation timed out, but counter is still running. \n'
                              'Try calling get_count_array() later or terminate process by terminate_counting().')
            elif status == 0:
                self.log.warn('get_count_array(): counter is "idle" - nothing to read')
            else:
                self.log.error('get_count_array(): counter broke and was deleted')

            return []

    def close_counter(self):

        # Try to stop and to clear TT.CountBetweenMarkers measurement instance
        try:
            self._counter.stop()
            self._counter.clear()
        except:
            pass

        # Remove reference, set status to "void"
        self._counter = None
        self._set_status(-1)

        return 0

    # ------------------------------------------------------

    def _set_status(self, new_status):
        """ Method to set new status in a clean way.

        This method compares the requested new_status with current status
        and checks if this transition is possible. If transition is possible,
        the change is applied to self._status. Otherwise, no status change
        is applied, -1 is returned, and error message is logged.


        :param new_status: (int) new status value
                            -1 - "void"
                             0 - "idle"
                             1 - "in_progress"
                             2 - "finished"

        :return: (int) operation status code:
                 0 - OK, change was accepted and applied
                -1 - Error, impossible transition was requested, no state change
                     was applied
        """

        # Transition to "void" is always possible
        # by calling close_counter()
        if new_status == -1:
            self._status = -1
            return 0

        # Transition to "idle" is possible from
        #   "void" by calling init_counter()
        #   "in_progress" by calling terminate_counting()
        if new_status == 0:
            if self._status==-1 or self._status==1:
                self._status = 0
                return 0
            else:
                self.log.error('_set_status(): transition to new_status={0} from self._status={1} is impossible. \n'
                               'Counter status was not changed.'
                               ''.format(new_status, self._status))
                return -1

        # Transition to "in_progress" is possible from
        #   "idle" by calling start_counting()
        #   "finished" by calling start_counting()
        if new_status == 1:
            if self._status==0 or self._status==2:
                self._status = 1
                return 0
            else:
                self.log.error('_set_status(): transition to new_status={0} from self._status={1} is impossible. \n'
                               'Counter status was not changed.'
                               ''.format(new_status, self._status))
                return -1

        # Transition to "finished" is only possible from "in_progress"
        if new_status == 2:
            if self._status == 1:
                self._status = 2
                return 0
            else:
                self.log.error('_set_status(): transition to new_status={0} from self._status={1} is impossible. \n'
                               'Counter status was not changed.'
                               ''.format(new_status, self._status))
                return -1

    def get_channel_assignment(self):
        """
        Returns dictionary containing current channel assignment:
            {
                'click_channel': (int) click_channel_number_including_edge_sign
                'gate_channel': (int) gate_channel_number_including_edge_sign
            }

        :return: dict('click_channel': _, 'gate_channel': _)
        """

        click_channel = copy.deepcopy(self._click_channel)
        gate_channel = copy.deepcopy(self._gate_channel)

        return {'click_channel': click_channel, 'gate_channel': gate_channel}

    def set_channel_assignment(self, click_channel=None, gate_channel=None):
        """Sets click channel and and gate channel.

        This method only changes internal variables
        self._click_channel and self._gate_channel.
        To apply the channel update, call  init_counter() again.


        :param click_channel: (int|list of int) click channel number
                              positive/negative values - rising/falling edge detection
                              if list is given, clicks on all specified channels
                              will be merged into one logic channel

        :param gate_channel: (int) channel number
                             positive/negative - count during high/low gate level

        :return: (dict) actually channel assignment:
                        {
                            'click_channel': (int) click_chnl_num,
                            'gate_channel': (int) gate_chnl_num
                        }
        """

        if click_channel is not None:
            # for convenience bring int type of input to list of int
            if isinstance(click_channel, list):
                click_channel_list = click_channel
            elif isinstance(click_channel, int):
                click_channel_list = [click_channel]
            else:
                # unknown input type
                self.log.error('set_channel_assignment(click_channel={0}): invalid argument type'
                               ''.format(click_channel))
                return self.get_channel_assignment()

            # sanity check: all requested channels are available on the device
            all_channels = self.get_all_channels()
            for channel in click_channel_list:
                if channel not in all_channels:
                    self.log.error('set_channel_assignment(): '
                                   'click_channel={0} - this channel is not available on the device'
                                   ''.format(click_channel))
                    return self.get_channel_assignment()

            # If several channel numbers were passed, create virtual Combiner channel
            if len(click_channel_list) > 1:
                combiner = TT.Combiner(
                    tagger=self._tagger,
                    channels=click_channel_list
                )
                # Obtain int channel number for the virtual channel
                click_channel_list = [combiner.getChannel()]

            # Set new value for click channel
            self._click_channel = int(click_channel_list[0])

        if gate_channel is not None:

            # sanity check: channel is available on the device
            if gate_channel not in self.get_all_channels():
                self.log.error('set_channel_assignment(): '
                               'gate_channel={0} - this channel is not available on the device'
                               ''.format(gate_channel))
                return self.get_channel_assignment()

            # Set new value for gate channel
            self._gate_channel = int(gate_channel)

        return self.get_channel_assignment()

    def get_all_channels(self):
        """Returns list of all channels available on the device,
        including edge type sign.

        Positive/negative numbers correspond to detection of rising/falling edges.
        For example:
            1 means 'rising edge on connector 1'
            -1 means 'falling edge on connector 1


        :return: (list of int) list of channel numbers including edge sign.
                Example: [-8, -7, -6, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 6, 7, 8]
                Empty list is returned in the case of error.
        """

        # Sanity check: check that connection to the device was established
        if self._tagger is None:
            self.log.error('get_all_channels(): not connected to the device yet')
            return []

        channel_list = list(
            self._tagger.getChannelList(TT.TT_CHANNEL_RISING_AND_FALLING_EDGES)
        )
        return channel_list
