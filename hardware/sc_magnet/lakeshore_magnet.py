# -*- coding: utf-8 -*-
"""

M. Chalupnik
Lakeshore superconducting magnet power supply
Qudi hardware file

Resources:
https://www.lakeshore.com/docs/default-source/product-downloads/manuals/625_manual.pdf?sfvrsn=2d9f6b7_1

Before setting output current, make sure that the instrument is properly setup for the magnet
system that is being used. This includes setting up the maximum output current, maximum compliance voltage limit,
maximum ramp rate, quench detection, and PSH parameters
        #for safety, perhaps I will not allow these to be set in qudi; so you have to set them manually in the power supply

The output current setting is not allowed to change if the current ramp rate is greater than the current step limit and
quench detection is on. The current step limit is a parameter of quench detection. If the current were allowed to change at
a rate greater than the current step limit, then a quench would be falsely detected. Refer to Paragraph 4.16 to setup
quench detection.

(TO ADD TO HELP)

"The output current setting is not allowed to change while the persistent switch heater is warming or cooling. The amount
of time it takes for the PSH to warm or cool is system dependent and can be setup under the PSH Setup key. Refer to
Paragraph 4.14 to setup the persistent switch heater.

If you ramp the current with the PSH off, you will get an erroneous field reading (calculated from the current reading).
In reality, magnetic field does not change when current is ramped with PSH off, and the displayed current is not in the
magnet but elsewhere.

When turning on the PSH, it is important that the output current setting of the power supply is equal to the current in the
magnet. If the currents are not equal when the PSH is turned on, there is a possibility that the magnet can quench. The
Model 625 adds an extra layer of protection to keep this from happening. The Model 625 stores the output current
setting of the supply when the PSH was turned off last. If the output current setting does not match this stored setting
when the PSH is being turned on, the following message screen will appear.

SOP:
1. Ensure set values equal measured values
2. Turn on PSH, wait for heat up
3. Change Field as desired; watch that magnet temp stays below 4.8K
4. Turn off PSH"


5.2.6 Message Flow Control
It is important to remember that the user program is in charge of the serial communication at all times. The instrument
cannot initiate communication, determine which device should be transmitting at a given time or guarantee timing
between messages. All of this is the responsibility of the user program.
When issuing commands only the user program should:
• Properly format and transmit the command including terminators as one string.
• Guarantee that no other communication is started for 50 ms after the last character is transmitted.
• Not initiate communication more than 20 times per second.
When issuing queries or queries and commands together the user program should:
• Properly format and transmit the query including terminators as one string.
• Prepare to receive a response immediately.
• Receive the entire response from the instrument including the terminators.
• Guarantee that no other communication is started during the response or for 50 ms after it completes.
• Not initiate communication more than 20 times per second.

5.2.8 Troubleshooting
New Installation
1. Check instrument Baud rate.
2. Make sure transmit (TD) signal line from the instrument is routed to receive (RD) on the computer and vice versa.
(Use a null modem adapter if not).
3. Always send terminators. (note: pyvisa write and read do this automatically for standard terminators \r\n.
                            If desired these terminators can be modified in the magnet control program)
4. Send entire message string at one time including terminators. (Many terminal emulation programs do not.)
5. Send only one simple command at a time until communication is established.
6. Be sure to spell commands correctly and use proper syntax.
Old Installation No Longer Working
7. Power instrument off then on again to see if it is a soft failure.
8. Power computer off then on again to see if communication port is locked up.
9. Verify that Baud rate has not been changed on the instrument during a memory reset.
10. Check all cable connections.
Intermittent Lockups
11. Check cable connections and length.
12. Increase delay between all commands to 100 ms to make sure instrument is not being over loaded.


Page 5-32 of manual: command summary



"""


import pyvisa
from core.module import Base, ConfigOption
import numpy as np
import time
from interface.lakeshore_interface import LakeshoreInterface
#from collections import OrderedDict
#import re


##For debugging:
#from hardware.sc_magnet import lakeshore_magnet as m
#mn = m.Magnet()
#mn.visa_name_x = 'GPIB0::11::INSTR'
#mn.visa_name_y = 'GPIB0::12::INSTR'
#mn.visa_name_z = 'GPIB0::13::INSTR'
#mn.timeout = 5000
#mn.on_activate()


#class Magnet(): #for debugging
class Magnet(Base, LakeshoreInterface):
    """ Magnet positioning software for superconducting magnet.

    Enables precise positioning of the magnetic field in spherical coordinates
    with the angle theta, phi and the radius rho.
    The superconducting magnet has three coils, one in x, y and z direction respectively.
    The current through these coils is used to compute theta, phi and rho.
    The alignment can be done manually as well as automatically via fluorescence alignment.

    Example config for copy-paste:

    lakeshore_magnet:
        module.Class: 'sc_magnet.lakeshore_magnet.Magnet'
        timeout: 5000
        magnet_visa_x : u'GPIB0::11::INSTR'
        magnet_visa_y : u'GPIB0::12::INSTR'
        magnet_visa_z : u'GPIB0::13::INSTR'


    """

    _modtype = 'magnet'
    _modclass = 'hardware'

    # config opts
    timeout = ConfigOption('timeout', missing='error')
    visa_name_x = ConfigOption('magnet_visa_x', missing='error')
    visa_name_y = ConfigOption('magnet_visa_y', missing='error')
    visa_name_z = ConfigOption('magnet_visa_z', missing='error')
    timeout = ConfigOption('timeout', 5000)

    def __init__(self, **kwargs):
        """
        Initialization
         """
        super().__init__(**kwargs)


    def on_activate(self):
        """
        loads the config file and extracts the necessary configurations for the
        superconducting magnet
        """
        rm = pyvisa.ResourceManager()
        self.pyvisa_x = rm.open_resource(self.visa_name_x)
        self.pyvisa_x.timeout = self.timeout  # set response time in milliseconds #TODO pass in via config file

        self.pyvisa_y = rm.open_resource(self.visa_name_y)
        self.pyvisa_y.timeout = self.timeout  # set response time in milliseconds #TODO pass in via config file

        self.pyvisa_z = rm.open_resource(self.visa_name_z)
        self.pyvisa_z.timeout = self.timeout  # set response time in milliseconds #TODO pass in via config file

        self.pyvisas = [self.pyvisa_x, self.pyvisa_y, self.pyvisa_z]

    def on_deactivate(self):
        """
        Deactivate module for Qudi
        @return:
        """
        self.pyvisa_x.close()
        self.pyvisa_y.close()
        self.pyvisa_z.close()

    def parse_reply(self, str):
        str = str.split('\r')[0]
        return list(map(float,str.split(',')))

    def set_psh(self, i, mode):
        """
        This command turns the current to the persistent switch on or off. The switch needs to be enabled and
        setup using the PSHS command. If the output current is not the same as the current setting when the
        PSH was turned off last, the PSH will not be turned on unless the PSH 99 command was issued.
        @param i: magnet axis number; format: integer [0,2]
        @param mode: 0=Heater off, 1=Heater on, 99=Heater on overriding output current setting check
        @return: []
        """
        self.pyvisas[i].write("PSH " + str(mode))

    def get_psh(self, i):
        """
        Specifies the current mode of the persistent switch heater
        @param i: magnet axis number; format: integer [0,2]
        @return: 0=Heater off, 1=Heater on, 2 = Heater warming, 3 = Heater cooling.
        """
        self.pyvisas[i].write("PSH?")
        stri = self.parse_reply(self.pyvisas[i].read())
        return int(stri[0])

    def get_psh_history(self, i):
        """
        Specifies the output current of the power supply when the persistent switch heater was
        turned off last. The PSH will not be allowed to turn on unless this current is equal to the
        present output current or the heater is turned on using the PSH 99 command. If 99.9999
        is returned, then the output current when the PSH was turned off last is unknown.
        @param i: magnet axis number; format: integer [0,2]
        @return: current; format nn.nnnn
        """
        self.pyvisas[i].write("PSHIS?")
        return self.parse_reply(self.pyvisas[i].read())

    def get_calc_field(self, i):
        """
        Calculated output field reading. Field is calculated by multiplying the field constant by
        the measured current output. Use the FLDS command to set the field constant and field
        constant units (G or T).
        @param i: magnet axis number; format: integer [0,2]
        @return: +/-nn.nnnnE+/-nn field
        """
        self.pyvisas[i].write("RDGF?")
        return self.parse_reply(self.pyvisas[i].read())

    def set_field(self, i, f):
        """
        Output Field setting command
        Sets the field value that the output will ramp to at the present ramp rate. The setting entered will be
        based on the field constant and the field units. Refer to the FLDS command.
        @param i: magnet axis number; format: integer [0,2]
        @param f: Format: ±nnn.nnnE±nn; Specifies the output field setting: 0.0000 – ±601.000E+03 G or 0.0000 – ±60.1000E+00 T
        @return: []
        """
        #convert from kG to G
        f = f*10**3
        self.pyvisas[i].write("SETF " + '{:.3e}'.format(f))

    def get_field(self, i):
        """
        Output Field Setting Query
        @param i: magnet axis number; format: integer [0,2]
        @return: Format: ±nnn.nnnE±nn; Specifies the output field setting: 0.0000 – ±601.000E+03 G or 0.0000 – ±60.1000E+00 T
        """
        self.pyvisas[i].write("SETF?")
        stri = self.parse_reply(self.pyvisas[i].read())
        return float(stri[0]) * 10**-3 #G to kG

    #For now, just always work in kG/G. Later if we want we can add ability to switch between kG and T
    def get_magnetic_const(self, i):
        """
        The computed magnetic field is calculated by multiplying the current output reading by the constant.
        The calculated field and the constant are in the units specified.
        @param i: magnet axis number; format: integer [0,2]
        @return: returns units (0 = T/A, 1 = kG/A) and magnetic field constant  (n.nnnn)
        """
        self.pyvisas[i].write("FLDS?")
        return self.parse_reply(self.pyvisas[i].read())


###############################################
    ## Below functions: Have not finished

    #For now, do not use
    def set_magnetic_const(self, i, units, const):
        """
        The computed magnetic field is calculated by multiplying the current output reading by the constant.
        The calculated field and the constant are in the units specified.
        @param i: magnet axis number; format: integer [0,2]
        @param units: (0 = T/A, 1 = kG/A)
        @param const: n.nnnn
        @return: returns units
        """
        self.pyvisas[i].write("FLDS "+ str(units)+ "," + str(const))

    #Can implement these into the gui for later; for now just keep at a value that works and is safe
    def set_ramprate(self, i, rate):
        """
        Sets the output current ramp rate. This value will be used in both the positive and negative directions.
        Setting value is limited by LIMIT.
        @param i: magnet axis number; format: integer [0,2]
        @param rate: Specifies the rate at which the current will ramp at when a new output current setting is
                        entered: 0.0001 – 99.999 A/s
        @return: []
        """
        self.pyvisas[i].write("RATE " + str(rate))

    def get_ramprate(self, i):
        """
        Gets the current ramp rate.
        @param i: magnet axis number; format: integer [0,2]
        @return: Rate at which the current will ramp at when a new output current setting is
                        entered: 0.0001 – 99.999 A/s
        """
        self.pyvisas[i].write("RATE?")
        return self.pyvisas[i].read()


    def get_id(self, i):
        """
        Query the id of the magnet (mostly useful for testing purposes)
        @param i: magnet axis number
        @return: id
        """
        self.pyvisas[i].write("*IDN?")
        return self.pyvisas[i].read()

    def get_resistance(self, i, ch):
        """
        Query the resistance of the magnet
        @param i: magnet axis number
        @param ch: channel number
        """
        self.pyvisas[i].write("RDGR? "+ str(ch))
        return self.pyvisas[i].read()

    def set_i(self, i, cur):
        """
        #Specify the output current setting
        #Sets the current value that the output will ramp to at the present ramp rate
        @param i: magnet axis number
        @param cur: set current, format: +/- nn.nnnn
        @return: []
        """
        self.pyvisas[i].write("SETI " + str(cur))

    def get_i(self, i):
        """
        Query current
        @param i: magnet axis number
        @return: output current setting: 0.0000 – ±60.1000A.
        """
        self.pyvisas[i].write("SETI?")
        return self.pyvisas[i].read()

    def clear_interface(self, i):
        """
        Clears the bits in the Status Byte Register and the Standard Event Status Register and terminates all pending
        operations. Clears the interface, but NOT the instrument. The related instrument command is *RST.
        @param i: magnet axis number, format: integer [0,2]
        @return: []
        """
        self.pyvisas[i].write("*CLS")

    def clear_instrument(self, i):
        """
        Sets controller parameters to power-up settings. Use the DFLT command to set to factory defaults
        @param i: magnet axis number, format: integer [0,2]
        @return: []
        """
        self.pyvisas[i].write("*RST")

    def self_test(self, i):
        """
        Reports status based on test done at powerup.
        @param i: magnet axis number, format: integer [0,2]
        @return: 0= no errors found; 1=Errors found
        """
        self.pyvisas[i].write("*TST?")
        return self.pyvisas[i].read()

    def set_baudrate(self, i, bps):
        """
        Specify Baud rate
        @param bps:  0 = 9600 Baud, 1 = 19200 Baud, 2 = 38400 Baud, 3 = 57600 Baud.
        @param i: magnet axis number, format: integer [0,2]
        @return: []
        """
        self.pyvisas[i].write("BAUD " + str(bps))

    def get_baudrate(self, i):
        """
        Get baud rate
        @param i: magnet axis number, format: integer [0,2]
        @return: Baud rate: 0 = 9600 Baud, 1 = 19200 Baud, 2 = 38400 Baud, 3 = 57600 Baud.
        """
        self.pyvisas[i].write("BAUD?")
        self.pyvisas[i].read()

    def error_clear(self, i):
        """
        This command will clear the operational and PSH errors. The errors will only be cleared if the error
        conditions have been removed. Hardware errors can never be cleared. Refer to Paragraph 5.1.4.3 of manual for a
        list of error bits.
        @param i: magnet axis number, format: integer [0,2]
        @return: []
        """
        self.pyvisas[i].write("ERCL")


    def keypad_status_query(self, i):
        """
        Returns keypad status since the last KEYST?. KEYST? returns 1 after initial powerup
        @param i: magnet axis number; format: integer [0,2]
        @return:
        """
        self.pyvisas[i].write("KEYST?")
        return self.pyvisas[i].read()

    #Do not touch these! These are already set in the magnet power supplies to match our specific magnets.
    def set_output_limits(self, i, cur, vol, rate):
        """
        Sets the upper setting limits for output current, compliance voltage, and output current ramp rate. This
        is a software limit that will limit the settings to these maximum values.
        @param i: magnet axis number; format: integer [0,2]
        @param cur: Specifies the maximum output current setting allowed: 0 – 60.1000 A
        @param vol: Specifies the maximum compliance voltage setting allowed: 0.1000 – 5.0000 V
        @param rate: Specifies the maximum output current ramp rate setting allowed: 0.0001 – 99.999 A/s
        @return: []
        """
        self.pyvisas[i].write("LIMIT " + str(cur) + "," + str(vol) + "," + str(rate))

    def get_output_limits(self, i):
        """
        Gets the upper setting limits for output current, compliance voltage, and output current ramp rate. This
        is a software limit that will limit the settings to these maximum values.
        @param i: magnet axis number; format: integer [0,2]
        @return: cur, vol, rate
        """
        self.pyvisas[i].write("LIMIT?")
        return self.pyvisas[i].read()

    #Again, do not touch these.
    def set_psh_parameters(self, i, en, cur, delay):
        """
        Set persistent switch heater parameters
        @param i: magnet axis number; format: integer [0,2]
        @param en: Specifies if there is a persistent switch in the system: 0 = Disabled (no PSH), 1 = Enabled
        @param cur: Specifies the current needed to turn on the persistent switch heater: 10 – 125 mA
        @param delay: Specifies the time needed to turn the persistent switch heater on or off: 5 – 100 s
        @return: []
        """
        self.pyvisas[i].write("*PSHS " + str(en) + "," + str(cur) + "," + str(delay))

    def get_psh_parameters(self, i):
        """
        Get persistent switch heater parameters
        @param i: magnet axis number; format: integer [0,2]
        @return: en (0 = Disabled (no PSH), 1 = Enabled), cur (10 – 125 mA), delay (5 – 100 s)
        """
        self.pyvisas[i].write("PSHS?")
        return self.pyvisas[i].read()

    #Again, do not touch these
    def set_quench_detection_params(self, i, en, rate):
        """
        When quench detection is enabled, a quench will be detected when the output current attempts to
        change at a rate greater than the current step limit.
        @param i: magnet axis number; format: integer [0,2]
        @param en: Specifies if quench detection is to be used: 0 = Disabled, 1 = Enabled
        @param rate: Specifies the current step limit for quench detection: 0.0100 – 10.000 A/s
        @return: []
        """
        self.pyvisas[i].write("QNCH " + str(en) + ",", str(rate))

    def get_quench_detection_params(self, i):
        """
        When quench detection is enabled, a quench will be detected when the output current attempts to
        change at a rate greater than the current step limit.
        @param i: magnet axis number; format: integer [0,2]
        @return: en (0 = Disabled, 1 = Enabled), rate (0.0100 – 10.000 A/s)
        """
        self.pyvisas[i].write("QNCH?")
        return self.pyvisas[i].read()



    def get_measured_current(self, i):
        """
        Current output reading query
        @param i: magnet axis number; format: integer [0,2]
        @return: nn.nnnn current
        """
        self.pyvisas[i].write("RDGI?")
        return self.pyvisas[i].read()


    def get_measured_voltage_leads(self, i):
        """
        Actual voltage measured at the remote voltage sense leads
        @param i: magnet axis number; format: integer [0,2]
        @return: n.nnnn voltage
        """
        self.pyvisas[i].write("RDGRV?")
        return self.pyvisas[i].read()

    def get_measured_voltage_terminals(self, i):
        """
        Actual output voltage measured at the power supply terminals
        @param i: magnet axis number; format: integer [0,2]
        @return: n.nnnn voltage
        """
        self.pyvisas[i].write("RDGV?")
        return self.pyvisas[i].read()

    def get_voltage(self, i):
        """
        Output Compliance Voltage Setting Query
        @param i: magnet axis number; format: integer [0,2]
        @return: output compliance voltage setting: 0.1000 – 5.0000 V
        """
        self.pyvisas[i].write("SETV?")
        return self.pyvisas[i].read()

    def set_voltage(self, i, vol):
        """
        Output Compliance Voltage Setting Command
        @param i: magnet axis number; format: integer [0,2]
        @param vol: output compliance voltage setting: 0.1000 – 5.0000 V
        @return: []
        """
        self.pyvisas[i].write("SETV " + str(vol)) #may need to wait between calls TODO

    #Nonstandard; do not use
    def set_pramprate(self, i, en, rate):
        """
        Set/enable persistent ramp rate. Typically the current can be ramped faster when the magnet is in persistent mode since the current
        change is not seen by the inductance of the magnet. This setting will automatically change the ramp
        rate when the magnet goes into or out of persistent mode.
        @param i: magnet axis number; format: integer [0,2]
        @param en: Specifies if the persistent mode ramp rate is to be used when the magnet is in persistent
                mode (PSH heater off): 0 = Never use persistent mode ramp rate, 1 = Use persistent mode
                ramp rate when in persistent mode
        @param rate: Specifies the ramp rate to use while in persistent mode: 0.0001 – 99.999 A/s.
        @return: []
        """
        self.pyvisas[i].write("RATEP " + str(en) + "," + str(rate))

    #This is non-standard; do not use
    def get_pramprate(self, i):
        """
        Get persistent ramp rate
        @param i: magnet axis number; format: integer [0,2]
        @return: en (0 = Never use persistent mode ramp rate, 1 = Use persistent mode), rate (0.0001 – 99.999 A/s)
        """
        self.pyvisas[i].write("RATEP?")
        return self.pyvisas[i].read()


    #Skipped some commands that are in manual
    #STOP : Stop output current ramp within two seconds of sending command (what about after 2 seconds? test this)

    # TRIG, TRIG?, XPGM, XPGM? : trigger/ allow voltage to  be set by external voltage
    # RSEG, RSEG?, RSEGS, RSEGS? Allows setting of different ramp rates in shortcuts (I think) (potentially return to)
    #LOCK, LOCK? : Lock out all front panel entries (may be useful?)
    #MODE, MODE? can switch between remote and local mode; I think this happens automatically with the gpib connected?
    #OPST?, OPSTE, OPSTE? Operational status query
    #OPSTR Sum of bit weighing of operational status bits
    # IEEE, IEEE? : Specify command terminator, don't change this!
    #ERCL, ERST?, ERSTE, ERSTE?, ERSTR? : Error clear and error status (potentially useful)
    #DFLT : resets to factory default.
    #DISP and DISP? : change instrument display settings
    #*SRE, *SRE?, *STB?, *TRG : service request enable register query; trigger event
    #*ESE, *ESE?, *ESR? : Event status enable register; bit stuff with register