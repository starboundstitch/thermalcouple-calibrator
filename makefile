FQBN=arduino:avr:nano
PORT=/dev/ttyUSB0
OPTS=-b $(FQBN) -p $(PORT)
all:
	echo Not Implemented

c_comp:
	arduino-cli compile controller/controller.ino $(OPTS)

c_up:
	arduino-cli upload controller/controller.ino $(OPTS)

s_start:
	python application/app.py
