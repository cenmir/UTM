# Universal Testing Machine

Based on the work done by [Stefan from CNC kitchen](https://www.youtube.com/watch?v=uvn-J8CbtzM) and the students [Stephen Jose Mathew and Vijay Francis](https://hj.diva-portal.org/smash/get/diva2:1472019/FULLTEXT01.pdf).



## Firmware

The firmware is is based on the HX711 amplifier, uses 10Hz polling rate and the TMC2160 driver on two MKS TMC2160_57 board, each driving a AMP57TH76-4280 Nema 23 stepper motor. The motors are geared down 20 times using EPL64/2 planetary gears. 

Rob Tillarts HX711 library is used to read raw values at 10Hz non-blocking (when data is available).

For drving the motors, one controll signal is sent to both drivers using the MobaTools library.

Additionally on each motor shaft end a magnet is attached and its rotational position contactlessly measured by a AS5600 magnetic encoder using Rob Tillats library. This is used to measure the rotational speed of the motors.


