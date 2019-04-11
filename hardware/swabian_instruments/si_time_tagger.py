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
import TimeTagger as TT


class SITimeTagger(Base):

    _modclass = 'SITimeTagger'
    _modtype = 'hardware'

    # Config Options
    # Serial number of the device
    _cfg_serial_str = ConfigOption(name='serial_number_string', default='', missing='nothing')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Serial number string
        self._serial_str = ''
        # Reference to the device
        self._tagger = None

    def on_activate(self):

        # Set the following channel numbering scheme:
        #   rising edge channels: 1, ..., 8
        #   falling edges channels: -1, ..., -8
        #   For details see Time Tagger documentation: "Channel Number Schema 0 and 1"
        TT.setTimeTaggerChannelNumberScheme(TT.TT_CHANNEL_NUMBER_SCHEME_ONE)

        # Populate serial number string attribute
        self._serial_str = self._cfg_serial_str

        # Connect to TimeTagger
        try:
            self._tagger = TT.createTimeTagger(self._serial_str)
        # If TT function call fails, it normally rises NotImplementedError
        except NotImplementedError:
            self.log.error('on_activate(): TT.createTimeTagger() call failed [self._serial_str={}]'
                           ''.format(self._serial_str))
            self._tagger = None
            return

        # Log device ID information to demonstrate that connection indeed works
        serial = self._tagger.getSerial()
        model = self._tagger.getModel()
        self.log.info('Successfully connected to Swabian Instruments TimeTagger device \n'
                      'Serial number: {0}, Model: {1}'
                      ''.format(serial, model))

    def on_deactivate(self):

        # Reset device
        try:
            self._tagger.reset()
        # handle exception during reset()
        except NotImplementedError:
            pass
        # handle the case of self._tagger = None
        except AttributeError:
            pass

        # Clear internal variables
        self._serial_str = ''
        self._tagger = None

    @property
    def reference(self):
        """
        Read-only access to the self._tagger reference to the device

        :return: reference to device
        """

        return self._tagger



