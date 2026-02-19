I want to hook up all of the pins on the ad7606 to the BBB for 16bit parallel read.

i have freed up the BBB by disabling the hdmi video, hdmi audio, and on board ADC.

I have already edited the /boot/uEnv.txt file and rebooted the BBB to make sure the changes take effect.

Here are the states of all the pins on the board right now.
@terminal:ssh 

DO NOT use the eMMC pins.


for the databus pins, i would like to make it easy for me to wire in the pins.  My AD7606 breakout board has the Databus pins in the following order:
DB1, DB0, DB3, DB2, DB5, DB4, etc.  With this said, i would like to choose pins to map in a continuous block if possible so that it looks like the following:

p8.7->db1, p8.8->db0, p8.9->db3, p8.10->db2, p8.11->db5, p8.12->db4, etc.

obviously make sure we choose free pins and if we cannot choose a group of pins all together, make sure that the pin mapping is in BBB ascending order while mapping to the ADC databus pins in the order mentioned (DB1, DB0, DB3, DB2, DB5, DB4, etc.). this will make it easiest for me to wire up the AD7606 to the BBB.


make sure to update the 
pru_main.c
 , 
pru_config.h
 , and the 
Makefile#L183-194
 (to set the config-pin for each of the pins used)


ask me if you want to run any commands on the BBB.
if we still cannot map all the AD7606 pins to the BBB for PRU0 to use, then split the pins such that PRU0 does the latching and reads the first 8 databus bits of the AD7606 ADC and then PRU1 reads the second set of 8 databus bits.
prefer to use just one PRU and keep the implementation simple if possible.

do not use risky pins that may cause boot issues such as the eMMC pins.

update the 
wiring-diagrams.md
  with the chosen pin outs using a nice table to show the wiring setup.