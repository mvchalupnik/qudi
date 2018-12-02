# -*- coding: utf-8 -*-

"""
This file contains the Qudi Interface for Random Number Generator (tutorial test tool).

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


class RNGInterface(metaclass=InterfaceMetaclass):
    """ Define the controls for a slow counter."""

    _modtype = 'RNGInterface'
    _modclass = 'interface'

    @abc.abstractmethod
    def set_params(self, mean=0.0, noise=1.0):
        """ Set mean value and noise amplitude of the RNG

        @param float mean: optional, mean value of the RNG
        @param float noise: optional, noise amplitude of the RNG, max deviation of random number from mean
        @return int: error code (0:OK, -1:error)
        """
        pass

    @abc.abstractmethod
    def get_params(self):
        """
        Get mean value and noise amplitude of the random number generator

        @return dict: {'mean': mean_value, 'noise': noise_amplitude}
        """
        pass

    @abc.abstractmethod
    def get_random_value(self, samples_number=1):
        """
        Get the output value of the random number generator

        :param int samples_number: optional, number of random numbers to return
        :return list random_numbers: list of n_samples output random numbers
        """
        pass
