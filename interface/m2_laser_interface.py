# -*- coding: utf-8 -*-
"""
Interface file for lasers where current and power can be set.

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

from enum import Enum
import abc
from core.util.interfaces import InterfaceMetaclass


##TODO: delete or use Enums below
class ShutterState(Enum):
    CLOSED = 0
    OPEN = 1
    UNKNOWN = 2
    NOSHUTTER = 3

class LaserState(Enum):
    OFF = 0
    ON = 1
    LOCKED = 2
    UNKNOWN = 3

class M2LaserInterface(metaclass=InterfaceMetaclass):
    _modtype = 'M2LaserInterface'
    _modclass = 'interface'



    @abc.abstractmethod
    def get_laser_state(self):
        """ Get laser state.
          @return enum LaserState: laser state
        """
        pass




