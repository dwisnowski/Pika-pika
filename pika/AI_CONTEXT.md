**Remember:**

This project is code for a Beagebone black.  This only runs on the beaglebone black.  DO NOT try to run commands because this editor is running on a Mac Book Pro.   Give me the commands you would like to run and i will run them on the Beaglebone Black using a ssh terminal.



The Pika project is a high-performance Linux userspace application responsible for consuming high-speed ADC data from the PRU, performing real-time signal processing, and storing events and decimated data to disk.



**Remember:**

There are `3` parts to this project:

* The PRU which is responsible for interfacing with the AD7606 ADC

* The Datalogger which reads the ringbuffer of data from the PRU and brings the data into the linux userspace.  This analyzes the data and stores interesting events to disk.  the remainder of the data is decimated and stored to disk too.

* The Webapp which is responsible for using the decimated data and event data from the datalogger to render charts and graphs and insights on a web page.


**Remember:**
The input to the AD7606 is a ZMPT101B which is plugged into 120VAC 60Hz mains.

The goal of this project is to show case insights about the 120VAC mains so that i can analyze my power