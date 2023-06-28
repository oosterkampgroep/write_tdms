# write tdms 

Read data from National Instruments DAQ, plot the date and write into tdms file. 
This module opens a tkinter window in which the folder to
save the data into can be chosen, maximum amount of samples per file, the DAQ channel to read the data from, the range of said DAQ and the sample rate. 
This module is tested on a NI myDAQ up untill a sample rate of 200k samples per second (the maximum sample rate of the myDAQ).