from dataclasses import dataclass
import serial
import time

import nidaqmx
from nidaqmx.constants import AcquisitionType, ThermocoupleType, TemperatureUnits, RTDType, ResistanceConfiguration, ExcitationSource


@dataclass
class State:
    ser: serial = 0
    task: nidaqmx.Task = 0
    curTemp: float = 0
    curSetpoint: float = 0
    curStability: bool = 0
    probeTemp: float = 0
    RTDTemp: float = 0


testPoints = [76, 80]
testPoints = [125, 150, 175, 125, 100, 75]

dataPoints = []


def storeState(state: State, cmd: str, data: str):

    match cmd:
        case "SOUR:SENS:DATA?":
            state.curTemp = float(data)
        case "SOUR:SPO?":
            state.curSetpoint = float(data)
        case "SOUR:STAB:TEST?":
            state.curStability = bool(int(data))


def createSerial() -> serial:
    return serial.Serial(
        port="COM7",
        baudrate=9600,
        timeout=0.1,
        stopbits=serial.STOPBITS_ONE,
    )


def takeData(state: State) -> float:
    dataPoints.append((state.curTemp, state.probeTemp))
    print(str(state.curTemp) + " Degrees: " + str(state.probeTemp))


def setTemp(state: State, temp: float):

    writeSerial(ser, "SOUR:SPO " + str(temp))
    writeSerial(ser, "SOUR:SPO?")

    while abs(float(readSerial(ser)) - temp) > 0.005:
        writeSerial(ser, "SOUR:SPO " + str(temp))
        time.sleep(0.005)
        writeSerial(ser, "SOUR:SPO?")


def periodicSerial(state: State) -> State:

    command = ["SOUR:SENS:DATA?", "SOUR:STAB:TEST?", "SOUR:SPO?"]

    # command = "SOUR:SENS:CAL:PAR1\r"
    # Read Current Temperature - "SOUR:SENS:DATA?\r"
    # Read Setpoint - "SOUR:SPO?\r"
    # Write 75.0C as setpoint - "SOUR:SPO 75.0\r"
    # Read if Temperature Stable - "SOUR:STAB:TEST?\r"
    # Set Beep on temperature stability - "SOUR:STAB:BEEP?\r"
    # Heater On or Off - "OUTP:STAT 0\r"

    for cmd in command:
        writeSerial(ser, cmd)
        storeState(state, cmd, readSerial(ser))

    data = state.task.read()
    state.probeTemp = data[0]
    state.RTDTemp = data[1]

    return state


def writeSerial(ser: serial, cmd: str):

    cmd = cmd + "\r"
    # print(cmd)
    ser.write(bytes(cmd, "ascii"))


def readSerial(ser: serial) -> str:

    text = ""
    msg = ser.read().decode()
    while msg != "\r":
        text += msg
        msg = ser.read().decode()
    return text


def collectData(state: State):

    for temp in testPoints:

        setTemp(state, temp)

        while True:

            time.sleep(5)

            # Update State from Device
            state = periodicSerial(state)
            print(state)

            # If Temperature is stable
            if state.curStability == True:
                takeData(state)
                break


def main():

    state = State()

    # Thermalcouple Setup -- MUST CLOSE TASK
    with nidaqmx.Task() as task:
        task.ai_channels.add_ai_thrmcpl_chan(
            "cDAQ1Mod3/ai14",
            units=TemperatureUnits.DEG_C,
            thermocouple_type=ThermocoupleType.T,
        )
        task.ai_channels.add_ai_rtd_chan(
             "cDAQ1Mod1/ai0",
             rtd_type=RTDType.PT_3851,
             resistance_config=ResistanceConfiguration.FOUR_WIRE,
             current_excit_source=ExcitationSource.INTERNAL,
             current_excit_val=.0005
        )

        # task.timing.cfg_samp_clk_timing(5.0, sample_mode=AcquisitionType.CONTINUOUS)
        state.task = task

        # Turn on the Heater
        writeSerial(ser, "OUTP:STAT 1")

        try:
            # Collect Data for all the temperatures
            collectData(state)

            print("Finished Collecting Data")
            print(dataPoints)

        except KeyboardInterrupt:
            pass
        finally:
            task.stop()


if __name__ == "__main__":

    ser = createSerial()
    main()
