# -*- coding: utf-8 -*-

"""
This file contains the Qudi hardware interface for gated counter.

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

import abc
from core.util.interfaces import InterfaceMetaclass


class GatedCounterInterface(metaclass=InterfaceMetaclass):
    """
    This is a base class for single-channel gated counter hardware modules.

    Counter is expected to return a 1D array of counts of fixed length,
    which must be specified during init_counter() call.

    If multiple independent logic click channels are used on the same device,
    each channel have to be considered as a separate virtual device,
    represented by its own instance of hardware module.
    """

    _modtype = 'interface'
    _modclass = 'PulserInterface'

    @abc.abstractmethod
    def init_counter(self, bin_number):
        """
        Initialize gated counter

        This method creates gated counter, which will counts clicks within
        bin_number sequential gate pulses. After successful call of this
        method, the counter is in state "idle" and is ready to be started by
        calling start_counting().


        :param bin_number: (int) number of count bins
                                (number of gate pulses to wait for)

        :return: (int) operation status code:
                0 - OK, status is "idle" and counter is ready to be started
               -1 - Error, status is "void" and counter has to be re-initialized
        """

        pass

    @abc.abstractmethod
    def start_counting(self):
        """
        Start counting clicks

        After call of this method, counter starts responding to gate pulses:
        clicks within subsequent gate pulses are counted and stored in count_array

        This method moves counter to "in_progress" state
        Once bin_number gate pulses are received, counter returns to "idle" state.

        This method will erase any count data still remaining in count_array.
        Make sure to read data out by get_count_array() before calling this method.

        If counter is still running since the last call of start_counting()
        (status is "in_progress"), this method will automatically call
        terminate_counting() to terminate existing process.


        :return: (int) operation status code:
                0 - OK, counter is running
               -1 - Error, counting was not started. Use get_status() to check
                counter status. If status is "void," counter has to be re-initialized
                by calling init_counter() again.
        """

        pass

    @abc.abstractmethod
    def terminate_counting(self):
        """
        Stop counting without waiting for all bin_number gate pulses
        to arrive.

        If counter is "in_progress", this method will terminate counting
        process and return counter to "idle" state.

        All clicks, accumulated since the last call of start_counting(),
        will be erased.


        :return: operation status code:
                 0 - OK
                -1 - Error (most probably counter has to be re-initialized)
        """

        pass

    @abc.abstractmethod
    def get_status(self):
        """
        Returns status of the counter

        -1 - "void" counter crashed or was not initialized.
             It has to be (re)initialized by calling init_counter()

         0 - "idle" - counter is ready to be started by calling start_counting().
             If counting process was started before, it is now complete and
             accumulated counts can be obtained by calling get_count_array()

         1 - "in_progress" - counter is accumulating clicks right now.
             Counter will return to "idle" state once it receives bin_number
             gate pulses.

             No data can be read out until this process is finished
             If get_count_array() is called in this state, it will be blocked and
             will return only after array accumulation is complete.

             Counter can be interrupted/closed by calling terminate_counting() or
             close_counter() to bring it to "idle" or "void" state.

         2 - "finished" - counter has finished accumulating counts.
             Now get_count_array() will return accumulated array

        :return: (int) counter status code
        """

        pass

    @abc.abstractmethod
    def get_count_array(self, timeout=-1):
        """
        Get count array, accumulated since the last call of start_counting()

        This method returns 1D array of length bin_number. Each element is a sum
        of clicks, received during the corresponding gate pulse. The first element
        corresponds to the first gate pulse received after start_counting() call.

        If click accumulation is complete (status is "idle" again), this method
        will return immediately. Otherwise (status is "in_progress") the call
        will be blocked and will not return until all bin_number gate pulses are
        received.

        To avoid indefinitely long blocking, one can specify timeout in seconds.
        If accumulation is not complete before timeout elapses, the method returns
        empty list -1 operation status code. Notice that in this case, counting
        process is not disturbed and continues to run. One can call get_count_array()
        later or call terminate_counting() to stop accumulation.
        To remove time limit, set timeout to -1.
        Attempt to read will be performed every abs(timeout/100) seconds.


        :param timeout: (int) operation timeout in seconds
                        (0 for "return immediately", -1 for "infinite")

        :return: np.array(bin_number, dtype=np.uint32) count_array
                 Empty list [] is returned if there is no data to read, if operation
                 timed out, or if counter broke


                tuple(
                    int operation_status_code,
                    np.array(bin_number, dtype=np.uint32) count_array
                 )

                 operation_status_code: 0 - OK, full array was returned
                                       -1 - Error, empty list was returned
                 count_array: counts, accumulated since the last start_counting() call
                              empty array is returned if operation times out
        """

        pass

    @abc.abstractmethod
    def close_counter(self):
        """
        Close and clean-up counter.

        Independent on counter's initial state, this method deletes counter and
        frees any resources allocated by it. All accumulated counts are lost.
        Module is brought to "void" state.


        :return: (int) 0
        """

        pass
