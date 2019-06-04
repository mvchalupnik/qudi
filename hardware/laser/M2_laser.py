# -*- coding: utf-8 -*-
"""
This module controls an M squared laser
Written by Graham Joe
"""

from core.module import Base, ConfigOption
from interface.simple_laser_interface import SimpleLaserInterface
from interface.simple_laser_interface import LaserState
from interface.simple_laser_interface import ShutterState

import serial
import time
import socket
import json
import websocket


class M2Laser:
    """ Implements the M squared laser.

        Example config for copy-paste:

        m2_laser:
            module.Class: 'laser.M2_laser.M2Laser'
            ip: '10.243.43.58'
            port: 39933
        """

    _modclass = 'laser'
    _modtype = 'hardware'

    def __init__(self, ip, port, timeout=5):
        # for now use '10.243.43.58' and 39933
        self.address = (ip, port)
        self.timeout = timeout
        self.transmission_id = 1
        self._last_status = {}

    def on_activate(self):
        """ Activate module.
        """
        self.connect_laser()
        self.connect_wavemeter()

    def on_deactivate(self):
        """ Deactivate module.
        """
        self.disconnect_wavemeter()
        self.disconnect_laser()

    def connect_laser(self):
        """ Connect to Instrument.

        @return bool: connection success
        """
        self.socket = socket.create_connection(self.address, timeout=self.timeout)
        interface = self.socket.getsockname()[0]
        _, reply = self.send('start_link', {'ip_address': interface})
        if reply['status'] == 'ok':
            return True
        else:
            return False

    def disconnect_laser(self):
        """ Close the connection to the instrument.
        """
        self.socket.close()
        self.socket = None

    def is_connected(self):
        """ Checks the laser connection

        :return bool: Whether or not the laser is connected
        """
        return self.socket.is_connected()

    def set_timeout(self, timeout):
        """ Sets the timeout in seconds for connecting or sending/receiving

        :param timeout: timeout in seconds
        """
        self.timeout = timeout
        self.socket.set_timeout(timeout)

    def send(self, op, parameters, transmission_id=None):
        """ Send json message to laser

        :param op: operation to be performed
        :param parameters: dictionary of parameters associated with op
        :param transmission_id: optional transmission id integer
        :return: reply operation dictionary, reply parameters dictionary
        """
        message = self._build_message(op, parameters, transmission_id)
        self.socket.sendall(message.encode('utf-8'))
        reply = self.socket.recv(1024)
        #self.log(reply)
        op_reply, parameters_reply = self._parse_reply(reply)
        self._last_status[self._parse_report_op(op_reply)] = parameters_reply
        return op_reply, parameters_reply

    def set(self, setting, value, key_name='setting'):
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

    def get(self, setting):
        """ Gets a laser parameter

        :param setting: string containing the setting
        :return bool: get success
        """
        _, reply = self.send(setting, {})
        if reply['status'] == 'ok':
            return reply
        else:
            return None

    def flush(self):
        """ Flush read buffer
        """
        self.socket.recv_all()

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
                #self.stop_all_operaion()
                #self.lock_wavemeter(False)
                #if self.is_wavemeter_lock_on():
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
        return reply

    def get_full_tuning_status(self):
        _, reply = self.send('poll_wave_m', {})
        return reply

    def lock_wavemeter(self, lock=True, sync=True):
        _, reply = self.send('lock_wave_m', {'operation': 'on' if lock else 'off'})
        if sync:
            while self.is_wavemeter_lock_on() != lock:
                time.sleep(0.05)
        return reply

    def is_wavemeter_lock_on(self):
        """Check if the laser is locked to the wavemeter"""
        return bool(self.get_full_tuning_status()["lock_status"][0])

    def tune_wavelength(self, wavelength, sync=True, timeout=None):
        """
        Fine-tune the wavelength.

        Only works if the wavemeter is connected.
        If ``sync==True``, wait until the operation is complete (might take from several seconds up to several minutes).
        """
        _, reply = self.send("set_wave_m", {"wavelength": [wavelength * 1E9], "report": "finished"})
        if reply["status"][0] == 1:
            pass
            #self.log.warning("can't tune wavelength: no wavemeter link")
        elif reply["status"][0] == 2:
            pass
            #self.log.warning("can't tune wavelength: {}nm is out of range".format(wavelength * 1E9))
        if sync:
            return self.wait_for_report(timeout=timeout)

    def check_tuning_report(self):
        """
        Check wavelength fine-tuning report
        Return ``"success"`` or ``"fail"`` if the operation is complete, or ``None`` if it is still in progress.
        """
        return self.check_report("set_wave_m_r")

    def wait_for_tuning(self, timeout=None):
        """Wait until wavelength fine-tuning is complete"""
        self.wait_for_report("set_wave_m", timeout=timeout)

    def get_tuning_status(self):
        """
        Get fine-tuning status.
        Return either ``"idle"`` (no tuning or locking), ``"nolink"`` (no wavemeter link),
        ``"tuning"`` (tuning in progress), or ``"locked"`` (tuned and locked to the wavemeter).
        """
        status = self.get_full_tuning_status()["status"][0]
        return ["idle", "nolink", "tuning", "locked"][status]

    def get_wavelength(self):
        """
        Get fine-tuned wavelength.

        Only works if the wavemeter is connected.
        """
        return self.get_full_tuning_status()["current_wavelength"][0] * 1E-9

    def stop_tuning(self):
        """Stop fine wavelength tuning."""
        _, reply = self.send("stop_wave_m", {})
        if reply["status"][0] == 1:
            pass
            #self.log.warning("can't stop tuning: no wavemeter link")

    def tune_wavelength_table(self, wavelength, sync=True):
        """
        Coarse-tune the wavelength.

        Only works if the wavemeter is disconnected.
        If ``sync==True``, wait until the operation is complete.
        """
        _, reply = self.send("move_wave_t", {"wavelength": [wavelength * 1E9], "report": "finished"})
        if reply["status"][0] == 1:
            pass
            #self.log.warning("can't tune etalon: command failed")
        elif reply["status"][0] == 2:
            pass
            #self.log.warning("can't tune wavelength: {}nm is out of range".format(wavelength * 1E9))
        if sync:
            self.wait_for_report("move_wave_t")

    def get_full_tuning_status_table(self):
        """Get full coarse-tuning status (see M2 ICE manual for ``"poll_move_wave_t"`` command)"""
        return self.send("poll_move_wave_t", {})[1]

    def get_tuning_status_table(self):
        """
        Get coarse-tuning status.
        Return either ``"done"`` (tuning is done), ``"tuning"`` (tuning in progress), or ``"fail"`` (tuning failed).
        """
        status = self.get_full_tuning_status_table()["status"][0]
        return ["done", "tuning", "fail"][status]

    def get_wavelength_table(self):
        """
        Get course-tuned wavelength.

        Only works if the wavemeter is disconnected.
        """
        return self.get_full_tuning_status_table()["current_wavelength"][0] * 1E-9

    def stop_tuning_table(self):
        """Stop coarse wavelength tuning."""
        self.query("stop_move_wave_t", {})

    def tune_etalon(self, percent, sync=True):
        """
        Tune the etalon to `perc` percent.

        Only works if the wavemeter is disconnected.
        If ``sync==True``, wait until the operation is complete.
        """
        _, reply = self.send("tune_etalon", {"setting": [percent], "report": "finished"})
        if reply["status"][0] == 1:
            pass
            #self.log.warning("can't tune etalon: {} is out of range".format(percent))
        elif reply["status"][0] == 2:
            pass
            #self.log.warning("can't tune etalon: command failed")
        if sync:
            self.wait_for_report("tune_etalon")

    def tune_laser_resonator(self, percent, fine=False, sync=True):
        """
        Tune the laser cavity to `percent` percent.

        If ``fine==True``, adjust fine tuning; otherwise, adjust coarse tuning.
        Only works if the wavemeter is disconnected.
        If ``sync==True``, wait until the operation is complete.
        """
        _, reply = self.send("fine_tune_resonator" if fine else "tune_resonator", {"setting": [percent], "report": "finished"})
        if reply["status"][0] == 1:
            pass
            #self.log.warning("can't tune resonator: {} is out of range".format(perc))
        elif reply["status"][0] == 2:
            pass
            #self.log.warning("can't tune resonator: command failed")
        if sync:
            self.wait_for_report("fine_tune_resonator")

    def _check_terascan_type(self, scan_type):
        if scan_type not in {"coarse", "medium", "fine", "line"}:
            pass
            #self.log.warning("unknown terascan type: {}".format(scan_type))
        if scan_type == "coarse":
            pass
            #self.log.warning("coarse scan is not currently available")

    _terascan_rates = [50E3, 100E3, 200E3, 500E3, 1E6, 2E6, 5E6, 10E6, 20E6, 50E6, 100E6, 200E6, 500E6, 1E9, 2E9, 5E9,
                       10E9, 15E9, 20E9, 50E9, 100E9]

    def _trunc_terascan_rate(self, rate):
        for tr in self._terascan_rates[::-1]:
            if rate >= tr:
                return tr
        return self._terascan_rates[0]

    def setup_terascan(self, scan_type, scan_range, rate, trunc_rate=True):
        """
        Setup terascan.
        Args:
            scan_type(str): scan type. Can be ``"medium"`` (BRF+etalon, rate from 100 GHz/s to 1 GHz/s),
                ``"fine"`` (all elements, rate from 20 GHz/s to 1 MHz/s), or ``"line"`` (all elements, rate from 20 GHz/s to 50 kHz/s).
            scan_range(tuple): tuple ``(start,stop)`` with the scan range (in Hz).
            rate(float): scan rate (in Hz/s).
            trunc_rate(bool): if ``True``, truncate the scan rate to the nearest available rate (otherwise, incorrect rate would raise an error).
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
        params = {"scan": scan_type, "start": [c / scan_range[0] * 1E9], "stop": [c / scan_range[1] * 1E9],
                  "rate": [rate / fact], "units": units}
        _, reply = self.query("scan_stitch_initialise", params)
        if reply["status"][0] == 1:
            pass
            #self.log.warning("can't setup TeraScan: start ({:.3f} THz) is out of range".format(scan_range[0] / 1E12))
        elif reply["status"][0] == 2:
            pass
            #self.log.warning("can't setup TeraScan: stop ({:.3f} THz) is out of range".format(scan_range[1] / 1E12))
        elif reply["status"][0] == 3:
            pass
            #self.log.warning("can't setup TeraScan: scan out of range")
        elif reply["status"][0] == 4:
            pass
            #self.log.warning("can't setup TeraScan: TeraScan not available")

    def start_terascan(self, scan_type, sync=False, sync_done=False):
        """
        Start terascan.
        Scan type can be ``"medium"`` (BRF+etalon, rate from 100 GHz/s to 1 GHz/s), ``"fine"`` (all elements, rate from 20 GHz/s to 1 MHz/s),
        or ``"line"`` (all elements, rate from 20 GHz/s to 50 kHz/s).
        If ``sync==True``, wait until the scan is set up (not until the whole scan is complete).
        If ``sync_done==True``, wait until the whole scan is complete.
        """
        self._check_terascan_type(scan_type)
        if sync:
            self.enable_terascan_updates()
        _, reply = self.query("scan_stitch_op", {"scan": scan_type, "operation": "start"}, report=True)
        if reply["status"][0] == 1:
            pass
            #self.log.warning(("can't start TeraScan: operation failed")
        elif reply["status"][0] == 2:
            pass
            #self.log.warning("can't start TeraScan: TeraScan not available")
        if sync:
            self.wait_for_terascan_update()
        if sync_done:
            self.wait_for_report("scan_stitch_op")

    def enable_terascan_updates(self, enable=True, update_period=0):
        """
        Enable sending periodic terascan updates.
        If enabled, laser will send updates in the beginning and in the end of every terascan segment.
        If ``update_period!=0``, it will also send updates every ``update_period`` percents of the segment (this option doesn't seem to be working currently).
        """
        _, reply = self.query("scan_stitch_output",
                              {"operation": ("start" if enable else "stop"), "update": [update_period]})
        if reply["status"][0] == 1:
            pass
            #self.log.warning("can't setup TeraScan updates: operation failed")
        if reply["status"][0] == 2:
            pass
            #self.log.warning("can't setup TeraScan updates: incorrect update rate")
        if reply["status"][0] == 3:
            pass
            #self.log.warning("can't setup TeraScan: TeraScan not available")
        self._last_status[self._terascan_update_op] = None

    def check_terascan_update(self):
        """
        Check the latest terascan update.
        Return ``None`` if none are available, or a dictionary ``{"wavelength":current_wavelength, "operation":op}``,
        where ``op`` is ``"scanning"`` (scanning in progress), ``"stitching"`` (stitching in progress), ``"finished"`` (scan is finished), or ``"repeat"`` (segment is repeated).
        """
        self.update_reports()
        rep = self._last_status.get(self._terascan_update_op, None)
        return rep

    def wait_for_terascan_update(self):
        """Wait until a new terascan update is available"""
        self.wait_for_report(self._terascan_update_op)
        return self.check_terascan_update()

    def check_terascan_report(self):
        """
        Check report on terascan start.
        Return ``"success"`` or ``"fail"`` if the operation is complete, or ``None`` if it is still in progress.
        """
        return self.check_report("scan_stitch_op")

    def stop_terascan(self, scan_type, sync=False):
        """
        Stop terascan of the given type.

        If ``sync==True``, wait until the operation is complete.
        """
        self._check_terascan_type(scan_type)
        _, reply = self.send("scan_stitch_op", {"scan": scan_type, "operation": "stop"})
        if reply["status"][0] == 1:
            pass
            #self.log.warning("can't stop TeraScan: operation failed")
        elif reply["status"][0] == 2:
            pass
            #self.log.warning("can't stop TeraScan: TeraScan not available")
        if sync:
            self.wait_for_report("scan_stitch_op")

    _web_scan_status_str = ['off', 'cont', 'single', 'flyback', 'on', 'fail']

    def get_terascan_status(self, scan_type, web_status="auto"):
        """
        Get status of a terascan of a given type.
        Return dictionary with 4 items:
            ``"current"``: current laser frequency
            ``"range"``: tuple with the fill scan range
            ``"status"``: can be ``"stopped"`` (scan is not in progress), ``"scanning"`` (scan is in progress),
            or ``"stitching"`` (scan is in progress, but currently stitching)
            ``"web"``: where scan is running in web interface (some failure modes still report ``"scanning"`` through the usual interface);
            only available if the laser web connection is on.
        """
        self._check_terascan_type(scan_type)
        _, reply = self.send("scan_stitch_status", {"scan": scan_type})
        status = {}
        if reply["status"][0] == 0:
            status["status"] = "stopped"
            status["range"] = None
        elif reply["status"][0] == 1:
            if reply["operation"][0] == 0:
                status["status"] = "stitching"
            elif reply["operation"][0] == 1:
                status["status"] = "scanning"
            status["range"] = c / (reply["start"][0] / 1E9), c / (reply["stop"][0] / 1E9)
            status["current"] = c / (reply["current"][0] / 1E9) if reply["current"][0] else 0
        elif reply["status"][0] == 2:
            pass
            #self.log.warning("can't stop TeraScan: TeraScan not available")
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

    def _check_fast_scan_type(self, scan_type):
        if scan_type not in self._fast_scan_types:
            pass
            #self.log.warning("unknown fast scan type: {}".format(scan_type))

    def start_fast_scan(self, scan_type, width, time, sync=False, setup_locks=True):
        """
        Setup and start fast scan.
        Args:
            scan_type(str): scan type. Can be ``"cavity_continuous"``, ``"cavity_single"``, ``"cavity_triangular"``,
                ``"resonator_continuous"``, ``"resonator_single"``, ``"resonator_ramp"``, ``"resonator_triangular"``,
                ``"ect_continuous"``, ``"ecd_ramp"``, or ``"fringe_test"`` (see ICE manual for details)
            width(float): scan width (in Hz).
            time(float): scan time/period (in s).
            sync(bool): if ``True``, wait until the scan is set up (not until the whole scan is complete).
            setup_locks(bool): if ``True``, automatically setup etalon and reference cavity locks in the appropriate states.
        """
        self._check_fast_scan_type(scan_type)
        if setup_locks:
            if scan_type.startswith("cavity"):
                self.lock_etalon()
                self.lock_reference_cavity()
            elif scan_type.startswith("resonator"):
                self.lock_etalon()
                self.unlock_reference_cavity()
        _, reply = self.send("fast_scan_start", {"scan": scan_type, "width": [width / 1E9], "time": [time]})
        if reply["status"][0] == 1:
            pass
            #self.log.warning(("can't start fast scan: width too great for the current tuning position")
        elif reply["status"][0] == 2:
            pass
            #self.log.warning("can't start fast scan: reference cavity not fitted")
        elif reply["status"][0] == 3:
            pass
            #self.log.warning("can't start fast scan: ERC not fitted")
        elif reply["status"][0] == 4:
            pass
            #self.log.warning("can't start fast scan: invalid scan type")
        elif reply["status"][0] == 5:
            pass
            #self.log.warning("can't start fast scan: time >10000 seconds")
        if sync:
            self.wait_for_report("fast_scan_start")

    def check_fast_scan_report(self):
        """
        Check fast scan report.
        Return ``"success"`` or ``"fail"`` if the operation is complete, or ``None`` if it is still in progress.
        """
        return self.check_report("fast_scan_start")

    def stop_fast_scan(self, scan_type, return_to_start=True, sync=False):
        """
        Stop fast scan of the given type.

        If ``return_to_start==True``, return to the center frequency after stopping; otherwise, stay at the current instantaneous frequency.
        If ``sync==True``, wait until the operation is complete.
        """
        self._check_fast_scan_type(scan_type)
        _, reply = self.send("fast_scan_stop" if return_to_start else "fast_scan_stop_nr", {"scan": scan_type})
        if reply["status"][0] == 1:
            pass
            #self.log.warning("can't stop fast scan: operation failed")
        elif reply["status"][0] == 2:
            pass
            #self.log.warning("can't stop fast scan: reference cavity not fitted")
        elif reply["status"][0] == 3:
            pass
            #self.log.warning("can't stop fast scan: ERC not fitted")
        elif reply["status"][0] == 4:
            pass
            #self.log.warning("can't stop fast scan: invalid scan type")
        if sync:
            self.wait_for_report("fast_scan_stop")

    def get_fast_scan_status(self, scan_type):
        """
        Get status of a fast scan of a given type.
        Return dictionary with 4 items:
            ``"status"``: can be ``"stopped"`` (scan is not in progress), ``"scanning"`` (scan is in progress).
            ``"value"``: current tuner value (in percent).
        """
        self._check_fast_scan_type(scan_type)
        _, reply = self.query("fast_scan_poll", {"scan": scan_type})
        status = {}
        if reply["status"][0] == 0:
            status["status"] = "stopped"
        elif reply["status"][0] == 1:
            status["status"] = "scanning"
        elif reply["status"][0] == 2:
            pass
            #self.log.warning("can't poll fast scan: reference cavity not fitted")
        elif reply["status"][0] == 3:
            pass
            #self.log.warning("can't poll fast scan: ERC not fitted")
        elif reply["status"][0] == 4:
            pass
            #self.log.warning("can't poll fast scan: invalid scan type")
        else:
            pass
            #self.log.warning("can't determine fast scan status: {}".format(reply["status"][0]))
        status["value"] = reply["tuner_value"][0]
        return status

    def stop_scan_web(self, scan_type):
        """
        Stop scan of the current type (terascan or fine scan) using web interface.
        More reliable than native programming interface, but requires activated web interface.
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
        self._send_websocket_request('{{"message_type":"task_request","task":["{}"]}}'.format(scan_task))

    _default_terascan_rates = {"line": 10E6, "fine": 100E6, "medium": 5E9}

    def stop_all_operation(self, repeated=True):
        """
        Stop all laser operations (tuning and scanning).
        More reliable than native programming interface, but requires activated web interface.
        If ``repeated==True``, repeat trying to stop the operations until succeeded (more reliable, but takes more time).
        Return ``True`` if the operation is success otherwise ``False``.
        """
        attempts = 0
        ctd = general.Countdown(self.timeout or None)
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
                raise M2Error("coudn't stop all operations: timed out")
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

    def _parse_message(self, message):
        """ Parses a standard format json message into a dictionary

        :param message: json string
        :return: message dictionary
        """
        pmessage = json.loads(message)
        if 'message' not in pmessage:
            pass
            #self.log.warning('coudn't decode message: {}'.format(message))
        pmessage = pmessage['message']
        for key in ['transmission_id', 'op', 'parameters']:
            if key not in pmessage:
                pass
                #self.log.warning("parameter '{}' not in the message {}".format(key,msg))
        return pmessage

    _parse_errors = ["unknown", "JSON parsing error", "'message' string missing",
                     "'transmission_id' string missing", "No 'transmission_id' value",
                     "'op' string missing", "No operation name",
                     "operation not recognized", "'parameters' string missing", "invalid parameter tag or value"]

    def _parse_reply(self, reply):
        """ Parses a json reply from the laser into the two relevant dictionaries

        :param reply: json reply from laser
        :return: reply operation dictionary, reply parameters dictionary
        """
        preply = self._parse_message(reply)
        if preply["op"] == "parse_fail":
            parameters = preply["parameters"]
            perror = parameters["protocol_error"][0]
            perror_description = "unknown" if perror>=len(self._parse_errors) else self._parse_errors[perror]
            error_message = "device parse error: transmission_id={}, error={}({}), error point='{}'".format(
                parameters.get("transmission", ["NA"])[0], perror, perror_description, parameters.get("JSON_parse_error","NA"))
            #self.log.warning(error_message)
        return preply["op"], preply["parameters"]

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

    _terascan_update_op = "wavelength"
    def _is_report_op(self, op):
        return op.endswith("_f_r") or op == self._terascan_update_op

    def _make_report_op(self, op):
        return op if op == self._terascan_update_op else op + "_f_r"

    def _parse_report_op(self, op):
        return op if op == self._terascan_update_op else op[:-4]

    def update_reports(self, timeout=0.):
        """Check for fresh operation reports."""
        timeout = max(timeout, 0.001)
        self.socket.settimeout(timeout)
        try:
            report = self.socket.recv(1024)
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

    def wait_for_report(self, timeout=None):
        self.socket.settimeout(timeout)
        report = self.socket.recv(1024)
        op_report, parameters_report = self._parse_reply(report)
        self.socket.settimeout(self.timeout)
        if not self._is_report_op(op_report):
            pass
            #self.log.warning("received reply while waiting for a report")
        return parameters_report
