# -*- coding: utf-8 -*-

"""
This module contains a POI Manager core class which gives capability to mark
points of interest, re-optimise their position, and keep track of sample drift
over time.

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

from qtpy import QtCore
import ctypes   # is a foreign function library for Python. It provides C
                # compatible data types, and allows calling functions in DLLs
                # or shared libraries. It can be used to wrap these libraries
                # in pure Python.

from interface.wavemeter_interface import WavemeterInterface
from core.module import Base, ConfigOption
from core.util.mutex import Mutex

import time
import socket
import json
import websocket


class HardwarePull(QtCore.QObject):
    """ Helper class for running the hardware communication in a separate thread. """

    # signal to deliver the wavelength to the parent class
    sig_wavelength = QtCore.Signal(float)

    def __init__(self, parentclass):
        super().__init__()

        # remember the reference to the parent class to access functions ad settings
        self._parentclass = parentclass


    def handle_timer(self, state_change):
        """ Threaded method that can be called by a signal from outside to start the timer.

        @param bool state: (True) starts timer, (False) stops it.
        """

        if state_change:
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(self._measure_thread)
            self.timer.start(self._parentclass._measurement_timing)
        else:
            if hasattr(self, 'timer'):
                self.timer.stop()

    def _measure_thread(self):
        """ The threaded method querying the data from the wavemeter.
        """

        # update as long as the state is busy
        if self._parentclass.module_state() == 'running':
            # get the current wavelength from the wavemeter
            temp = float(self._parentclass._wavemeterdll.GetWavelengthNum(3, 0))

            # send the data to the parent via a signal
            self.sig_wavelength.emit(temp)



class M2ScannerWavemeter(Base,WavemeterInterface):
    """ Hardware class to controls a High Finesse Wavemeter.

    Example config for copy-paste:

    high_finesse_wavemeter:
        module.Class: 'high_finesse_wavemeter.HighFinesseWavemeter'
        measurement_timing: 10.0 # in seconds

    """

    _modclass = 'HighFinesseWavemeter'
    _modtype = 'hardware'

    # config options
    _measurement_timing = ConfigOption('measurement_timing', default=10.)

    # signals
    sig_handle_timer = QtCore.Signal(bool)

    #############################################
    # Flags for the external DLL
    #############################################

    # define constants as flags for the wavemeter
    _cCtrlStop                   = ctypes.c_uint16(0x00)
    # this following flag is modified to override every existing file
    _cCtrlStartMeasurment        = ctypes.c_uint16(0x1002)
    _cReturnWavelangthAir        = ctypes.c_long(0x0001)
    _cReturnWavelangthVac        = ctypes.c_long(0x0000)






    _ip = ConfigOption('ip', missing='error')
    _port = ConfigOption('port', missing='error')
    _timeout = ConfigOption('port', 5, missing='warn')  # good default setting for timeout?

    buffersize = 1024


    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)

        #locking for thread safety
        self.threadlock = Mutex()

        # the current wavelength read by the wavemeter in nm (vac)
        self._current_wavelength = 0.0


    def on_activate(self):
        #############################################
        # Initialisation to access external DLL
        #############################################
        try:
            # imports the spectrometer specific function from dll
            self._wavemeterdll = ctypes.windll.LoadLibrary('wlmData.dll')

        except:
            self.log.critical('There is no Wavemeter installed on this '
                    'Computer.\nPlease install a High Finesse Wavemeter and '
                    'try again.')

        # define the use of the GetWavelength function of the wavemeter
#        self._GetWavelength2 = self._wavemeterdll.GetWavelength2
        # return data type of the GetWavelength function of the wavemeter
        self._wavemeterdll.GetWavelengthNum.restype = ctypes.c_double
        # parameter data type of the GetWavelength function of the wavemeter
        self._wavemeterdll.GetWavelengthNum.argtypes = [ctypes.c_long, ctypes.c_double]

        # define the use of the ConvertUnit function of the wavemeter
#        self._ConvertUnit = self._wavemeterdll.ConvertUnit
        # return data type of the ConvertUnit function of the wavemeter
        self._wavemeterdll.ConvertUnit.restype = ctypes.c_double
        # parameter data type of the ConvertUnit function of the wavemeter
        self._wavemeterdll.ConvertUnit.argtypes = [ctypes.c_double, ctypes.c_long, ctypes.c_long]

        # manipulate perdefined operations with simple flags
#        self._Operation = self._wavemeterdll.Operation
        # return data type of the Operation function of the wavemeter
        self._wavemeterdll.Operation.restype = ctypes.c_long
        # parameter data type of the Operation function of the wavemeter
        self._wavemeterdll.Operation.argtypes = [ctypes.c_ushort]

        # create an indepentent thread for the hardware communication
        self.hardware_thread = QtCore.QThread()

        # create an object for the hardware communication and let it live on the new thread
        self._hardware_pull = HardwarePull(self)
        self._hardware_pull.moveToThread(self.hardware_thread)

        # connect the signals in and out of the threaded object
        self.sig_handle_timer.connect(self._hardware_pull.handle_timer)
        self._hardware_pull.sig_wavelength.connect(self.handle_wavelength)

        # start the event loop for the hardware
        self.hardware_thread.start()






        self.address = (self._ip, self._port)
        self.timeout = self._timeout
        self.transmission_id = 1
        self._last_status = {}

        print('connecting to laser')
        self.connect_laser()
        print('connecting to wavemeter')
        self.connect_wavemeter()



    def on_deactivate(self):

        print('in hardware trying to deactivate')
        #   self.disconnect_wavemeter() #Not ideal to comment this, but for now, an issue with is_wavemeter_connected
        # is causing a crash. Specifically, a problem with _read_websocket_status
        # which is trying to create a websocket connection which is trying to _open_socket
        # but instead I get WinError 10061 No connection could be made because the target machien
        # actively refused it
        self.disconnect_laser()





        if self.module_state() != 'idle' and self.module_state() != 'deactivated':
            self.stop_acqusition()
        self.hardware_thread.quit()
        self.sig_handle_timer.disconnect()
        self._hardware_pull.sig_wavelength.disconnect()

        try:
            # clean up by removing reference to the ctypes library object
            del self._wavemeterdll
            return 0
        except:
            self.log.error('Could not unload the wlmData.dll of the '
                    'wavemeter.')


    #############################################
    # Methods of the main class
    #############################################

    def handle_wavelength(self, wavelength):
        """ Function to save the wavelength, when it comes in with a signal.
        """
        self._current_wavelength = wavelength

    def start_acqusition(self):
        """ Method to start the wavemeter software.

        @return int: error code (0:OK, -1:error)

        Also the actual threaded method for getting the current wavemeter reading is started.
        """

        # first check its status
        if self.module_state() == 'running':
            self.log.error('Wavemeter busy')
            return -2


        self.module_state.run()
        # actually start the wavemeter
        self._wavemeterdll.Operation(self._cCtrlStartMeasurment) #starts measurement

        # start the measuring thread
        self.sig_handle_timer.emit(True)

        return 0

    def stop_acqusition(self):
        """ Stops the Wavemeter from measuring and kills the thread that queries the data.

        @return int: error code (0:OK, -1:error)
        """
        # check status just for a sanity check
        if self.module_state() == 'idle':
            self.log.warning('Wavemeter was already stopped, stopping it '
                    'anyway!')
        else:
            # stop the measurement thread
            self.sig_handle_timer.emit(True)
            # set status to idle again
            self.module_state.stop()

        # Stop the actual wavemeter measurement
        self._wavemeterdll.Operation(self._cCtrlStop)

        return 0

    def get_current_wavelength(self, kind="vac"):
        """ This method returns the current wavelength.

        @param string kind: can either be "air" or "vac" for the wavelength in air or vacuum, respectively.

        @return float: wavelength (or negative value for errors)
        """
        if kind in "air":
            # for air we need the convert the current wavelength. The Wavemeter DLL already gives us a nice tool do do so.
            return float(self._wavemeterdll.ConvertUnit(self._current_wavelength,self._cReturnWavelangthVac,self._cReturnWavelangthAir))
        if kind in "vac":
            # for vacuum just return the current wavelength
            return float(self._current_wavelength)
        return -2.0

    def get_timing(self):
        """ Get the timing of the internal measurement thread.

        @return float: clock length in second
        """
        return self._measurement_timing

    def set_timing(self, timing):
        """ Set the timing of the internal measurement thread.

        @param float timing: clock length in second

        @return int: error code (0:OK, -1:error)
        """
        self._measurement_timing=float(timing)
        return 0




    def connect_laser(self):
        """ Connect to Instrument.

        @return bool: connection success
        """
        self.socket = socket.create_connection(self.address, timeout=self.timeout)
        interface = self.socket.getsockname()[0]
        _, reply = self.send('start_link', {'ip_address': interface})
        if reply[-1]['status'] == 'ok':
            return True
        else:
            return False

    def disconnect_laser(self):
        """ Close the connection to the instrument.
        """
        self.socket.close()
        self.socket = None

    def set_timeout(self, timeout):  # ????Look at
        """ Sets the timeout in seconds for connecting or sending/receiving

        :param timeout: timeout in seconds
        """
        self.timeout = timeout
        self.socket.settimeout(timeout)

    def send(self, op, parameters, transmission_id=None):  # LOOK AT
        """ Send json message to laser

        :param op: operation to be performed
        :param parameters: dictionary of parameters associated with op
        :param transmission_id: optional transmission id integer
        :return: reply operation dictionary, reply parameters dictionary
        """
        message = self._build_message(op, parameters, transmission_id)
        self.socket.sendall(message.encode('utf-8'))
        reply = self.socket.recv(self.buffersize)
        # self.log(reply)
        op_reply, parameters_reply = self._parse_reply(reply)
        self._last_status[self._parse_report_op(op_reply[-1])] = parameters_reply[-1]
        return op_reply, parameters_reply

    def set(self, setting, value, key_name='setting'):  # LOOK AT
        """ Sets a laser parameter

        :param setting: string containing the setting to be set
        :param value: value of the setting
        :param key_name: optional keyword
        :return bool: set success
        """
        parameters = {}
        parameters[key_name] = value
        if key_name == 'setting':
            parameters[key_name] = [parameters[key_name]]
        _, reply = self.send(setting, parameters)
        if reply['status'] == 'ok':
            return True
        else:
            return False

    def get(self, setting):  # LOOK AT
        """ Gets a laser parameter

        :param setting: string containing the setting
        :return bool: get success
        """
        _, reply = self.send(setting, {})
        if reply[-1]['status'] == 'ok':
            # if reply['status'] == 'ok':
            return reply
        else:
            return None

    def flush(self, bits=1000000):
        """ Flush read buffer
        May cause socket timeout if used when laser isn't scanning
        """

        self.set_timeout(5)  # if this is lower than 5 (e.g. 2) things crash
        try:
            report = self.socket.recv(bits)
        except:
            return -1
        return report

    def update_reports(self, timeout=0.):
        """Check for fresh operation reports."""
        timeout = max(timeout, 0.001)  # ?
        self.socket.settimeout(timeout)
        try:
            report = self.socket.recv(self.buffersize)
        except:
            pass
            # self.log.warning("received reply while waiting for a report: '{}'".format(report[0]))
        self.socket.settimeout(self.timeout)

    def get_last_report(self, op):
        """Get the latest report for the given operation"""
        rep = self._last_status.get(op, None)
        if rep:
            return "fail" if rep["report"][0] else "success"
        return None

    def check_report(self, op):
        """Check and return the latest report for the given operation"""
        self.update_reports()
        return self.get_last_report(op)

    def wait_for_report(self, op, timeout=None):
        """Waits for a report on the given operation

        :param op string: Operation waited on
        :param timeout float: Time before operation quits
        :return dict: report
        """
        self.socket.settimeout(timeout)  # modified
        while True:
            report = self.socket.recv(10000)
            op_reports, parameters_reports = self._parse_reply(report)
            for op_report, parameters_report in zip(op_reports, parameters_reports):
                #               print(op_report)
                #               print(parameters_report)

                if not self._is_report_op(op_report):
                    pass
                    # self.log.warning("received reply while waiting for a report")
                if op_report == self._make_report_op(op):
                    return parameters_report

    def connect_wavemeter(self, sync=True):
        """ Connect to the wavemeter via websocket, if sync==True wait until the connection is established

        :param sync bool: wait until connection is established
        :return bool: connection success
        """
        if self.is_wavemeter_connected():
            return True
        self._send_websocket_request('{"message_type":"task_request","task":["start_wavemeter_link"]}')
        if sync:
            while not self.is_wavemeter_connected():
                time.sleep(0.02)
        return self.is_wavemeter_connected()

    def disconnect_wavemeter(self, sync=True):
        """ Disconnect the wavemeter websocket, if sync==True wait until the connection is established

        :param sync bool: wait until connection is established
        :return: connection success
        """
        if not self.is_wavemeter_connected():
            return True
        if not sync:
            self._send_websocket_request('{"message_type":"task_request","task":["job_stop_wavemeter_link"]}')
        else:
            while self.is_wavemeter_connected():
                # self.stop_all_operaion()
                # self.lock_wavemeter(False)
                # if self.is_wavemeter_lock_on():
                #   time.sleep(1.)
                self._send_websocket_request('{"message_type":"task_request","task":["job_stop_wavemeter_link"]}')
                for _ in range(25):
                    if not self.is_wavemeter_connected():
                        return True
                    time.sleep(0.02)
            return self.is_wavemeter_connected()

    def is_wavemeter_connected(self):
        """ Checks if the wavemeter is connected via websocket

        :return bool: wavemeter connected via websocket
        """
        return bool(self._read_websocket_status(present_key="wlm_fitted")["wlm_fitted"])

    def get_laser_state(self):
        """ Gets the state of the laser.

        :return dict: laser state message
        """
        _, reply = self.send('get_status', {})
        return reply[-1]

    def get_full_tuning_status(self):
        """ Gets the current wavelength, lock_status, and extended zone of the laser

        :return dict: laser tuning status
        """

        _, reply = self.send('poll_wave_m', {})
        return reply[-1]

    def lock_wavemeter(self, lock=True, sync=True):
        """Causes SolsTiS to monitor the wavelength and automatically readjust the tuning to the currently set target
        wavelength.

        :param lock bool: Lock the etalon
        :param sync bool: Wait for the etalon to lock
        :return bool: Wavemeter locked
        """

        _, reply = self.send('lock_wave_m', {'operation': 'on' if lock else 'off'})
        if sync:
            while self.is_wavemeter_lock_on() != lock:
                time.sleep(0.05)
        return self.is_wavemeter_lock_on()

    def is_wavemeter_lock_on(self):
        """Check if the laser is locked to the wavemeter

        :return bool: Wavemeter locked
        """
        return bool(self.get_full_tuning_status()["lock_status"][0])

    def tune_wavelength(self, wavelength, sync=True, timeout=None):
        """
        Fine-tune the wavelength. Only works if the wavemeter is connected.

        :param wavelength float: Wavelength (nm) to be tuned to
        :param sync bool: Wait for the etalon to lock
        :param timeout: timeout in seconds
        :return dict: Tuning report
        """
        _, reply = self.send("set_wave_m", {"wavelength": [wavelength], "report": "finished"})
        if reply[-1]["status"][0] == 1:
            pass
            # self.log.warning("can't tune wavelength: no wavemeter link")
        elif reply[-1]["status"][0] == 2:
            pass
            # self.log.warning("can't tune wavelength: {}nm is out of range".format(wavelength * 1E9))
        if sync:
            return self.wait_for_report('set_wave_m', timeout=timeout)

    def check_tuning_report(self):
        """Check wavelength fine-tuning report

        :return: 'success' or 'fail' if the operation is complete, or None if it is still in progress.
        """
        return self.check_report("set_wave_m_r")

    def wait_for_tuning(self, timeout=None):
        """Wait until wavelength fine-tuning is complete

        :return dict: Tuning report
        """
        self.wait_for_report("set_wave_m", timeout=timeout)

    def get_tuning_status(self):
        """ Get fine-tuning status.

        :reutn string: Tuning status
            'idle': no tuning or locking
            'nolink': no wavemeter link
            'tuning': tuning in progress
            'locked: tuned and locked to the wavemeter
        """
        status = self.get_full_tuning_status()["status"][0]
        return ["idle", "nolink", "tuning", "locked"][status]

    def get_wavelength(self):
        """
        Get fine-tuned wavelength.

        Only works if the wavemeter is connected.
        """
        return self.get_full_tuning_status()["current_wavelength"][0]

    def get_terascan_wavelength(self):
        # use this function to get the wavelength while terascan is running
        # currently calls to this function take ~.21 sec
        timeouted = self.flush(1000000)

        if timeouted == -1:  # timeout or some other error in flush()
            # assume this means the scan is done, even though there are other possible reasons for this to occur
            # (eg. bad connection)
            print('Timeout in get_terascan_wavelength')
            return -1, 'complete'

        out = self.get_laser_state()

        if out.get('report'):  # I think this means we happened to land on the report end status update
            # (unlikely since we are constantly grabbing one update out of many)
            print(out)
            return -1, 'complete'

        if out.get('activity'):
            status = out['activity']
        else:
            status = 'stitching'
            print(out)

        return out['wavelength'][0], status

    def get_terascan_wavelength_web(self):
        # Currently does not work very well
        # uses websocket instead of tcp socket to get wavelength
        # calls take ~0.18 sec, not appreciably faster
        #    while True:
        #        try:
        #            msg_data = self._read_websocket_status_leftpanel()
        #            break
        #        except:
        #            time.sleep(0.05)

        try:
            msg_data = self._read_websocket_status_leftpanel()
        except:
            print('Scan completed')
            return -1, 'complete'

        if msg_data['dodgy_reading']:
            status = 'stitching'
        else:
            status = 'scanning'
        return msg_data['wlm_wavelength'], status

    def stop_tuning(self):
        """Stop fine wavelength tuning."""
        # _, reply = self.send("stop_wave_m", {})
        _, reply = self.send("stop_move_wave_t", {})
        print(reply)
        if reply[-1]["status"][0] == 1:
            print('-1')
            # self.log.warning("can't stop tuning: no wavemeter link")

    def tune_wavelength_table(self, wavelength, sync=True):
        """Coarse-tune the wavelength. Only works if the wavemeter is disconnected.

        :param wavelength double: Wavelength (nm) to be tuned to
        :param sync bool: Wait for the etalon to lock
        """
        _, reply = self.send("move_wave_t", {"wavelength": [wavelength], "report": "finished"})
        if reply[-1]["status"][0] == 1:
            pass
            # self.log.warning("can't tune etalon: command failed")
        elif reply[-1]["status"][0] == 2:
            pass
            # self.log.warning("can't tune wavelength: {}nm is out of range".format(wavelength * 1E9))
        if sync:
            self.wait_for_report("move_wave_t")

    def get_full_tuning_status_table(self):
        """Get full coarse-tuning status (see M2 ICE manual for 'poll_move_wave_t' command)"""
        return self.send("poll_move_wave_t", {})[1]

    def get_tuning_status_table(self):
        """Get coarse-tuning status.

        :return string:
            'done': tuning is done
            'tuning': tuning in progress
            'fail': tuning failed
        """
        status = self.get_full_tuning_status_table()["status"][0]
        return ["done", "tuning", "fail"][status]

    def get_wavelength_table(self):
        """
        Get course-tuned wavelength.

        Only works if the wavemeter is disconnected.
        """
        return self.get_full_tuning_status_table()["current_wavelength"][0]

    def stop_tuning_table(self):
        """Stop coarse wavelength tuning."""
        self.send('stop_move_wave_t', {})

    def tune_etalon(self, percent, sync=True):
        """Tune the etalon to percent. Only works if the wavemeter is disconnected.

        :param percent float: Percent to tune etalon to
        :param sync bool: Wait for the etalon to tune
        """
        _, reply = self.send("tune_etalon", {"setting": [percent], "report": "finished"})
        if reply[-1]["status"][0] == 1:
            pass
            # self.log.warning("can't tune etalon: {} is out of range".format(percent))
        elif reply[-1]["status"][0] == 2:
            pass
            # self.log.warning("can't tune etalon: command failed")
        if sync:
            return self.wait_for_report("tune_etalon")

    def tune_laser_resonator(self, percent, fine=False, sync=True):
        """Tune the laser cavity to percent. Only works if the wavemeter is disconnected.

    :param fine bool: Fine tuning
            True: adjust fine tuning
            False: adjust coarse tuning.
    :param sync bool: Wait for the laser cavity to tune
        """
        _, reply = self.send("fine_tune_resonator" if fine else "tune_resonator",
                             {"setting": [percent], "report": "finished"})
        if reply[-1]["status"][0] == 1:
            pass
            # self.log.warning("can't tune resonator: {} is out of range".format(perc))
        elif reply[-1]["status"][0] == 2:
            pass
            # self.log.warning("can't tune resonator: command failed")
        if sync:
            self.wait_for_report("fine_tune_resonator")

    _terascan_rates = [50E3, 100E3, 200E3, 500E3, 1E6, 2E6, 5E6, 10E6, 20E6, 50E6, 100E6, 200E6, 500E6, 1E9, 2E9, 5E9,
                       10E9, 15E9, 20E9, 50E9, 100E9]

    def setup_terascan(self, scan_type, scan_range, rate, trunc_rate=True):
        """
        Setup terascan.

        :param scan_type str: scan type
            'medium': BRF+etalon, rate from 100 GHz/s to 1 GHz/s
            'fine': All elements, rate from 20 GHz/s to 1 MHz/s
            'line': All elements, rate from 20 GHz/s to 50 kHz/s).
        :param scan_range tuple: (start,stop) in nm
        :param rate float: scan rate in Hz/s
        :param trunc_rate bool: Truncate rate
            True: Truncate the scan rate to the nearest available rate
            False: Incorrect rate would raise an error.
        """
        self._check_terascan_type(scan_type)
        if trunc_rate:
            rate = self._trunc_terascan_rate(rate)
        if rate >= 1E9:
            fact, units = 1E9, "GHz/s"
        elif rate >= 1E6:
            fact, units = 1E6, "MHz/s"
        else:
            fact, units = 1E3, "kHz/s"
        parameters = {"scan": scan_type, "start": [scan_range[0]], "stop": [scan_range[1]],
                      "rate": [rate / fact], "units": units}
        _, reply = self.send('scan_stitch_initialise', parameters)

        if not reply[-1].get('status'):
            print(reply)
            return 2  # error!

        if reply[-1]["status"][0] == 1:
            pass
            # self.log.warning("can't setup TeraScan: start ({:.3f} THz) is out of range".format(scan_range[0] / 1E12))
        elif reply[-1]["status"][0] == 2:
            pass
            # self.log.warning("can't setup TeraScan: stop ({:.3f} THz) is out of range".format(scan_range[1] / 1E12))
        elif reply[-1]["status"][0] == 3:
            pass
            # self.log.warning("can't setup TeraScan: scan out of range")
        elif reply[-1]["status"][0] == 4:
            pass
            # self.log.warning("can't setup TeraScan: TeraScan not available")
        return reply[-1]

    def start_terascan(self, scan_type, sync=True, sync_done=True):
        """Start terascan.
        :param scan_type string: Scan type
            'medium': BRF+etalon, rate from 100 GHz/s to 1 GHz/s
            'fine': All elements, rate from 20 GHz/s to 1 MHz/s
            'line': All elements, rate from 20 GHz/s to 50 kHz/s
        :param sync bool: Wait until the scan is set up (not until the whole scan is complete)
        :param sync_done bool: wait until the whole scan is complete
        """
        self._check_terascan_type(scan_type)
        if sync:
            self.enable_terascan_updates()
        _, reply = self.send("scan_stitch_op", {"scan": scan_type, "operation": "start", "report": "finished"})
        if reply[-1]["status"][0] == 1:
            pass
            # self.log.warning(("can't start TeraScan: operation failed")
        elif reply[-1]["status"][0] == 2:
            pass
            # self.log.warning("can't start TeraScan: TeraScan not available")
        #        print(reply)

        if sync:
            self.wait_for_terascan_update()

    #        if sync_done:
    #            self.wait_for_report("scan_stitch_op") #Prints to command line, also returns the same thing

    _terascan_update_op = "wavelength"

    def enable_terascan_updates(self, enable=True, update_period=0):
        """Enable sending periodic terascan updates. Laser will send updates in the beginning and in the end of every terascan segment.

        :param enable bool: Enable terascan updates
        :param update_period float: Sends updates every update_period percents of the segment (this option doesn't seem to be working currently).
        """
        _, reply = self.send("scan_stitch_output",
                             {"operation": ("start" if enable else "stop"), "update": [update_period]})
        if reply[-1]["status"][0] == 1:
            pass
            # self.log.warning("can't setup TeraScan updates: operation failed")
        if reply[-1]["status"][0] == 2:
            pass
            # self.log.warning("can't setup TeraScan updates: incorrect update rate")
        if reply[-1]["status"][0] == 3:
            pass
            # self.log.warning("can't setup TeraScan: TeraScan not available")
        self._last_status[self._terascan_update_op] = None

    def check_terascan_update(self):
        """Check the latest terascan update.

        :return dict: Terascan report {'wavelength': current_wavelength, 'operation': op}
        where op is:
            'scanning': scanning in progress
            'stitching': stitching in progress
            'finished': scan is finished
            'repeat': segment is repeated
        """
        self.update_reports()
        rep = self._last_status.get(self._terascan_update_op, None)
        return rep

    def wait_for_terascan_update(self):
        """Wait until a new terascan update is available

        :return dict: Terascan report
        """
        self.wait_for_report(self._terascan_update_op)
        return self.check_terascan_update()

    def check_terascan_report(self):
        """Check report on terascan start.

        :return: 'success' or 'fail' if the operation is complete, or None if it is still in progress
        """
        return self.check_report("scan_stitch_op")

    def stop_terascan(self, scan_type, sync=False):
        """Stop terascan of the given type.

        :param scan type string: Scan type
            'medium': BRF+etalon, rate from 100 GHz/s to 1 GHz/s
            'fine': All elements, rate from 20 GHz/s to 1 MHz/s
            'line': All elements, rate from 20 GHz/s to 50 kHz/s
        :param sync_done bool: wait until the scan stop is complete.
        """
        self._check_terascan_type(scan_type)

        # Using TCP connection (below) works, but is very slow
        # _, reply = self.send("scan_stitch_op", {"scan": scan_type, "operation": "stop"})
        # print(reply)

        # FASTER WAY: Seems is already here via stop_scan_web - look into
        self._send_websocket_request(
            '{"stop_scan_stitching":1,"message_type":"page_update"}'
        )
        self._send_websocket_request(
            '{"message_type":"task_request","task":["medium_scan_stop"]}')
        if sync:
            # ready = 0
            # while ready != -1:
            #     ready = self.flush() #waste of 5 seconds
            while True:
                try:
                    self.on_activate()  # todo fix so on_activate isn't necessary
                    return
                except:
                    pass
            ##self.wait_for_report("scan_stitch_op")

    _web_scan_status_str = ['off', 'cont', 'single', 'flyback', 'on', 'fail']

    def get_terascan_status(self, scan_type, web_status="auto"):
        """Get status of a terascan of a given type.

        :param scan type string: Scan type
            'medium': BRF+etalon, rate from 100 GHz/s to 1 GHz/s
            'fine': All elements, rate from 20 GHz/s to 1 MHz/s
            'line': All elements, rate from 20 GHz/s to 50 kHz/s
        :param web_status: Don't really know what this is
        :return dict: Dictionary with 4 items:
            'current': current laser frequency
            'range': tuple with the fill scan range
            'status': Laser status
                'stopped': Scan is not in progress)
                'scanning': Scan is in progress
                'stitching': Scan is in progress, but currently stitching
            'web': Where scan is running in web interface (some failure modes still report 'scanning' through the usual interface);
            only available if the laser web connection is on.
        """
        self._check_terascan_type(scan_type)
        _, reply = self.send("scan_stitch_status", {"scan": scan_type})
        status = {}
        if reply[-1]["status"][0] == 0:
            status["status"] = "stopped"
            status["range"] = None
        elif reply[-1]["status"][0] == 1:
            if reply[-1]["operation"][0] == 0:
                status["status"] = "stitching"
            elif reply[-1]["operation"][0] == 1:
                status["status"] = "scanning"
            status["range"] = reply[-1]["start"][0], reply[-1]["stop"][0]
            status["current"] = reply[-1]["current"][0] if reply[-1]["current"][0] else 0
        elif reply[-1]["status"][0] == 2:
            pass
            # self.log.warning("can't stop TeraScan: TeraScan not available")
        web_status = self._as_web_status(web_status)
        if web_status:
            status["web"] = self._web_scan_status_str[web_status["scan_status"]]
        else:
            status["web"] = None
        return status

    _fast_scan_types = {"cavity_continuous", "cavity_single", "cavity_triangular",
                        "resonator_continuous", "resonator_single", "resonator_ramp", "resonator_triangular",
                        "ect_continuous", "ecd_ramp",
                        "fringe_test"}

    def start_fast_scan(self, scan_type, width, time, sync=False, setup_locks=True):
        """Setup and start fast scan.

        :param scan_type str: scan type(see ICE manual for details)
            'cavity_continuous'
            'cavity_single'
            'cavity_triangular'
            'resonator_continuous'
            'resonator_single'
            'resonator_ramp'
            'resonator_triangular'
            'ect_continuous'
            'ecd_ramp'
            'fringe_test'
        :param width float: scan width (in GHz)
        :param time float: scan time/period (in s)
        :param sync bool: Wait until the scan is set up (not until the whole scan is complete)
        :param setup_locks bool: Automatically setup etalon and reference cavity locks in the appropriate states.
        """
        self._check_fast_scan_type(scan_type)
        if setup_locks:
            if scan_type.startswith("cavity"):
                self.lock_etalon()
                self.lock_reference_cavity()
            elif scan_type.startswith("resonator"):
                self.lock_etalon()
                self.unlock_reference_cavity()
        _, reply = self.send("fast_scan_start", {"scan": scan_type, "width": [width], "time": [time]})
        if reply[-1]["status"][0] == 1:
            pass
            # self.log.warning(("can't start fast scan: width too great for the current tuning position")
        elif reply[-1]["status"][0] == 2:
            pass
            # self.log.warning("can't start fast scan: reference cavity not fitted")
        elif reply[-1]["status"][0] == 3:
            pass
            # self.log.warning("can't start fast scan: ERC not fitted")
        elif reply[-1]["status"][0] == 4:
            pass
            # self.log.warning("can't start fast scan: invalid scan type")
        elif reply[-1]["status"][0] == 5:
            pass
            # self.log.warning("can't start fast scan: time >10000 seconds")
        if sync:
            self.wait_for_report("fast_scan_start")

    def check_fast_scan_report(self):
        """Check fast scan report.

        :return: 'success' or 'fail' if the operation is complete, or None if it is still in progress.
        """
        return self.check_report("fast_scan_start")

    def stop_fast_scan(self, scan_type, return_to_start=True, sync=False):
        """Stop fast scan of the given type.

        :param scan_type str: scan type(see ICE manual for details)
            'cavity_continuous'
            'cavity_single'
            'cavity_triangular'
            'resonator_continuous'
            'resonator_single'
            'resonator_ramp'
            'resonator_triangular'
            'ect_continuous'
            'ecd_ramp'
            'fringe_test'
        :param return_to_start bool: Return to start.
            True: Return to the center frequency after stopping
            False: Stay at the current instantaneous frequency.
        :param sync bool: Wait until the operation is complete.
        """
        self._check_fast_scan_type(scan_type)
        _, reply = self.send("fast_scan_stop" if return_to_start else "fast_scan_stop_nr", {"scan": scan_type})
        if reply[-1]["status"][0] == 1:
            pass
            # self.log.warning("can't stop fast scan: operation failed")
        elif reply[-1]["status"][0] == 2:
            pass
            # self.log.warning("can't stop fast scan: reference cavity not fitted")
        elif reply[-1]["status"][0] == 3:
            pass
            # self.log.warning("can't stop fast scan: ERC not fitted")
        elif reply[-1]["status"][0] == 4:
            pass
            # self.log.warning("can't stop fast scan: invalid scan type")
        if sync:
            self.wait_for_report("fast_scan_stop")

    def get_fast_scan_status(self, scan_type):
        """Get status of a fast scan of a given type.

        :param scan_type str: scan type(see ICE manual for details)
            'cavity_continuous'
            'cavity_single'
            'cavity_triangular'
            'resonator_continuous'
            'resonator_single'
            'resonator_ramp'
            'resonator_triangular'
            'ect_continuous'
            'ecd_ramp'
            'fringe_test'
        "return dict: A dictionary with 4 items:
            'status': 'stopped' - scan is not in progress, or 'scanning' - scan is in progress
            'value': current tuner value (in percent)
        """
        self._check_fast_scan_type(scan_type)
        _, reply = self.query("fast_scan_poll", {"scan": scan_type})
        status = {}
        if reply[-1]["status"][0] == 0:
            status["status"] = "stopped"
        elif reply[-1]["status"][0] == 1:
            status["status"] = "scanning"
        elif reply[-1]["status"][0] == 2:
            pass
            # self.log.warning("can't poll fast scan: reference cavity not fitted")
        elif reply[-1]["status"][0] == 3:
            pass
            # self.log.warning("can't poll fast scan: ERC not fitted")
        elif reply[-1]["status"][0] == 4:
            pass
            # self.log.warning("can't poll fast scan: invalid scan type")
        else:
            pass
            # self.log.warning("can't determine fast scan status: {}".format(reply["status"][0]))
        status["value"] = reply[-1]["tuner_value"][0]
        return status

    def stop_scan_web(self, scan_type):
        """Stop scan of the current type (terascan or fine scan) using web interface. More reliable than native
        programming interface, but requires activated web interface.

        :param scan_type str: scan type(see ICE manual for details)
            'cavity_continuous'
            'cavity_single'
            'cavity_triangular'
            'resonator_continuous'
            'resonator_single'
            'resonator_ramp'
            'resonator_triangular'
            'ect_continuous'
            'ecd_ramp'
            'fringe_test'
        """
        if not self.use_websocket:
            return
        try:
            self._check_terascan_type(scan_type)
            scan_type = scan_type + "_scan"
        except:
            self._check_fast_scan_type(scan_type)
            scan_type = scan_type.replace("continuous", "cont")
        scan_task = scan_type + "_stop"
        print(scan_task)  # check
        self._send_websocket_request('{{"message_type":"task_request","task":["{}"]}}'.format(scan_task))

    _default_terascan_rates = {"line": 10E6, "fine": 100E6, "medium": 5E9}

    def stop_all_operation(self, repeated=True):
        """Stop all laser operations (tuning and scanning). More reliable than native programming interface, but
        requires activated web interface.
        TODO: Implement countdown so that this function works

        :param: repeated bool: Repeat trying to stop the operations until succeeded (more reliable, but takes more time).\
        :return bool: If the operation is a success
        """
        attempts = 0
        # ctd = general.Countdown(self.timeout or None)
        ctd = self.timeout
        while True:
            operating = False
            if not (self.use_websocket and self.get_full_web_status()["scan_status"] == 0):
                for scan_type in ["medium", "fine", "line"]:
                    stat = self.get_terascan_status(scan_type)
                    if stat["status"] != "stopped":
                        operating = True
                        self.stop_terascan(scan_type)
                        time.sleep(0.5)
                        if attempts > 3:
                            self.stop_scan_web(scan_type)
                        if attempts > 6:
                            rate = self._default_terascan_rates[scan_type]
                            scan_center = stat["current"] or 400E12
                            self.setup_terascan(scan_type, (scan_center, scan_center + rate * 10), rate)
                            self.start_terascan(scan_type)
                            time.sleep(1.)
                            self.stop_terascan(scan_type)
                for scan_type in self._fast_scan_types:
                    try:
                        if self.get_fast_scan_status(scan_type)["status"] != "stopped":
                            operating = True
                            self.stop_fast_scan(scan_type)
                            time.sleep(0.5)
                            if attempts > 3:
                                self.stop_scan_web(scan_type)
                    except M2Error:
                        pass
            if self.get_tuning_status() == "tuning":
                operating = True
                self.stop_tuning()
            if self.get_tuning_status_table() == "tuning":
                operating = True
                self.stop_tuning_table()
            if (not repeated) or (not operating):
                break
            time.sleep(0.1)
            attempts += 1
            if (attempts > 10 and ctd.passed()):
                # raise M2Error("coudn't stop all operations: timed out")
                print('M2 Error: could not stop all operations')
        return not operating

    def _build_message(self, op, params, transmission_id=None):
        """ Builds a json message in standard format to be sent to the laser

        :param op: operation to be performed by the laser
        :param params: parameters dictionary associated with the operation
        :param transmission_id: optional transmission id integer
        :return: json byte string to be send to the laser
        """
        if transmission_id is None:
            self.transmission_id = self.transmission_id % 16383 + 1
        else:
            self.transmission_id = transmission_id
        message = {'message': {'transmission_id': [self.transmission_id], 'op': op, 'parameters': dict(params)}}
        return json.dumps(message)

    def _parse_messages(self, message):
        """ Parses a standard format json message into a dictionary

        :param message: json string
        :return: message dictionary
        """
        #      print(message)
        #        print(len(message))  # seems messages are greater than the buffer length... not sure why

        if len(message) >= self.buffersize:  # As is, this throws away data from messages on the edges of the buffer
            # Not sure if there is a good solution though
            msg = message.rsplit('},{', 1)  # split from right
            message = msg[0]
            msg = message.split('},{', 1)  # split from left
            message = msg[1]
            message = '[{' + message + '}]'
        #            print(message)

        pmessages = json.loads(message)
        for i in range(len(pmessages)):
            if 'message' not in pmessages[i]:
                pass
                # self.log.warning('coudn't decode message: {}'.format(message))
            pmessages[i] = pmessages[i]['message']
            for key in ['transmission_id', 'op', 'parameters']:
                if key not in pmessages[i]:
                    pass
                    # self.log.warning("parameter '{}' not in the message {}".format(key,msg))
        return pmessages

    _parse_errors = ["unknown", "JSON parsing error", "'message' string missing",
                     "'transmission_id' string missing", "No 'transmission_id' value",
                     "'op' string missing", "No operation name",
                     "operation not recognized", "'parameters' string missing", "invalid parameter tag or value"]

    def _parse_reply(self, reply):
        """ Parses a json reply from the laser into the two relevant dictionaries

        :param reply: json reply from laser
        :return: reply operation dictionary, reply parameters dictionary
        """
        op_reply = []
        parameters_reply = []
        reply = reply.decode("utf-8")
        preplies = self._parse_messages('[' + reply.replace('}{', '},{') + ']')
        for preply in preplies:
            if preply["op"] == "parse_fail":
                parameters = preply["parameters"]
                perror = parameters["protocol_error"][0]
                perror_description = "unknown" if perror >= len(self._parse_errors) else self._parse_errors[perror]
                error_message = "device parse error: transmission_id={}, error={}({}), error point='{}'".format(
                    parameters.get("transmission", ["NA"])[0], perror, perror_description,
                    parameters.get("JSON_parse_error", "NA"))
                # self.log.warning(error_message)
            op_reply.append(preply["op"])
            parameters_reply.append(preply["parameters"])
        return op_reply, parameters_reply

    def _is_report_op(self, op):
        return op.endswith("_f_r") or op == self._terascan_update_op

    def _make_report_op(self, op):
        return op if op == self._terascan_update_op else op + "_f_r"

    def _parse_report_op(self, op):
        return op if op == self._terascan_update_op else op[:-4]

    def _send_websocket_request(self, message):
        """ Sends a websocket request

        :param message: message to be sent
        """
        ws = websocket.create_connection("ws://{}:8088/control.htm".format(self.address[0]), timeout=self.timeout)
        try:
            self._wait_for_websocket_status(ws, present_key="wlm_fitted")
            self._wait_for_websocket_status(ws, present_key="wlm_fitted")
            ws.send(message)
        finally:
            ws.close()

    def _wait_for_websocket_status(self, ws, present_key=None, nmax=20):
        """ Waits for the websocket to respond and returns the status

        :param ws: websocket
        :param present_key: not sure, I think its the status that we are waiting or
        :param nmax: number of iterations to wait for
        :return: websocket status
        """
        full_data = {}
        for _ in range(nmax):
            data = ws.recv()
            full_data.update(json.loads(data))
            if present_key is None or present_key in data:
                return full_data

    def _read_websocket_status(self, present_key=None, nmax=20):
        """ Reads the websocket status

        :param present_key: not sure, I think its the status that we are waiting or
        :param nmax: number of iterations to wait for
        :return: websocket status
        """
        ws = websocket.create_connection("ws://{}:8088/control.htm".format(self.address[0]), timeout=self.timeout)
        try:
            return self._wait_for_websocket_status(ws, present_key=present_key, nmax=nmax)
        finally:
            ws.recv()
            ws.close()

    def _read_websocket_status_leftpanel(self, present_key=None, nmax=20):
        """ Reads the websocket status

        :param present_key: not sure, I think its the status that we are waiting or
        :param nmax: number of iterations to wait for
        :return: websocket status
        """
        print('inside read websocket status')
        ws = websocket.create_connection("ws://{}:8088/control.htm".format(self.address[0]), timeout=self.timeout)
        try:
            self._wait_for_websocket_status(ws, present_key=present_key, nmax=nmax)  # first call gets first_page
            print('read websocket status ended')
            return self._wait_for_websocket_status(ws, present_key=present_key,
                                                   nmax=nmax)  # second call gets left_panel
        finally:
            ws.recv()
            ws.close()

        print('read websocket stautus ended')

    def _check_terascan_type(self, scan_type):
        """Checks that the terascan type is valid.

        :param scan_type string: Terascan type
        """

        if scan_type not in {"coarse", "medium", "fine", "line"}:
            pass
            # self.log.warning("unknown terascan type: {}".format(scan_type))
        if scan_type == "coarse":
            pass
            # self.log.warning("coarse scan is not currently available")

    def _trunc_terascan_rate(self, rate):
        """Chooses the closest terascan rate

        :param rate: Input terascan rate
        :return: Closest terascan rate
        """

        for tr in self._terascan_rates[::-1]:
            if rate >= tr:
                return tr
        return self._terascan_rates[0]

    def _check_fast_scan_type(self, scan_type):
        """Check that fast scan type is valid

        :param scan_type str: Fast scan type
        """
        if scan_type not in self._fast_scan_types:
            pass
            # self.log.warning("unknown fast scan type: {}".format(scan_type))

