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

from core.module import Base, ConfigOption, Connector
from interface.gated_counter_interface import GatedCounterInterface
import TimeTagger as TT
import time
import numpy as np
import copy


class SITimeTaggerGatedCounter(Base, GatedCounterInterface):

    _modclass = 'SITimeTaggerGatedCounter'
    _modtype = 'hardware'

    # Connector to SITimeTagger hardware module
    # (which connects to the device and keeps reference to it)
    timetagger = Connector(interface='DoesNotMatterWhenThisIsString')

    # Config Options

    # Click channel
    # [list can be passed - clicks on all specified channels will be summed into one logical channel]
    _cfg_click_channel = ConfigOption(name='click_channel', missing='error')

    # Gate channel
    # [positive/negative channel number - count while gate is high/low]
    _cfg_gate_channel = ConfigOption(name='gate_channel', missing='error')

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        # Reference to tagger
        self._tagger = None
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

    def on_activate(self):

        # Pull device reference in from underlying SITimeTagger hardware module
        self._tagger = self.timetagger().reference

        # Log device ID information to demonstrate that connection indeed works
        serial = self._tagger.getSerial()
        model = self._tagger.getModel()
        self.log.info('Got reference to Swabian Instruments TimeTagger device \n'
                      'Serial number: {0}, Model: {1}'
                      ''.format(serial, model))

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

        # # Clear reference to the device
        # self._tagger = None

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

            # save bin_number in internal variable
            self._bin_number = bin_number

        # handle NotImplementedError (typical error, produced by TT functions)
        except NotImplementedError:
            self.log.error('init_counter(): instantiation of CountBetweenMarkers measurement failed')

            # remove reference to the counter measurement
            self._counter = None
            # set status to "void"
            self._set_status(-1)

            return -1

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
