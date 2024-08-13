from dataclasses import dataclass
import serial
import time

@dataclass
class State:
  ser: serial        = 0
  curTemp: float     = 0
  curSetpoint: float = 0
  curStability: bool = 0

#testPoints = [ 50, 75, 100, 125]
testPoints = [ 130, 150, 175, 125, 100 ]

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
      port='/dev/ttyUSB0',
      baudrate=9600,
      timeout=.1,
      stopbits=serial.STOPBITS_ONE,
      )

def takeData(temp: float):
    print("Data Has Been Taken at " + str(temp) + " Degrees")

def setTemp(state: State, temp: float):

  writeSerial(ser, "SOUR:SPO " + str(temp))
  writeSerial(ser, "SOUR:SPO?")

  while abs(float(readSerial(ser)) - temp) > .005:
    writeSerial(ser, "SOUR:SPO " + str(temp))
    time.sleep(.005)
    writeSerial(ser, "SOUR:SPO?")


def periodicSerial(state: State) -> State:

  command = [ "SOUR:SENS:DATA?", "SOUR:STAB:TEST?", "SOUR:SPO?" ]

  #command = "SOUR:SENS:CAL:PAR1\r"
  # Read Current Temperature - "SOUR:SENS:DATA?\r"
  # Read Setpoint - "SOUR:SPO?\r"
  # Write 75.0C as setpoint - "SOUR:SPO 75.0\r"
  # Read if Temperature Stable - "SOUR:STAB:TEST?\r"
  # Set Beep on temperature stability - "SOUR:STAB:BEEP?\r"
  # Heater On or Off - "OUTP:STAT 0\r"

  for cmd in command:
    writeSerial(ser, cmd)
    storeState(state, cmd, readSerial(ser))

  return state
    
def writeSerial(ser: serial, cmd: str):

  cmd = (cmd + '\r')
  print(cmd)
  ser.write(bytes(, 'ascii'))


def readSerial(ser: serial) -> str:

  text = ""
  msg = ser.read().decode()
  while (msg != '\r'):
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
      if(state.curStability == True):
        takeData(temp)
        break

def main():

  state = State()

  # Turn on the Heater
  writeSerial(ser, "OUTP:STAT 1")

  # Collect Data for all the temperatures
  collectData(state)

  print("Finished Collecting Data")
  

if __name__ == "__main__":

  ser = createSerial()
  main()
