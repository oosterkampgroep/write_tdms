""" write_tdms.py
Read data from National Instruments DAQ, plot the date and write into 
tdms file. This module opens a tkinter window in which the folder to
save the data into can be chosen, maximum amount of samples per file,
the DAQ channel to read the data from, the range of said DAQ and the 
sample rate. This module is tested on a NI myDAQ up untill a sample rate
of 200k samples per second (the maximum sample rate of the myDAQ).
"""


import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk
import ctypes

import numpy as np
import matplotlib.backends.backend_tkagg as tkagg
from matplotlib.figure import Figure
import nidaqmx
import nidaqmx.constants as nico
from nidaqmx.stream_readers import AnalogMultiChannelReader


__author__ = "Jaimy Plugge"


class Picker(ttk.Frame):

    def __init__(self, master=None,activebackground='#b1dcfb',values=[],entry_wid=None,activeforeground='black', selectbackground='#003eff', selectforeground='white', command=None, borderwidth=1, relief="solid"):

        self._selected_item = None

        self._values = values

        self._entry_wid = entry_wid

        self._sel_bg = selectbackground 
        self._sel_fg = selectforeground

        self._act_bg = activebackground 
        self._act_fg = activeforeground

        self._command = command
        ttk.Frame.__init__(self, master, borderwidth=borderwidth, relief=relief)

        self.bind("<FocusIn>", lambda event:self.event_generate('<<PickerFocusIn>>'))
        self.bind("<FocusOut>", lambda event:self.event_generate('<<PickerFocusOut>>'))

        self.dict_checkbutton = {}
        self.dict_checkbutton_var = {}
        self.dict_intvar_item = {}

        for index,item in enumerate(self._values):

            self.dict_intvar_item[item] = tk.IntVar()
            self.dict_checkbutton[item] = ttk.Checkbutton(self, text = item, variable=self.dict_intvar_item[item],command=lambda ITEM = item:self._command(ITEM))
            self.dict_checkbutton[item].grid(row=index, column=0, sticky=tk.NSEW)
            self.dict_intvar_item[item].set(0)


class Combopicker(ttk.Entry, Picker):
    def __init__(self, master, values= [] ,entryvar=None, entrywidth=None, entrystyle=None, onselect=None,activebackground='#b1dcfb', activeforeground='black', selectbackground='#003eff', selectforeground='white', borderwidth=1, relief="solid"):

        if entryvar is not None:
            self.entry_var = entryvar
        else:
            self.entry_var = tk.StringVar()

        entry_config = {}
        if entrywidth is not None:
            entry_config["width"] = entrywidth

        if entrystyle is not None:
            entry_config["style"] = entrystyle

        ttk.Entry.__init__(self, master, textvariable=self.entry_var, **entry_config, state = "readonly")

        self._is_menuoptions_visible = False

        self.picker_frame = Picker(self.winfo_toplevel(), values=values,entry_wid = self.entry_var,activebackground=activebackground, activeforeground=activeforeground, selectbackground=selectbackground, selectforeground=selectforeground, command=self._on_selected_check)

        self.bind_all("<1>", self._on_click, "+")

        self.bind("<Escape>", lambda event: self.hide_picker())

    @property
    def current_value(self):
        try:
            value = self.entry_var.get()
            return value
        except ValueError:
            return None

    @current_value.setter
    def current_value(self, INDEX):
        self.entry_var.set(values.index(INDEX))

    def _on_selected_check(self, SELECTED):

        value = []
        if self.entry_var.get() != "" and self.entry_var.get() != None:
            temp_value = self.entry_var.get()
            value = temp_value.split(",")

        if str(SELECTED) in value:
            value.remove(str(SELECTED))

        else:    
            value.append(str(SELECTED))

        value.sort()

        temp_value = ""
        for index,item in enumerate(value):
            if item!= "":
                if index != 0:
                    temp_value += ","
                temp_value += str(item)

        self.entry_var.set(temp_value)

    def _on_click(self, event):
        str_widget = str(event.widget)

        if str_widget == str(self):
            if not self._is_menuoptions_visible:
                self.show_picker()
        else:
            if not str_widget.startswith(str(self.picker_frame)) and self._is_menuoptions_visible:
                self.hide_picker()

    def show_picker(self):
        if not self._is_menuoptions_visible:
            self.picker_frame.place(in_=self, relx=0, rely=1, relwidth=1 )
            self.picker_frame.lift()

        self._is_menuoptions_visible = True

    def hide_picker(self):
        if self._is_menuoptions_visible:
            self.picker_frame.place_forget()

        self._is_menuoptions_visible = False


class Reader: 
    def __init__(self, physical_channels, sample_rate, block_size, logging, 
                 volt_range, termconfig, callback):
        self.settings = { "physical channels"  : physical_channels,
                          "number of channels" : len(
                            nidaqmx._task_modules.channels.channel.Channel(
                            0,physical_channels).channel_names
                            ),
                          "sample rate"        : sample_rate,
                          "sample block size"  : block_size
                        }

        self.physical_channels = physical_channels
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.logging = logging
        self.min, self.max = volt_range
        self.termconfig = termconfig
        self.callback = callback

        self.data_in = np.zeros((self.physical_channels.count(",")+1, self.settings["sample block size"]),'d')

    def configure_task(self):
        self.task = nidaqmx.Task()
        self.task.ai_channels.add_ai_voltage_chan(
            self.settings["physical channels"],
            terminal_config=self.termconfig,
            min_val=self.min, max_val=self.max)
        self.task.in_stream.auto_start=0

        self.task.timing.cfg_samp_clk_timing(
            rate=self.sample_rate, source="OnboardClock", 
            sample_mode= nico.AcquisitionType.CONTINUOUS,
            samps_per_chan=10*self.sample_rate)

        self.channel_reader = AnalogMultiChannelReader(self.task.in_stream)

    def start_reading(self):
        self.task.register_every_n_samples_acquired_into_buffer_event(
            self.block_size, self.callback)
        self.task.start()
        
    def pausefunc(self):
        self.task.stop()

    def stopfunc(self):
        self.pausefunc()
        self.task.close()
        self.task = False


class Mainwindow:
    def __init__(self):
        self.mainwindow = tk.Tk()
        self.mainwindow.title('Write TDMS')

        # Make sure the program stops as the window gets closed
        self.mainwindow.protocol("WM_DELETE_WINDOW", self.quit_me)

        # UI Settings
        self.entrywidth = 10
        self.xpadding = (5, 5)
        self.ypadding = (2, 2)
        self.relief = tk.RIDGE

        self.createmenu()

        # Find connected devices
        system = nidaqmx.system.System.local()
        self.channellist = []
        try:
            for device in system.devices:
                for channel in device.ai_physical_chans:
                    self.channellist.append(channel.name)
        except:
            tk.messagebox.showerror(
                'DAQ error', 
                'Error: Could not find a DAQ connected to your device.')

        self.phys_chans = tk.StringVar()
        #self.phys_chans.set(self.channellist[0])

        self.sample_rate = tk.StringVar()
        self.sample_rate.set("200k")

        self.sample_chan = tk.StringVar()
        self.sample_chan.set("200k")

        self.logging = False

        self.max_samples_file = tk.IntVar()
        self.max_samples_file.set(3000000)

        self.reader = False

        self.create_gui()
        self.plot_frame()

        self.mainwindow.mainloop()

    def createmenu(self):
        """
        This function creates the top menu. The default settings 
        option does not work yet!
        """
        menubar = tk.Menu(self.mainwindow)
        windowmenu = tk.Menu(menubar, tearoff=0)
        #windowmenu.add_command(label="Set values to default", 
        #                       command=self.defaultsettings)
        windowmenu.add_command(label="Choose folder", command=self.openfolder)
        windowmenu.add_separator()
        windowmenu.add_command(label="Exit", command=self.quit_me)
        menubar.add_cascade(label="Window", menu=windowmenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="Help", command=self.helpme)
        menubar.add_cascade(label="Help", menu=helpmenu)
        self.mainwindow.config(menu=menubar)

    def create_gui(self):
        # controls
        width_names = 20
        width_number = 7

        xpad = (5,5)
        ypad = (2,2)

        controlsframelabel = ttk.Label(text="Controls", 
                                       foreground="black")
        controlsframe = ttk.LabelFrame(self.mainwindow, 
                                       labelwidget=controlsframelabel, 
                                       relief=self.relief)
        controlsframe.pack(side="left")

        lbl_tdms_folder = tk.Label(master=controlsframe, text="TDMS Folder")
        self.entry_tdms_folder = tk.Entry(master=controlsframe, 
                                        width=width_names)
        btn_folder = tk.Button(master=controlsframe, text="Browse", 
                               command=self.openfolder)

        self.tdms_filename_var = tk.StringVar()
        self.tdms_filename_var.set("Choose Folder")
        lbl_tdms_filename = tk.Label(master=controlsframe, text="TDMS Filename")
        lbl_tdms_filename_display = tk.Label(
            master=controlsframe, textvariable=self.tdms_filename_var, 
            relief=tk.SUNKEN, anchor='w', width=50)

        self.amount_samples_var = tk.IntVar()
        self.amount_samples_var.set(0)
        lbl_amount_samples = tk.Label(master=controlsframe, 
                                      text="# Samples in File")
        lbl_amount_samples_display = tk.Label(
            master=controlsframe, textvariable=self.amount_samples_var, 
            relief=tk.SUNKEN, anchor='w')

        lbl_max_samplesfile = tk.Label(master=controlsframe, 
                                       text="Max Samples/File")
        entry_max_samplesfile = tk.Entry(master=controlsframe, 
                                         width=width_number, 
                                         textvariable=self.max_samples_file)

        lbl_phys_chan = tk.Label(master=controlsframe, text="Physical Channel")
        self.combo_phys_chan = Combopicker(master=controlsframe, 
                                           values =self.channellist, 
                                           entryvar=self.phys_chans,
                                           entrywidth=25)

        # self.combo_phys_chan = ttk.Combobox(master=controlsframe, 
        #                                     values=self.channellist, 
        #                                     textvariable=self.phys_chans)
        # self.combo_phys_chan.set(self.phys_chans.get())
        # self.combo_phys_chan['state'] = 'readonly'

        lbl_range = tk.Label(master=controlsframe, text="Range")
        self.rangedict = {"+1 / -1": (-1,1), 
                          "+5 / -5": (-5,5), 
                          "+10 / -10": (-10,10)
                          }
        self.rangevar = tk.StringVar()
        self.rangevar.set("+5 / -5")
        combo_range = ttk.Combobox(master=controlsframe, 
                                   values=list(self.rangedict.keys()), 
                                   width=width_number, 
                                   textvariable=self.rangevar)
        combo_range.set(self.rangevar.get())
        combo_range['state'] = 'readonly'

        lbl_samps_per_chan = tk.Label(master=controlsframe, 
                                      text="Samples/Channel")
        entry_samps_per_chan = tk.Entry(master=controlsframe, width=width_number,
                                        textvariable=self.sample_chan)

        lbl_sample_rate = tk.Label(master=controlsframe, text="Sample Rate")
        entry_sample_rate = tk.Entry(master=controlsframe, width=width_number, 
                                     textvariable=self.sample_rate)
                                     
        lbl_termconfig = tk.Label(master=controlsframe, text="Terminal configuration")
        self.termconfigdict = {"Default": nico.TerminalConfiguration.DEFAULT,
 							   "Differential": nico.TerminalConfiguration.DIFF, 
 							   #"Differential": nico.TerminalConfiguration.BAL_DIFF, 
                                "RSE": nico.TerminalConfiguration.RSE, 
                                "NRSE": nico.TerminalConfiguration.NRSE,
                                }
        self.termconfigvar = tk.StringVar()
        self.termconfigvar.set("Default")
        combo_termconfig = ttk.Combobox(master=controlsframe, 
                                        values=list(self.termconfigdict.keys()), 
                                        width=width_number, 
                                        textvariable=self.termconfigvar)
        combo_termconfig.set(self.termconfigvar.get())
        combo_termconfig['state'] = 'readonly'

        self.btn_logging = tk.Button(master=controlsframe, text="Logging", 
                                     command=self.logging_toggle, 
                                     bg="red")
        self.btn_start = tk.Button(master=controlsframe, text="Start", 
                                   command=self.start_reading)
        self.btn_stop = tk.Button(master=controlsframe, text="Stop", 
                                  command=self.stop_reading)

        self.btn_logging.config(state="disabled")
        self.btn_stop.config(state="disabled")

        lbl_tdms_folder.grid(row=0,column=0,sticky="e",padx=xpad,pady=ypad)
        self.entry_tdms_folder.grid(row=0,column=1,columnspan=3,sticky="nsew",padx=xpad,pady=ypad)
        btn_folder.grid(row=0,column=4,sticky="ew",padx=xpad,pady=ypad)
        lbl_tdms_filename.grid(row=1,column=0,sticky="e",padx=xpad,pady=ypad)
        lbl_tdms_filename_display.grid(row=1,column=1,columnspan=4,sticky="nsew",padx=xpad,pady=ypad)
        lbl_amount_samples.grid(row=2,column=0,sticky="e",padx=xpad,pady=ypad)
        lbl_amount_samples_display.grid(row=2,column=1,sticky="nsew",padx=xpad,pady=ypad)
        lbl_max_samplesfile.grid(row=2,column=3,sticky="e",padx=xpad,pady=ypad)
        entry_max_samplesfile.grid(row=2,column=4,sticky="nsew",padx=xpad,pady=ypad)
        lbl_phys_chan.grid(row=3,column=0,sticky="e",padx=xpad,pady=ypad)
        self.combo_phys_chan.grid(row=3,column=1,sticky="nsew",padx=xpad,pady=ypad)
        lbl_range.grid(row=3,column=3,sticky="e",padx=xpad,pady=ypad)
        combo_range.grid(row=3,column=4,sticky="nsew",padx=xpad,pady=ypad)
        lbl_samps_per_chan.grid(row=4,column=0,sticky="e",padx=xpad,pady=ypad)
        entry_samps_per_chan.grid(row=4,column=1,sticky="nsew",padx=xpad,pady=ypad)
        lbl_sample_rate.grid(row=4,column=3,sticky="e",padx=xpad,pady=ypad)
        entry_sample_rate.grid(row=4,column=4,sticky="nsew",padx=xpad,pady=ypad)
        lbl_termconfig.grid(row=5,column=0,sticky="e",padx=xpad,pady=ypad)
        combo_termconfig.grid(row=5,column=1,sticky="nsew",padx=xpad,pady=ypad)

        self.btn_logging.grid(row=6,column=0,sticky="nsew",padx=xpad,pady=ypad)
        self.btn_start.grid(row=6,column=1,sticky="nsew",padx=xpad,pady=ypad)
        self.btn_stop.grid(row=6,column=3,sticky="nsew",columnspan=2,padx=xpad,pady=ypad)

    def plot_frame(self):
        dataframelabel = ttk.Label(text="Data written to TDMS", 
                                   foreground="black")
        dataframe = ttk.LabelFrame(self.mainwindow, labelwidget=dataframelabel, 
                                   relief=self.relief)
        dataframe.pack(expand=True, fill="both", side="right")

        self.fig = Figure(figsize=(12,3), tight_layout=True)
        self.axs = self.fig.add_subplot(111)
        self.axs.set_xlabel('Time [s]')
        self.axs.set_ylabel('Amplitude [V]')
        self.axs.grid()

        self.canvas = tkagg.FigureCanvasTkAgg(self.fig, master=dataframe)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(expand=True, fill="both", side="top")

        self.navtoolbar = tkagg.NavigationToolbar2Tk(self.canvas, dataframe)

    def openfolder(self):
        self.folder = tk.filedialog.askdirectory()
        self.entry_tdms_folder.insert(0,self.folder)
        self.tdms_filename_var.set(self.folder
                                   +'/TDMS_'
                                   +datetime.now().strftime("%Y%m%d-%H%M%S")
                                   +".tdms")
        self.btn_logging.config(state="normal")
        self.logging_toggle()

    def start_reading(self):
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.btn_logging.config(state="disabled")

        samp_rate = self.int_from_str(self.sample_rate.get())
        samp_chan = self.int_from_str(self.sample_chan.get())

        if samp_chan/samp_rate < 0.1 or samp_chan/samp_rate > 5:
            tk.messagebox.showerror(
                'Samples/channel incompatible with chosen sample rate', 
                ("To make sure the program keeps working, the " 
                 + "samples/channel should be bigger than a tenth "
                 + "of the sample rate and smaller than sample rate itself."))
            
            self.btn_start.config(state="normal")
            self.btn_stop.config(state="disabled")

            #if self.folder_chosen:
            #    self.btn_logging.config(state="normal")

            self.amount_samples_var.set(0) 

        else:
            try:
                self.reader = Reader(self.phys_chans.get(), samp_rate, samp_chan, 
                                     self.logging, self.rangedict[self.rangevar.get()], 
                                     self.termconfigdict[self.termconfigvar.get()], 
									 self.callback)
                
                self.x_axis = np.linspace(0, (samp_chan/samp_rate), samp_chan)

                self.reader.configure_task()
                if self.logging:
                    name = '/TDMS_'+datetime.now().strftime("%Y%m%d-%H%M%S")+".tdms"
                    self.reader.task.in_stream.configure_logging(
                        self.folder+name, nidaqmx.constants.LoggingMode.LOG_AND_READ,
                        group_name="group")
                    self.tdms_filename_var.set(self.folder+name)
                    self.reader.task.in_stream.input_buf_size = self.int_from_str(
                        self.sample_rate.get()) * 5

                self.reader.start_reading()

            except nidaqmx.errors.DaqError as error:
                self.show_error(error)

    def multichan_toggle(self):
        if self.multichan:
            self.multichan = False
            self.combo_phys_chan['state'] = 'readonly'
        else:
            self.multichan = True
            self.combo_phys_chan['state'] = 'normal'

    def logging_toggle(self):
        if self.logging:
            self.btn_logging.config(bg="red")
            self.logging = False
        else:
            self.btn_logging.config(bg="green")
            self.logging = True

    def stop_reading(self):
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")
        self.btn_logging.config(state="normal")

        self.amount_samples_var.set(0)        

        self.reader.stopfunc()

    def callback(self, task_handle, every_n_samples_event_type, 
                 number_of_samples, callback_data):
        self.reader.channel_reader.read_many_sample(
            self.reader.data_in, 
            number_of_samples_per_channel=self.reader.settings["sample block size"], 
            timeout=nidaqmx.constants.WAIT_INFINITELY)
        self.axs.cla()
        for row in self.reader.data_in:
            self.axs.plot(self.x_axis, row)
        self.axs.set_xlabel('Time [s]')
        self.axs.set_ylabel('Amplitude [V]')
        self.axs.grid()
        self.canvas.draw()
        self.navtoolbar.update()
        if self.logging:
            self.amount_samples_var.set(self.amount_samples_var.get() 
                                        + self.int_from_str(self.sample_rate.get()))
        if self.amount_samples_var.get() >= self.max_samples_file.get():
            name = '/TDMS_'+datetime.now().strftime("%Y%m%d-%H%M%S")+".tdms"
            self.reader.task.in_stream.start_new_file(self.folder+name)
            self.tdms_filename_var.set(self.folder+name)
            self.amount_samples_var.set(0)
            
        return 0

    def int_from_str(self, var_string):
        var_string = var_string.replace("k", "E3")
        var_string = var_string.replace("M", "E6")
        while var_string[-1] not in "1234567890":
            var_string = var_string[:-1]
        return int(float(var_string))

    def defaultsettings(self):
        print("werkt nog niet")

    def quit_me(self):
        print('Closing the program')
        self.mainwindow.quit()
        self.mainwindow.destroy()
        if self.reader != False:
            if self.reader.task != False:
                self.reader.stopfunc()
                print("Stopped Reader")

    def show_error(self, error):
        from nidaqmx._lib import lib_importer
        error_buffer = ctypes.create_string_buffer(2048)
        cfunc = lib_importer.windll.DAQmxGetExtendedErrorInfo
        cfunc(error_buffer, 2048)

        self.stop_reading()
        tk.messagebox.showerror(str(error.error_code), str(nidaqmx.errors.DaqError(error_buffer.value.decode("utf-8"), error.error_code)))

    def helpme(self):
        try:
            os.startfile("README.md")
        except:
            print("Can't find the readme file in the working folder.")


def main():
    Mainwindow()


if __name__ == "__main__":
    main()