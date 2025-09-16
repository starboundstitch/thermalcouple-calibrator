from dataclasses import dataclass
import serial
import time
import scipy

import nidaqmx
from nidaqmx.constants import (
    AcquisitionType,
    ThermocoupleType,
    TemperatureUnits,
    RTDType,
    ResistanceConfiguration,
    ExcitationSource,
)

testPoints = [76, 80]
testPoints = [125, 150, 175, 125, 100, 75]
MAX_STABILITY_SLOPE = 0.1
WAIT_TIME = 5


@dataclass
class State:

    def __init__(self):
        self.ser: serial = self.createSerial()
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
        self.RTDSlope: float = 100
        self.calibrationData = []

    def getCalibrationData(self):
        return self.calibrationData

    # Collects Data required for each of the test points and stores the state
    def calibrateProbe(self):

        for temp in testPoints:
            # Set Setpoint
            self.setTemp(temp)

            while True:
                time.sleep(WAIT_TIME)

                # Update State from Device
                self.collectData()

                # If Temperature is stable
                # Modify to have an external stability function that ensures stability with every
                # thermocouple probe that is hooked to the system
                if (self.curStability == True) & (self.RTDSlope < MAX_STABILITY_SLOPE):
                    self.addCalibrationPoint()
                    break

    def collectData(self):

        command = ["SOUR:SENS:DATA?", "SOUR:STAB:TEST?", "SOUR:SPO?"]

        # Uncomment For Actual Hardware Testing
        for cmd in command:
            self.writeSerial(cmd)
            self.flukeDataAdd(cmd, self.readSerial())

        # Updates Currently Stored Data
        data = self.task.read()
        self.pastData.append(data)
        self.probeTemp = data[0]
        self.RTDTemp = data[1]

        # Truncate Past Data if too large
        if len(self.pastData) > (60 / WAIT_TIME):
            del self.pastData[:1]

    # Takes one point of data and stores it to the global calibrationData list
    def addCalibrationPoint(self) -> float:
        self.calibrationData.append((self.RTDTemp, self.probeTemp))
        print(
            "RTD_Temp: {} Probe_Temp: {}".format(str(self.RTDTemp), str(self.probeTemp))
        )

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


    # Serial port creation
    def createSerial(self) -> serial:
        return serial.Serial(
            port="COM5",
            baudrate=9600,
            timeout=0.1,
            stopbits=serial.STOPBITS_ONE,
        )


def main():

    # Thermalcouple Setup -- MUST CLOSE TASK OR BAD THINGS HAPPEN
    with nidaqmx.Task() as task:
        task.ai_channels.add_ai_thrmcpl_chan(
            "cDAQ2Mod3/ai0",
            units=TemperatureUnits.DEG_C,
            thermocouple_type=ThermocoupleType.T,
        )
        task.ai_channels.add_ai_rtd_chan(
            "cDAQ2Mod1/ai0",
            rtd_type=RTDType.PT_3750,
            resistance_config=ResistanceConfiguration.FOUR_WIRE,
            current_excit_source=ExcitationSource.INTERNAL,
            current_excit_val=0.0005,
        )

        # task.timing.cfg_samp_clk_timing(5.0, sample_mode=AcquisitionType.CONTINUOUS)

        # Create internal calibration state
        state = State()
        state.task = task

        # Turn on the Heater

        try:
            # Collect Data for all the temperatures
            state.calibrateProbe()

            print("Finished Collecting Data")
            print(state.getCalibrationData())

        except KeyboardInterrupt:
            pass
        finally:
            task.stop()
            state.ser.close()


if __name__ == "__main__":

    main()
