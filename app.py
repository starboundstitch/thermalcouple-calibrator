from dataclasses import dataclass
import numpy as np
import pandas as pd
import scipy
import serial
import time
import yaml

import nidaqmx
from nidaqmx.constants import (
    AcquisitionType,
    ThermocoupleType,
    TemperatureUnits,
    RTDType,
    ResistanceConfiguration,
    ExcitationSource,
)

@dataclass
class State:

    def __init__(self):
        # Config File
        with open('config.yml', 'r') as file:
            self.config = yaml.safe_load(file)

        self.ser: serial = self.createSerial()
        print("**Fluke Device Initialized**")
        self.task: nidaqmx.Task = 0
        self.pastData = []
        # Various Temperature Sources
        self.probeTemp: float = 0
        self.RTDTemp: float = 0
        # Fluke Data
        self.flukeTemp: float = 0
        self.curSetpoint: float = 0
        self.curStability: bool = 0
        # Calibration Data
        self.RTDSlope: float = np.nan
        self.probeStability: str = ''
        self.calibrationData = []

    def writeCalibrationData(self):

        # Regression of Tuple Data

        df = pd.DataFrame(self.calibrationData)
        df_t = df.transpose().to_numpy()

        regress = []

        for probe in df_t[1:]:

            # Calculate our Linear Regressions
            if len(probe) > 1:
                regress.append(scipy.stats.linregress(probe, df_t[0]))
            else:
                regress.append(np.nan)

        regress = np.matrix(regress).transpose()

        # Export Specific Code

        # Get Probe Heading Label
        headers = ['RTD']
        headers.extend(self.config['thermocouple']['channel'])
        df.columns = headers

        slope = ["Slope"]
        slope.extend(np.asarray(regress[0]).flatten())

        intercept = ["Intercept"]
        intercept.extend(np.asarray(regress[1]).flatten())

        # Add slope and intercept to dataframe
        df.loc[len(df)] = slope
        df.loc[len(df)] = intercept

        # Catch cases where the file cannot be written and ensure data isn't lost
        while True:
            try:
                df.to_excel("calibration.xlsx", sheet_name="sheet1", index=False)
                break
            except:
                print("File cannot be written, try closing any open programs using the file and ensure you have permissions to write in this folder")

            while True:
                input("Hit Enter to Attempt to re-write file.")
                break

        print("**Calibration Data Written**")


    # Collects Data required for each of the test points and stores the state
    def calibrateProbe(self):

        points = []

        if self.config['calibration']['generate']['enabled']:
            points = self.generatePoints()
        else:
            points = self.config['calibration']['points']

        for temp in points:
            # Set Setpoint
            self.setTemp(temp)

            while True:

                # Sleep Based on Sample Time
                # WARNING: This needs to be after the temperature set and
                # before the stability is checked or else it can collect data
                # twice in a row
                time.sleep(self.config['calibration']['polling_time'])

                # Update State from Device
                self.collectData()
                self.statusLine()

                # If Temperature is stable
                if self.checkStability():
                    self.addCalibrationPoint()
                    break

    def checkStability(self) -> bool:

        # Attempt to skip regression testing
        if self.curStability == False:
            self.RTDSlope = np.nan
            return False

        # Regression of Tuple Data

        df = pd.DataFrame(self.pastData)
        df_t = df.transpose().to_numpy()

        regress = []

        for probe in df_t:

            # Calculate our Linear Regressions

            if len(probe) > 1:
                regress.append(scipy.stats.linregress(list(range(len(probe))), probe))
            else:
                regress.append(np.nan)

        regress = np.asarray(np.matrix(regress).transpose()[0]).flatten()

        self.RTDSlope = regress[0]

        # State vars for Stability
        checks = 0
        self.probeStability = ''

        # Check for RTD to be stable
        if abs(regress[0]) < self.config['RTD']['max_stability_slope']:
            checks += 1
            self.probeStability += '1'
        else:
            self.probeStability += '0'

        # Check for all Thermocouples to be stable
        thermo_slope = self.config['thermocouple']['max_stability_slope']
        for regression in regress[1:]:
            # Increment Check Value
            if abs(regression) < thermo_slope:
                checks = checks + 1
                self.probeStability += '1'
            else:
                self.probeStability += '0'


        # Every Regressed value must return within specifications for this to return True
        return len(regress) == checks

    def collectData(self):

        command = ["SOUR:SENS:DATA?", "SOUR:STAB:TEST?", "SOUR:SPO?"]

        # Uncomment For Actual Hardware Testing
        for cmd in command:
            self.writeSerial(cmd)
            self.flukeDataAdd(cmd, self.readSerial())

        # Updates Currently Stored Data
        data = self.task.read()
        # Convert RTD from resistance to Temperature
        data[0] = self.calibRTDTemp(data[0])
        self.pastData.append(data)
        self.RTDTemp = data[0]
        self.probeTemp = data[1]

        # Truncate Past Data if too large
        if len(self.pastData) > (self.config['calibration']['stability_time'] / self.config['calibration']['polling_time']):
            del self.pastData[:1]

    # Takes one point of data and stores it to the global calibrationData list
    def addCalibrationPoint(self) -> float:
        data = self.pastData[-1]
        self.calibrationData.append(data)
        print("**Collecting Data**")
        print(data)

    def setTemp(self, temp: float):

        self.writeSerial("SOUR:SPO " + str(temp))
        self.writeSerial("SOUR:SPO?")

        # Ensure Temperature is set before leaving function
        while abs(float(self.readSerial()) - temp) > 0.005:
            self.writeSerial("SOUR:SPO " + str(temp))
            time.sleep(0.005)
            self.writeSerial("SOUR:SPO?")

    # Store data based on cmd
    def flukeDataAdd(self, cmd: str, data: str):

        match cmd:
            case "SOUR:SENS:DATA?":
                self.flukeTemp = float(data)
            case "SOUR:SPO?":
                self.curSetpoint = float(data)
            case "SOUR:STAB:TEST?":
                self.curStability = bool(int(data))

    # Writes one serial command to the serial port
    def writeSerial(self, cmd: str):

        cmd = cmd + "\r"
        self.ser.write(bytes(cmd, "ascii"))

    # Reads until the carriage return to get one point of data
    def readSerial(self) -> str:

        text = ""
        msg = self.ser.read().decode()
        while msg != "\r":
            text += msg
            msg = self.ser.read().decode()
        return text

    # Prints information important for the status of the program
    # might do ncurses if I care later
    def statusLine(self):
        print(
                "CurSetpoint: {:.3f} FlukeTemp: {:.3f} RTDTemp: {:.3f} ProbeTemp: {:.3f} Probe Stability: {}".format(
                self.curSetpoint,
                self.flukeTemp,
                self.probeTemp,
                self.RTDTemp,
                self.probeStability,
            )
        )

    # Turns the heating element on the thermocouple calibrator off
    def heaterEnabled(self, val):
        state = "0"
        if val == True:
            state = "1"
        self.writeSerial("OUTP:STAT {}".format(state))

    # Serial port creation
    def createSerial(self) -> serial:
        return serial.Serial(
            port=self.config['serial']['port'],
            baudrate=9600,
            timeout=0.1,
            stopbits=serial.STOPBITS_ONE,
        )

    # Converts RTD resistance to temperature based on calibration data
    def calibRTDTemp(self, res):
        rtd = self.config['RTD']
        return rtd['high_coefficient'] * res**2 + rtd['low_coefficient'] * res + rtd['constant_coefficient']


    # Generates Point functionality in the config file
    def generatePoints(self):
        # inputs
        generation = self.config['calibration']['generate']
        min_temp = generation['min_temp']
        max_temp = generation['max_temp']
        point_count = generation['points']

        # Generate Point List
        point_list = np.linspace(min_temp, max_temp, point_count)
        midpoint = int(np.floor((point_count) / 2))

        sorted_points = []

        # Deal With Odd Case
        is_odd = point_count % 2 != 0
        if is_odd:
            sorted_points.append(point_list[midpoint])

        # Sorting Algorithm
        for i in range(midpoint):
            # Append Decreasing Val
            sorted_points.append(point_list[i])
            # Append Increasing Val
            if is_odd:
                sorted_points.append(point_list[i + midpoint + 1])
            else:
                sorted_points.append(point_list[i + midpoint])

        print("**Generated Points**")

        return sorted_points

def main():

    # Thermalcouple Setup -- MUST CLOSE TASK OR BAD THINGS HAPPEN
    with nidaqmx.Task() as task:
        # Create Calibration State (loads config)
        state = State()

        print("**State Initialized**")

        rtd = state.config['RTD']
        task.ai_channels.add_ai_resistance_chan(
            "{}{}/{}".format(rtd['device'], rtd['module'], rtd['channel']),
            resistance_config=ResistanceConfiguration.FOUR_WIRE,
            current_excit_source=ExcitationSource.INTERNAL,
            current_excit_val=rtd['current_excit_val'],

        )
        thermo = state.config['thermocouple']
        tc_type = thermo['type']
        for channel in thermo['channel']:
            task.ai_channels.add_ai_thrmcpl_chan(
                "{}{}/{}".format(thermo['device'], thermo['module'], channel),
                units=TemperatureUnits.DEG_C,
                thermocouple_type=ThermocoupleType[tc_type],
            )

        print("**NI Devices Initialized**")

        # task.timing.cfg_samp_clk_timing(5.0, sample_mode=AcquisitionType.CONTINUOUS)

        # Create internal calibration state
        state.task = task

        # Turn on the Heater
        state.heaterEnabled(True)

        try:
            # Collect Data for all the temperatures
            print("**Starting Calibration**")
            state.calibrateProbe()

            print("Finished Collecting Data")
            state.writeCalibrationData()

        except KeyboardInterrupt:
            pass
        finally:
            task.stop()
            state.heaterEnabled(False)
            state.ser.close()
            input("Program has ended, click 'Enter' to close window: ")


if __name__ == "__main__":

    main()
