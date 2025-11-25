## To Do

// Number of probes slopes in tolerance (bitmap)
// good UX for typo in probe name
// debug mode which gives additional info on initialization etc


// Actual Readme starts here

# thermocouple-calibrator

A simple python program that automates the thermocouple calibration process for arbitrary numbers of National Instruments thermocouples using a fluke dry well and RTD temperature baseline.

## Installation

You can grab the latest bundled windows release in the [releases](https://github.com/starboundstitch/thermalcouple-calibrator/releases) page. Extract the zip file and the program should be useable by double-clicking the executable file.

## Configuration

For the program to actually calibrate probes, one will need to edit the config file. This should be packaged with the current release zip and can be edited with any text editor. The configuration file syntax is yaml and a reference guide can be found [here](https://docs.ansible.com/ansible/latest/reference_appendices/YAMLSyntax.html).

### RTD Setup

This program uses an RTD with a parabolic calibration curve which is defined in the config file. The `high_coefficient` corresponds to the x^2 value. The `low_coefficient` corresponds to the x value, and the `constant_coefficient` corresponds to the constant offset.

```yaml
RTD:
  high_coefficient: 0.001139
  low_coefficient: 2.320800
  constant_coefficient: -243.417949
```

Since there is only ever 1 RTD used for calibration, you need to set up a `channel` for its use which you can find in the `NI MAX` software for your probe.

```yaml
RTD:
  channel: "ai0"
```

### Thermocouple Setup

This program allows an arbitrary number of thermocouples of the same type to be calibrated at once. This type needs to be specified by editing the `type` in the `thermocouple` section.

```yaml
thermocouple:
  type: 'K'
```

Additionally, the thermocouples need to be specified under the `channel` key as a list. Make sure you include `ai` in the name of the thermocouple probe; this once again can be found in the `NI MAX` software.
```yaml
thermocouple:
  channel:
    - "ai0"
    - "ai10"
```

### Device Setup

In addition to the channel, one needs to specify the NI `device` and `module` that are to be used for the thermocouples and the RTD. This program supports a single device and module for *all* thermocouples and a separate device and module for the RTD. Please find the corresponding modules and devices in the `NI MAX` software and input them into the config file.

```yaml
RTD:
  device: "cDAQ2"
  module: "Mod1"
thermocouple:
  device: "cDAQ2"
  module: "Mod3"
```

### Serial Setup

The program needs to communicate with the fluke dry well. Connect a serial cable to the dry well. Once that is done, you should have a serial device which can be found in Windows Device Manager under the `COM Ports` section. You can input the `COMX` where `X` is a number into the program to tell it which serial device to use.

```yaml
serial:
  port: "COM5"
```

### Calibration Setup

The program also has some settings to define how the calibration works. The first option is to manually define every single point that you want to calibrate. This allows you to choose any possible combination of points and should be used in case of special requirements or a desire for specific accuracy. The following example calibrates at 50C, then 70C, then 90C.

```yaml
calibration:
  points: [ 50, 70, 90 ]
```

Alternatively, the program can generate points for you given a minimum and maximum temperature and a number of points. The algorithm will start in the middle of the temperature range and then decrease and increase temperature on each respective calibration point. It will start at a lower general temperature and work its way to a higher general temperature in a kinda stair pattern.

```yaml
calibration:
  generate:
    enabled: True
    points: 10
    max_temp: 150
    min_temp: 50
```

The output file name can be adjusted as well. By default, it outputs to "calibration.xlsx".

```yaml
calibration:
  file_name: "calibration.xlsx"
```

Lastly, you can change the polling and stability time. The `polling_time` attribute corresponds to the period of time between temperature samples by the program. The `stability_time` attribute corresponds to the period of time that the temperature must be stable for before a calibration sample can be taken.

```yaml
calibration:
  polling_time: 5
  stability_time: 60
```
