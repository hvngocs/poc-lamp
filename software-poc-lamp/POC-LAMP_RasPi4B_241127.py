"""
POC-LAMP-Chip Raspberry Pi 4B_20241101

Firmware: Bottom + 1, Top = Bottom + 4, tempadd = 1;
Firmware: Limit minimum room temperature 10 degC;
Firmware: ADC setGain(GAIN_ONE);
Reaction teperature set for Sam, Camp: 67 degC and COV: 66 degC;
Chip postion error <100;
Reaction time set for COV, Sal: 50 min and Cam: 60 min;
Start calculation time at 5 min;
Base line at 8000 (rateLimit = 8000); Derivative at 350 (noiseThreshold = 350);

Software define:
 WELL 1A, WELL 1B, WELL 2A, WELL 2B, WELL 3A, WELL 4A, WELL 1C, WELL 1D,  WELL 2C, WELL 2D, WELL 3D, WELL 4D
 well 1 , 2      , 3      , 4      , 5      , 6      , 7      , 8      , 9       , 10     , 11     , 12

PCB design:
 LED     1 , 1      , 2      , 2      , 2      , 3      , 3      ,  3      , 4      , 4      , 3      ,  2
 WELL    4A, WELL 3A, WELL 2A, WELL 1A, WELL 1B, WELL 1C, WELL 1D,  WELL 2D, WELL 3D, WELL 4D, WELL 2C,  WELL 2B
 ADC No. 1 , 2      , 3      , 4      , 5      , 6      , 7      ,  8      , 9      , 10     , 11     ,  12
	ads1-0 , ads1-1 , ads1-2 , ads1-3 , ads2-0 , ads2-1 , ads2-2 ,  ads2-3 , ads3-0 , ads3-1 , ads3-2 ,  ads3-3
"""

import os, sys

if sys.version_info[0] == 3:
    import tkinter as tk
    from tkinter import *
    from tkinter import ttk

    from tkinter.filedialog import asksaveasfilename, askopenfilename
    from tkinter import messagebox as mess
else:
    import Tkinter as tk
    from Tkinter import *
    from Tkinter import ttk

    from tkFileDialog import asksaveasfilename
    import tkMessageBox as mess

from PIL import Image, ImageTk

import time

# ----- for data processing
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from drawnow import *
import numpy as np
import math
import xlsxwriter
import csv
from datetime import datetime
from threading import Thread
from multiprocessing import Queue, Process

#-------Import blockchain----------------------
import asyncio
import websockets
import json

#-------Import GPS-----------------------------
import serial
import pynmea2

#-------Interface with RasPI--------------------
# ----- for PID control
from PID import LampPID

# ----- for Adafruit MAX31855 temperature sensors
import RPi.GPIO as GPIO
# Raspberry Pi software SPI configuration.

# CLK = 11 # GPIO 11 connect to CLK of MAX31855
# CS1 = 5 # GPIO 5 connect to Top heater sensor CS
# CS2 = 6 # GPIO 6 connect to Bottom heater sensor SC
# DO  = 9 # GPIO 9 connect to Data of MAX31855

import board
import digitalio
import adafruit_max31855

spi = board.SPI()
cs1 = digitalio.DigitalInOut(board.D5)
cs2 = digitalio.DigitalInOut(board.D6)

sensor1 = adafruit_max31855.MAX31855(spi, cs1)  # Top heater
sensor2 = adafruit_max31855.MAX31855(spi, cs2)  # Bottom heater

# Import the ADS1x15 module.
import Adafruit_GPIO.SPI as SPI
import Adafruit_ADS1x15

# import Adafruit_ADS1x15
# Create an ADS1115 ADC (16-bit) instance.-----------------------
# adc = Adafruit_ADS1x15.ADS1115()
# GPIO 2 (SDA) connect to SDA of ADS1115
# GPIO 3 (SCL) connect to SCL of ADS1115
adc1 = Adafruit_ADS1x15.ADS1115(address=0x48, busnum=1)
adc2 = Adafruit_ADS1x15.ADS1115(address=0x49, busnum=1)
adc3 = Adafruit_ADS1x15.ADS1115(address=0x4A, busnum=1)

# Note you can change the I2C address from its default (0x48), and/or the I2C
# bus by passing in these optional parameters:
# adc = Adafruit_ADS1x15.ADS1115(address=0x49, busnum=1)

# Choose a gain of 1 for reading voltages from 0 to 4.09V.
# Or pick a different gain to change the range of voltages that are read:
#  - 2/3 = +/-6.144V
#  -   1 = +/-4.096V
#  -   2 = +/-2.048V
#  -   4 = +/-1.024V
#  -   8 = +/-0.512V
#  -  16 = +/-0.256V
# See table 3 in the ADS1015/ADS1115 datasheet for more info on gain.
GAIN = 1

# Function to launch Onboard virtual keyboard
def launch_keyboard():
    os.system("onboard &")  # Launch Onboard in the background
    time.sleep(2)  # Wait for Onboard to start
    position_keyboard()

# Function to position the Onboard keyboard
def position_keyboard():
    try:
        # Use wmctrl to get the Onboard window ID
        os.system("wmctrl -r Onboard -e 0,0,300,800,180")  # Move Onboard to x=0, y=300, with width 800 and height 180
    except Exception as e:
        print(f"Error positioning Onboard: {e}")

# Function to close Onboard virtual keyboard
def close_keyboard():
    os.system("pkill onboard")  # Kill the Onboard process

root = tk.Tk()
root.title('POC-LAMP')
root.geometry('800x480')

# Launch the keyboard when an entry field is focuseds
def on_entry_click(event):
    launch_keyboard()

# Close the keyboard when the window is closed
root.protocol("WM_DELETE_WINDOW", lambda: [close_keyboard(), root.destroy()])

# Avoid close program by pressing 'X'
#def disable_event():
#    pass
#root.protocol('WM_DELETE_WINDOW', disable_event)

#im = Image.open('POC_LAMPIcon.png')
#new_width  = 25
#new_height = 20
#im = im.resize((new_width, new_height), Image.ANTIALIAS)
#im.save('POC_LAMPIcon.png')

POC_LAMPIcon = tk.PhotoImage(file='POC_LAMPIcon.png')
root.tk.call('wm', 'iconphoto', root._w, POC_LAMPIcon)

# Create a figure and axis
fig, ax = plt.subplots()

# Set the size of the plot (figure size in inches)
fig.set_size_inches(8, 6)

plt.ion() # Enable interactive mode

canvas = fig.canvas
tk_window = canvas.manager.window

# Set the window position (x, y) and size (width, height) in pixel
tk_window.geometry('500x280+300+200')

class GuiPart:
    def __init__(self, master, queue):
        self.queue = queue
        self.master = master
        self.frameinit = Frame(master)
        self.master.option_add("*Font", "Arial 12")
        self.frameinit.pack(side=TOP, fill="both", expand=True, padx=2, pady=2)
        # --------------------------------------------------------------------------------------

        # Frame 1 (User Info)
        self.f1 = Frame(self.frameinit, relief=GROOVE, bd=4)
        self.f1.grid(row=0, column=0, rowspan=6, columnspan=2, padx=2, pady=2, sticky=W)

        self.lbdatetime = Label(self.f1, text=self.get_datetime(), bd=4)
        self.lbdatetime.grid(row=0, column=1, pady=2)

        # Labels and Entries for user data
        self.lbsystemID = Label(self.f1, text="System ID", width=10).grid(row=1, column=0, sticky=W)
        self.entrysystemID = Entry(self.f1, width=16)
        self.entrysystemID.grid(row=1, column=1, pady=2)
        self.entrysystemID.insert(END, "POC-LAMP 01")
        self.entrysystemID.bind("<FocusIn>", on_entry_click)

        self.lbusername = Label(self.f1, text="User Name", width=10).grid(row=2, column=0, sticky=W)
        self.entryusername = Entry(self.f1, width=16)
        self.entryusername.grid(row=2, column=1, pady=2)
        self.entryusername.insert(END, "Huynh Van Ngoc")
        self.entryusername.bind("<FocusIn>", on_entry_click)

        self.lbuserphone = Label(self.f1, text="Phone num", width=10).grid(row=3, column=0, sticky=W)
        self.entryuserphone = Entry(self.f1, width=16)
        self.entryuserphone.grid(row=3, column=1, pady=2)
        self.entryuserphone.insert(END, "91921931")
        self.entryuserphone.bind("<FocusIn>", on_entry_click)

        self.lbsamplename = Label(self.f1, text="Sample ID", width=10).grid(row=4, column=0, sticky=W)
        self.entrysampleID = Entry(self.f1, width=16)
        self.entrysampleID.grid(row=4, column=1, pady=2)
        self.entrysampleID.insert(END, "1")
        self.entrysampleID.bind("<FocusIn>", on_entry_click)

        # Location Button and Entry
        self.btLocation = Button(self.f1, text="Location", overrelief=SUNKEN, width=10)
        self.btLocation.grid(row=5, column=0, pady=2, sticky=W)
        self.entryLocation = Entry(self.f1, width=16)
        self.entryLocation.grid(row=5, column=1, pady=2)
        #self.entryLocation.insert(END, "55.78210, 12.51834")
        self.entryLocation.insert(END, "Unknown")

        # --------------------------------------------------------------------------------------
        # Frame 2 (Main Task)
        self.f2 = Frame(self.frameinit, relief=GROOVE, bd=4)
        self.f2.grid(row=0, column=2, rowspan=4, columnspan=2, padx=2, pady=2, sticky=W)
        self.lbMainTask = Label(self.f2, text="Main Task").grid(row=0, column=0, columnspan=2, pady=2)

        # select mode
        self.modeVar = StringVar()
        self.modeOp = ['Select Mode', 'COV', 'Sal', 'Cam', 'Custom']
        self.modeVar.set(self.modeOp[0])
        self.modeOpMenu = OptionMenu(self.f2, self.modeVar, *self.modeOp)
        self.modeOpMenu.grid(row=1, column=0, pady=2, sticky=W)

        self.btStart = Button(self.f2, text="Start System", width=10)
        self.btStart.grid(row=1, column=1, pady=2)

        self.btStop = Button(self.f2, text="Stop", width=10)
        self.btStop.grid(row=2, column=1, pady=2)

        self.btRun = Button(self.f2, text="Run", width=10)
        self.btRun.grid(row=2, column=0, pady=2)

        self.lbRemain = Label(self.f2, text="Remain Time", width=12).grid(row=3, column=0, pady=2, sticky=W)
        self.entryRemain = Entry(self.f2, width=10)
        self.entryRemain.grid(row=3, column=1, pady=2)

        # --------------------------------------------------------------------------------------
        # Frame 3 (Settings)
        self.f3 = Frame(self.frameinit, relief=GROOVE, bd=4)
        self.f3.grid(row=0, column=4, rowspan=4, columnspan=2, padx=2, pady=2, sticky=W)

        self.checkVar = IntVar()  # default of selected is 1
        self.btCheckCustom = Checkbutton(self.f3, bd=4, variable=self.checkVar, text="Custom set")
        self.btCheckCustom.grid(row=0, column=0, sticky=W, pady=2)

        self.lbtime = Label(self.f3, text="Interval (min)").grid(row=1, column=0, sticky=W, pady=2)
        self.lampInterval = Entry(self.f3, width=12)
        self.lampInterval.grid(row=1, column=1, pady=2)

        self.lbRate = Label(self.f3, text="Threshold").grid(row=2, column=0, sticky=W, pady=2)
        self.enRate = Entry(self.f3, width=12, state="disabled")
        self.enRate.grid(row=2, column=1, pady=2)

        self.lbDerTime = Label(self.f3, text="Noise Threshold").grid(row=3, column=0, sticky=W, pady=2)
        self.enNoiseThres = Entry(self.f3, width=12, state="disabled")
        self.enNoiseThres.grid(row=3, column=1, pady=2)

        # ---------------------------------------------------------------------------------------
        # Frame 4 (Results)
        self.f4 = Frame(self.frameinit, relief=GROOVE, bd=4)
        self.f4.grid(row=5, column=2, rowspan=4, columnspan=2, padx=2, pady=2, sticky=W)

        lbResults = Label(self.f4, text="Results").grid(row=0, column=0, pady=2)

        self.btLampFigs = Button(self.f4, text="LAMP Graph", width=11)
        self.btLampFigs.grid(row=1, column=0, pady=2, sticky=W)

        self.btTempFig = Button(self.f4, text="Heating Graph", width=11)
        self.btTempFig.grid(row=2, column=0, pady=2, sticky=W)

        self.btDerAbs = Button(self.f4, text="Derivative", width=11)
        self.btDerAbs.grid(row=3, column=0, pady=2, sticky=W)

        self.btAbsFigs = Button(self.f4, text="Intensity", width=11)
        self.btAbsFigs.grid(row=1, column=1, pady=2, sticky=W)

        self.btReport = Button(self.f4, text="Report", width=11)
        self.btReport.grid(row=2, column=1, pady=2, sticky=W)

        self.btSendRS = Button(self.f4, text="Send Result", width=11)
        self.btSendRS.grid(row=3, column=1, pady=2, sticky=W)

        # --------------------------------------------------------------------------------------
        # Frame 5 (I/O)
        self.f5 = Frame(self.frameinit, relief=GROOVE, bd=4)
        self.f5.grid(row=5, column=4, rowspan=4, columnspan=2, padx=2, pady=2, sticky=W)

        self.lbIO = Label(self.f5, text="I/O").grid(row=0, column=0, pady=2)

        self.btFillData = Button(self.f5, text="Fill Samples", width=10)
        self.btFillData.grid(row=1, column=0, pady=2, sticky=W)

        self.btResetData = Button(self.f5, text="Reset", width=10)
        self.btResetData.grid(row=1, column=1, pady=2, sticky=W)

        self.btOpenFile = Button(self.f5, text="Open File", width=10)
        self.btOpenFile.grid(row=2, column=0, pady=2, sticky=W)

        self.btSendfile = Button(self.f5, text="Send File", width=10)
        self.btSendfile.grid(row=2, column=1, pady=2, sticky=W)

        # select mode in openfile
        self.OpenVar = StringVar()
        self.OpenOp = ['Mode', 'COV', 'Sal', 'Cam', 'Custom']
        self.OpenVar.set(self.OpenOp[0])
        self.OpenOpMenu = OptionMenu(self.f5, self.OpenVar, *self.OpenOp)
        self.OpenOpMenu.grid(row=3, column=0, pady=2, sticky=W)
        self.btProcess = Button(self.f5, text="Process", width=10, overrelief=SUNKEN, bd=3)
        self.btProcess.grid(row=3, column=1, pady=2, sticky=W)

        # --------------------------------------------------------------------------------------
        self.f6 = Frame(self.frameinit, relief=GROOVE, bd=4)
        self.f6.grid(row=7, column=0, rowspan=2, columnspan=2, sticky=tk.W, padx=2, pady=2)

        self.lbtoptemp = Label(self.f6, text='Top Heater', width=12)
        self.lbtoptemp.grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)

        self.lbbottomtemp = Label(self.f6, text='Bottom Heater', width=12)
        self.lbbottomtemp.grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)

        self.entrytoptemp = Entry(self.f6, width=14, bd=2)
        self.entrytoptemp.grid(row=0, column=1, padx=5, pady=2)

        self.entrybottomtemp = Entry(self.f6, width=14, bd=2)
        self.entrybottomtemp.grid(row=1, column=1, padx=5, pady=2)

#        # Adding Menu
#        menubar = Menu(self.master)
#        self.master.config(menu=menubar)

#        fileMenu = Menu(menubar, tearoff=0)
#        fileMenu.add_command(label="Open Excel File", command=lambda: self.openFile())
#        fileMenu.add_separator()
#        fileMenu.add_command(label="Help", command=lambda: self.openManual())
#        fileMenu.add_command(label="Quit", command=lambda: self.quit_program())
#        fileMenu.add_separator()
#        fileMenu.add_command(label="About App", command=lambda: self.show_owner())
#        menubar.add_cascade(label="File", menu=fileMenu)

        # Scrollable Text Display
        self.scrollText = Scrollbar(master)
        self.scrollText.pack(side=RIGHT, fill=BOTH)

        self.txtDisplay = Text(master, padx=5, pady=2, yscrollcommand=self.scrollText.set, bd=4, relief=GROOVE)
        self.txtDisplay.pack(side=BOTTOM, fill=BOTH, expand=True)
        self.scrollText.config(command=self.txtDisplay.yview)

        self.change_time_label()
    # --------------------------------------------------------------------------------------
    def frameFinalResults(self):

        self.frameResults = Frame(Toplevel())
        self.frameResults.pack()
        self.scrollTextResults = Scrollbar(self.frameResults)
        self.scrollTextResults.pack(side=RIGHT, fill=BOTH)
        self.txtResults = Text(self.frameResults, padx=3, pady=3, relief=GROOVE,
                               yscrollcommand=self.scrollTextResults.set, bd=5)
        self.scrollTextResults.config(command=self.txtResults.yview)
        self.txtResults.pack(side=BOTTOM, fill=BOTH, expand=1)

    # --------------------------------------------------------------------------------------
    def change_time_label(self):  # to change timestamp on time
        text = self.get_datetime()
        self.lbdatetime.configure(text=text)
        self.frameinit.after(60, self.change_time_label)

    # --------------------------------------------------------------------------------------
    def get_datetime(self):
        current_time = str(datetime.now())
        current_time = current_time[0:16]
        return current_time

    # --------------------------------------------------------------------------------------
    def openFile(self):
        try:
            filetypes = [("Excel Workbook", "*.xls; *.xlsx; *.csv")]
            filename = askopenfilename(initialdir=os.getcwd(), title="Select file", filetypes=filetypes)
            os.popen(filename)
        except:
            mess.showerror("Open file error", "Do not have Microsoft Excel to run...")

    # --------------------------------------------------------------------------------------
    def openManual(self):
        filePath = os.getcwd() + "\\KIT manual.txt"
        os.popen(filePath)

    # --------------------------------------------------------------------------------------
    def quit_program(self):
        GPIO.output(heaterSafe, GPIO.LOW)  # Set heaterSafe OFF
        pwmt.start(0)  # Start Top heater with 0% duty cycle (off)
        pwmb.start(0)  # Start Bottom heater with 0% duty cycle (off)
        os._exit(0)

    # --------------------------------------------------------------------------------------
    def show_owner(self):
        mess.showinfo("POC-LAMP APP ", "Written by Huynh Van Ngoc \n hvngocs@gmail.com")

    # --------------------------------------------------------------------------------------
    def processIncoming(self):
        # Handle all messages currently in the queue, if any
        while self.queue.qsize():
            try:
                msg = self.queue.get(0)
                # Check contents of message and do whatever is needed. As a
                # simple test, print it (in real life, you would
                # suitably update the GUI's display in a richer fashion).
                print(msg)
            except Queue.Empty:
                pass

# --------------------------------------------------------------------------------------
class ThreadedAction:
    """
	Launch the main part of the GUI and the worker thread. periodicCall and
	endApplication could reside in the GUI part, but putting them here
	means that you have all the thread controls in a single place.
	"""
    # for storing raw data
    global data, temperatures, timestamps, data1, data2, data3, data4, data5, data6, data7, data8, data9, data10, data11, data12
    data, temperatures, timestamps, data1, data2, data3, data4, data5, data6, data7, data8, data9, data10, data11, data12 = \
        [], [], [], [], [], [], [], [], [], [], [], [], [], [], []
    global temperaturesT, temperaturesB, timestampspre, temperaturesTstop, temperaturesBstop, timestampsstop
    temperaturesT, temperaturesB, timestampspre, temperaturesTstop, temperaturesBstop, timestampsstop = [], [], [], [], [], []
    global dataS, timestampsS, dataS1, dataS2, dataS3, dataS4, dataS5, dataS6, dataS7, dataS8, dataS9, dataS10, dataS11, dataS12
    dataS, timestampsS, dataS1, dataS2, dataS3, dataS4, dataS5, dataS6, dataS7, dataS8, dataS9, dataS10, dataS11, dataS12 = \
        [], [], [], [], [], [], [], [], [], [], [], [], [], []

    # for storing intensity data
    global timestampsAb, ab, ab1, ab2, ab3, ab4, ab5, ab6, ab7, ab8, ab9, ab10, ab11, ab12
    timestampsAb, ab, ab1, ab2, ab3, ab4, ab5, ab6, ab7, ab8, ab9, ab10, ab11, ab12 = [], [], [], [], [], [], [], [], [], [], [], [], [], []

    # intensity reference values
    global ref, ref1, ref2, ref3, ref4, ref5, ref6, ref7, ref8, ref9, ref10, ref11, ref12
    ref = []

    # derivation
    global timestampsDer, der, der1, der2, der3, der4, der5, der6, der7, der8, der9, der10, der11, der12
    timestampsDer, der, der1, der2, der3, der4, der5, der6, der7, der8, der9, der10, der11, der12 = [], [], [], [], [], [], [], [], [], [], [], [], [], []
    # gruppe
    global timestampsG, gruppe, gruppe1, gruppe2, gruppe3, gruppe4, gruppe5, gruppe6, gruppe7, gruppe8, gruppe9, gruppe10, gruppe11, gruppe12
    timestampsG, gruppe, gruppe1, gruppe2, gruppe3, gruppe4, gruppe5, gruppe6, gruppe7, gruppe8, gruppe9, gruppe10, gruppe11, gruppe12 = \
    	[], [], [], [], [], [], [], [], [], [], [], [], [], []

    global isFileOpen
    isFileOpen = False

    global isModeSelected
    isModeSelected = False

    global well_1, well_2, well_3, well_4, well_5, well_6, well_7, well_8, well_9, well_10, well_11, well_12

    # Assigning light sources LEDs as gpio pinout
    global LED1, LED2, LED3, LED4
        # GPIO 4 connect to LED1
        # GPIO 17 connect to LED2
        # GPIO 27 connect to LED3
        # GPIO 22 connect to LED2

    LED1 = digitalio.DigitalInOut(board.D4)
    LED1.direction = digitalio.Direction.OUTPUT
    LED2 = digitalio.DigitalInOut(board.D17)
    LED2.direction = digitalio.Direction.OUTPUT
    LED3 = digitalio.DigitalInOut(board.D27)
    LED3.direction = digitalio.Direction.OUTPUT
    LED4 = digitalio.DigitalInOut(board.D22)
    LED4.direction = digitalio.Direction.OUTPUT

    # Set up PID control variables double
    global Kp, Ki, Kd, Kp
    Kp = 5
    Ki = 0.03
    Kd = 0.01

    global setPoint_t, lastsetPoint_t, stopheatTemp_t, setPointEnd_t
    global setPoint_b, lastsetPoint_b, stopheatTemp_b, setPointEnd_b
    global tempadd

    # Set up pins for heater control using PWM for PID
    global topHeaterPin, bottomHeaterPin, heaterSafe, FAN, beepPin, pwmt, pwmb
        # GPIO 12 connect to Top heator control (PWM0)
        # GPIO 13 connect to Bottom heator control (PWM1)

    # Set up PWM on a pin
    topHeaterPin = 12  # GPIO pin for PWM
    bottomHeaterPin = 13
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(topHeaterPin, GPIO.OUT)
    GPIO.setup(bottomHeaterPin, GPIO.OUT)

    # Initialize PWM on the pin at a specific frequency
    pwmt = GPIO.PWM(topHeaterPin, 50)  # 50 Hz frequency (can be adjusted)
    pwmt.start(0)  # Start with 0% duty cycle (off)
    pwmb = GPIO.PWM(bottomHeaterPin, 50)  # 50 Hz frequency (can be adjusted)
    pwmb.start(0)  # Start with 0% duty cycle (off)

        # for Fan and heater safe
        # GPIO 23 connect to Heater save relays control
        # GPIO 24 connect to FAN control
        # for sound beep
        # GPIO 25 connect to beepPin control

    heaterSafe = 23
    GPIO.setup(heaterSafe, GPIO.OUT)
    GPIO.output(heaterSafe, GPIO.LOW)  # Set heaterSafe OFF, stop heating
    FAN = 24
    GPIO.setup(FAN, GPIO.OUT)
    GPIO.output(FAN, GPIO.LOW)

    beepPin = 25
    GPIO.setup(beepPin, GPIO.OUT)

    # Preparing digital outputs for heaters control
    tempadd = 1
    setPoint_b = 65.0 + tempadd
    setPoint_t = setPoint_b + 3

    lastsetPoint_b = 85.0 + tempadd
    #lastsetPoint_b = 75.0 + tempadd # For test only
    lastsetPoint_t = lastsetPoint_b + 3

    stopheatTemp_b = 24.0
    stopheatTemp_t = 24.0

    setPointEnd_t = setPoint_t  # test for coolingFan
    setPointEnd_b = setPoint_b

    def __init__(self, master):
        self.master = master
        self.queue = Queue()
        self.gui = GuiPart(master, self.queue)
        self.gui.btRun.config(state=DISABLED)
        self.gui.btStop.config(state=DISABLED)
        self.gui.OpenOpMenu.config(state=DISABLED)
        self.gui.btProcess.config(state=DISABLED)

        # set up the thread to do tasks
        # threads can be created and used if necessary
        self.running = False
        self.sign = ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-']
        self.samplesName = ["", "", "", "", "", "", "", "", "", "", "", ""]
        self.timePositive = ["", "", "", "", "", "", "", "", "", "", "", ""]
        self.expStartAt = 'Unknown'
        self.expStopAt = 'Unknown'
        self.expSampleID = 'Unknown'
        self.expPeriod = 'Unknown'
        self.expPeriodCut = 'Unknown'
        self.expMode = 'Unknown'
        self.periodicCall()

        self.well_1 = 0
        self.well_2 = 0
        self.well_3 = 0
        self.well_4 = 0
        self.well_5 = 0
        self.well_6 = 0
        self.well_7 = 0
        self.well_8 = 0
        self.well_9 = 0
        self.well_10 = 0
        self.well_11 = 0
        self.well_12 = 0

        LED1.value = False
        LED2.value = False
        LED3.value = False
        LED4.value = False

        # binds to buttons
        self.gui.btRun.config(command=self.runDetect)
        self.gui.btStop.config(command=self.stopDetect)
        self.gui.btStart.config(command=self.startsystem)
        self.gui.btProcess.config(command=self.processfile)
        self.gui.btCheckCustom.config(command=self.onBtCheckCustom)
        self.gui.btDerAbs.config(command=self.callFigDer)  # bind to deriavative func
        self.gui.btOpenFile.bind("<1>", self.openFile)
        self.gui.btAbsFigs.config(command=self.callFigAbs)
        self.gui.btLampFigs.bind("<1>", self.callFigLamp)
        self.gui.btTempFig.bind("<1>", self.callFigTemp)
        self.gui.btReport.config(command=self.createFinalReport)
        self.gui.btFillData.config(command=self.fillData)
        self.gui.txtDisplay.config(state=NORMAL)
        self.gui.btLocation.config(command=self.log_gps_datatest)
        self.gui.btSendRS.config(command=self.blockchainsend)

        # --- In active Results frame
        self.gui.btLampFigs.config(state=DISABLED)
        self.gui.btTempFig.config(state=DISABLED)
        self.gui.btDerAbs.config(state=DISABLED)
        self.gui.btAbsFigs.config(state=DISABLED)
        self.gui.btReport.config(state=DISABLED)
        self.gui.btSendRS.config(state=DISABLED)

        self.master.bind("<Control-Key-x>", self.quit)
        self.master.bind("<Control-Key-o>", self.openFile)
        self.master.bind("<Control-Key-h>", self.openManual)

        self.isFileOpen = False
        self.isModeSelected = False
        self.isCalDerivation = False
        self.lastPath = 'Unknown'
        self.isCSV = False

        # Time control for PID
        self.lampInterval = 36000  # 10 hours for max waiting time
        self.lampIntervalset = 4200  # 70 min for real sample
        self.lastPointInterval = 300  # 5 min
        self.setTimeFan = self.lampInterval + self.lastPointInterval + 30  # Cooling Fan ON after 30 second heaters off
        self.rateLimit = 8000
        self.noiseThreshold = 350.0

        self.isStart = False
        self.isFinishLAMP = False
        self.isStopping = False

        # Temperature control for PID
        self.inPut_t = 0
        self.inPut_b = 0
        self.outPut_t = 0
        self.outPut_b = 0
        self.rate = []
        self.maxDer = []

        # Initialize a list to store datalines in csv
        self.datalines = []

    # ------------------End Init -------------

    # ------------------Blockchain function-------------

    async def communicate(self, wallet_name, token_name, pocname, pocphone, poclocation, poctype,
                     pocs1, pocs1result,
                     pocs2, pocs2result,
                     pocs3, pocs3result,
                     pocs4, pocs4result,
                     pocs5, pocs5result,
                     pocs6, pocs6result,
                     pocs7, pocs7result,
                     pocs8, pocs8result,
                     pocs9, pocs9result,
                     pocs10, pocs10result,
                     pocs11, pocs11result,
                     pocs12, pocs12result,
                     ):
        uri = "ws://cardano2vn.duckdns.org:8765"
        async with websockets.connect(uri) as websocket:
            # Tạo metadata dạng JSON
            metadata = {
                "walletName" : str(wallet_name),
                "tokenName" : str(token_name),
                "pocName" : str(pocname),
                "pocPhone" : str(pocphone),
                "pocLocation" :  str(poclocation),
                "pocType" : str(poctype),
                "pocs1": str(pocs1),
                "pocs1result" : str(pocs1result),
                "pocs2": str(pocs2),
                "pocs2result" : str(pocs2result),
                "pocs3": str(pocs3),
                "pocs3result" : str(pocs3result),
                "pocs4": str(pocs4),
                "pocs4result" : str(pocs4result),
                "pocs5": str(pocs5),
                "pocs5result" : str(pocs5result),
                "pocs6": str(pocs6),
                "pocs6result" : str(pocs6result),
                "pocs7": str(pocs7),
                "pocs7result" : str(pocs7result),
                "pocs8": str(pocs8),
                "pocs8result" : str(pocs8result),
                "pocs9": str(pocs9),
                "pocs9result" : str(pocs9result),
                "pocs10": str(pocs10),
                "pocs10result" : str(pocs10result),
                "pocs11": str(pocs11),
                "pocs11result" : str(pocs11result),
                "pocs12": str(pocs12),
                "pocs12result" : str(pocs12result),
            }
            metadata_json = json.dumps(metadata)
            print(f"Sending JSON to server: {metadata}")

            # Gửi JSON đến server
            await websocket.send(metadata_json)

            # Nhận phản hồi từ server
            response = await websocket.recv()
            response_data = json.loads(response)
            print("Received JSON from server:")
            for key, value in response_data.items():
                print(f"{key}: {value}")

            # Nhận phản hồi từ server txhash
            response = await websocket.recv()
            response_data = json.loads(response)
            print("Received JSON from server:")
            for key, value in response_data.items():
                print(f"{key}: {value}")

    def blockchainsend(self):
        wallet_name = "owner1"
        token_name = "POC-LAMP01"
        pocname = self.gui.entryusername.get()
        pocphone = self.gui.entryuserphone.get()
        poclocation = self.gui.entryLocation.get()
        poctype = self.expMode
        pocsampleid = self.gui.entrysampleID.get()
        pocs1, pocs2, pocs3, pocs4, pocs5, pocs6, pocs7, pocs8, pocs9, pocs10, pocs11, pocs12 = "","","","","","","","","","","",""
        pocs1result, pocs2result, pocs3result, pocs4result, pocs5result, pocs6result, pocs7result, pocs8result, pocs9result, pocs10result, pocs11result, pocs12result = "","","","","","","","","","","",""
        pocID = [pocs1, pocs2, pocs3, pocs4, pocs5, pocs6, pocs7, pocs8, pocs9, pocs10, pocs11, pocs12]
        pocRS = [pocs1result, pocs2result, pocs3result, pocs4result, pocs5result, pocs6result, pocs7result, pocs8result, pocs9result, pocs10result, pocs11result, pocs12result]
        for i in range(0, 12):
            if self.rate[i] > self.rateLimit:
                if self.maxDer[i] > self.noiseThreshold:
                    if i < 9:
                        pocID[i] = pocsampleid + '0' + str(i+1)
                        pocRS[i] = 'P'
                    else:
                        pocID[i] = pocsampleid + str(i+1)
                        pocRS[i] = 'P'
                else:
                    if i < 9:
                        pocID[i] = pocsampleid + '0' + str(i+1)
                        pocRS[i] = 'N'
                    else:
                        pocID[i] = pocsampleid + str(i+1)
                        pocRS[i] = 'N'
            else:
                if i < 9:
                    pocID[i] = pocsampleid + '0' + str(i+1)
                    pocRS[i] = 'N'
                else:
                    pocID[i] = pocsampleid + str(i+1)
                    pocRS[i] = 'N'

        pocs1, pocs2, pocs3, pocs4, pocs5, pocs6, pocs7, pocs8, pocs9, pocs10, pocs11, pocs12 = \
            pocID[0],pocID[1],pocID[2],pocID[3],pocID[4],pocID[5],pocID[6],pocID[7],pocID[8],pocID[9],pocID[10],pocID[11]
        pocs1result, pocs2result, pocs3result, pocs4result, pocs5result, pocs6result, pocs7result, pocs8result, pocs9result, pocs10result, pocs11result, pocs12result = \
            pocRS[0], pocRS[1],pocRS[2],pocRS[3],pocRS[4],pocRS[5],pocRS[6],pocRS[7],pocRS[8],pocRS[9],pocRS[10],pocRS[11]

        asyncio.run(self.communicate(wallet_name, token_name, pocname, pocphone, poclocation, poctype,
                     pocs1, pocs1result,
                     pocs2, pocs2result,
                     pocs3, pocs3result,
                     pocs4, pocs4result,
                     pocs5, pocs5result,
                     pocs6, pocs6result,
                     pocs7, pocs7result,
                     pocs8, pocs8result,
                     pocs9, pocs9result,
                     pocs10, pocs10result,
                     pocs11, pocs11result,
                     pocs12, pocs12result,
                     ))
        plt.pause(0.1)
        self.gui.txtDisplay.delete('1.0', END)
        self.gui.txtDisplay.insert(END, "Result have been sent to Blockchain")
        
# ------------------------------------------------------------------------------------
    def periodicCall(self):
        # Check every 100ms if there is something new in the queue
        self.gui.processIncoming()
        if not self.running:
            # This is the brutal stop of the system. You may want to do
            # some cleanup before actually shutting it down.
            pass
        self.master.after(100, self.periodicCall)

    # ------------------------------------------------------------------------------------
    # FILL DATA fORM
    # ------------------------------------------------------------------------------------

    def fillData(self):
        # self.gui.createFillForm()
        # print(self.samplesName)
        # self.gui.fTopup.update()
        # self.gui.fTopup.deiconify()
        # del self.samplesName[:]
        self.fTopup = Toplevel()
        self.fTopup.title('Samples Name...')
        self.fTopup.tk.call('wm', 'iconphoto', self.fTopup._w, POC_LAMPIcon)

        label1A = Label(self.fTopup, text="1A", bd=4, width=5).grid(row=0, column=0)
        label1B = Label(self.fTopup, text="1B", bd=4, width=5).grid(row=1, column=0)
        label2A = Label(self.fTopup, text="2A", bd=4, width=5).grid(row=2, column=0)
        label2B = Label(self.fTopup, text="2B", bd=4, width=5).grid(row=3, column=0)
        label3A = Label(self.fTopup, text="3A", bd=4, width=5).grid(row=4, column=0)
        label4A = Label(self.fTopup, text="4A", bd=4, width=5).grid(row=5, column=0)
        label1C = Label(self.fTopup, text="1C", bd=4, width=5).grid(row=6, column=0)
        label1D = Label(self.fTopup, text="1D", bd=4, width=5).grid(row=7, column=0)
        label2C = Label(self.fTopup, text="2C", bd=4, width=5).grid(row=8, column=0)
        label2D = Label(self.fTopup, text="2D", bd=4, width=5).grid(row=9, column=0)
        label3D = Label(self.fTopup, text="3D", bd=4, width=5).grid(row=10, column=0)
        label4D = Label(self.fTopup, text="4D", bd=4, width=5).grid(row=11, column=0)

        self.en1A = Entry(self.fTopup, width=80)
        self.en1B = Entry(self.fTopup, width=80)
        self.en2A = Entry(self.fTopup, width=80)
        self.en2B = Entry(self.fTopup, width=80)
        self.en3A = Entry(self.fTopup, width=80)
        self.en4A = Entry(self.fTopup, width=80)
        self.en1C = Entry(self.fTopup, width=80)
        self.en1D = Entry(self.fTopup, width=80)
        self.en2C = Entry(self.fTopup, width=80)
        self.en2D = Entry(self.fTopup, width=80)
        self.en3D = Entry(self.fTopup, width=80)
        self.en4D = Entry(self.fTopup, width=80)

        self.en1A.grid(row=0, column=1)
        self.en1B.grid(row=1, column=1)
        self.en2A.grid(row=2, column=1)
        self.en2B.grid(row=3, column=1)
        self.en3A.grid(row=4, column=1)
        self.en4A.grid(row=5, column=1)
        self.en1C.grid(row=6, column=1)
        self.en1D.grid(row=7, column=1)
        self.en2C.grid(row=8, column=1)
        self.en2D.grid(row=9, column=1)
        self.en3D.grid(row=10, column=1)
        self.en4D.grid(row=11, column=1)

        self.en1A.insert(END, self.samplesName[0])
        self.en1B.insert(END, self.samplesName[1])
        self.en2A.insert(END, self.samplesName[2])
        self.en2B.insert(END, self.samplesName[3])
        self.en3A.insert(END, self.samplesName[4])
        self.en4A.insert(END, self.samplesName[5])
        self.en1C.insert(END, self.samplesName[6])
        self.en1D.insert(END, self.samplesName[7])
        self.en2C.insert(END, self.samplesName[8])
        self.en2D.insert(END, self.samplesName[9])
        self.en3D.insert(END, self.samplesName[10])
        self.en4D.insert(END, self.samplesName[11])

        # Chip template
        self.fTemplate = Frame(self.fTopup, relief=GROOVE, bd=4)
        self.fTemplate.grid(row=0, column=3, rowspan=6, columnspan=4)
        lbChip = Label(self.fTemplate, text='Chip Template').grid(row=0, column=1)
        lb1a = Label(self.fTemplate, text='1A', width=6).grid(row=2, column=0)
        lb1b = Label(self.fTemplate, text='1B', width=6).grid(row=2, column=1)
        lb1c = Label(self.fTemplate, text='1C', width=6).grid(row=2, column=2)
        lb1d = Label(self.fTemplate, text='1D', width=6).grid(row=2, column=3)
        lb2a = Label(self.fTemplate, text='2A', width=6).grid(row=3, column=0)
        lb2b = Label(self.fTemplate, text='2B', width=6).grid(row=3, column=1)
        lb2c = Label(self.fTemplate, text='2C', width=6).grid(row=3, column=2)
        lb2d = Label(self.fTemplate, text='2D', width=6).grid(row=3, column=3)
        lb3a = Label(self.fTemplate, text='3A', width=6).grid(row=4, column=0)
        lb3d = Label(self.fTemplate, text='3D', width=6).grid(row=4, column=3)
        lb4a = Label(self.fTemplate, text='4A', width=6).grid(row=5, column=0)
        lb4d = Label(self.fTemplate, text='4D', width=6).grid(row=5, column=3)

        self.btFillDone = Button(self.fTopup, text="Done", overrelief=SUNKEN, bd=3, width=6)
        self.btFillDone.grid(row=7, column=4)
        self.btFillReset = Button(self.fTopup, text="Reset all", overrelief=SUNKEN, bd=3, width=6)
        self.btFillReset.grid(row=7, column=5)
        self.btFillDone.config(command=self.onBtFillDone)
        self.btFillReset.config(command=self.onBtFillReset)
        del self.samplesName[:]
        self.tupEn = [self.en1A, self.en1B, self.en2A, self.en2B, self.en3A, self.en4A, self.en1C, \
                      self.en1D, self.en2C, self.en2D, self.en3D, self.en4D]

    def onBtFillDone(self):
        for en in self.tupEn:
            self.samplesName.append(en.get())
        self.fTopup.destroy()

    def onBtFillReset(self):
        for en in self.tupEn:
            en.delete(0, END)

    def onBtCheckCustom(self):
        if self.gui.checkVar.get():
            # if self.gui.checkVar.get()==1:
            self.gui.enRate.config(state=NORMAL)
            self.gui.enNoiseThres.config(state=NORMAL)
            self.gui.enRate.delete(0, END)
            self.gui.enNoiseThres.delete(0, END)
            self.gui.lampInterval.delete(0, END)
            self.gui.lampInterval.insert(0, '50')
            self.gui.enRate.insert(END, "8000")
            self.gui.enNoiseThres.insert(END, "350")
        else:
            self.gui.enRate.config(state=DISABLED)
            self.gui.enNoiseThres.config(state=DISABLED)

    def quit(self, event):
        os._exit(0)

    def openFile(self, event):
        if self.lastPath == 'Unknown':
            self.lastPath = os.getcwd()
        filetypes = [("Excel Workbook", "*.xls; *.xlsx; *.csv")]
        self.pickedFilename = askopenfilename(initialdir=self.lastPath, title="Select file", filetypes=filetypes)
        self.lastPath, self.tail = os.path.split(self.pickedFilename)
        self.isFileOpen = True
        self.ModeSelected()

    # --------------------------------------------------------------------------------------
    def openManual(self, event):
        filePath = os.getcwd() + "\\KIT manual.txt"
        os.popen(filePath)

    # -------GPS function--------------------------------------------------------------------
    def log_gps_datatest(self):
        self.gui.entryLocation.delete(0, END)
        self.gui.entryLocation.insert(END, "55.78210, 12.51834")
    # -------GPS function--------------------------------------------------------------------
    def log_gps_data(self):
        self.port='/dev/ttyACM0'
        self.baudrate=9600
        self.output_file='GPSdata.txt'
        try:
            gps = serial.Serial(self.port, self.baudrate, timeout=1)
            print("Connected to GPS.")

            # Open the output file for appending data
            with open(self.output_file, 'w') as file:
                file.write("Latitude,Longitude,Timestamp,Date\n")  # Header for the file

                for i in range(20):
                    line = gps.readline().decode('ascii', errors='replace')
                    if line.startswith('$G'):
                        try:
                            msg = pynmea2.parse(line)

                            # Check for sentences that contain location data
                            if isinstance(msg, (pynmea2.types.talker.GGA, pynmea2.types.talker.RMC, pynmea2.types.talker.GLL)):
                                # Retrieve and format the data
                                #latitude = msg.latitude
                                #longitude = msg.longitude
                                latitude = round(float(msg.latitude), 5)
                                longitude = round(float(msg.longitude), 5)
                                timestamp = msg.timestamp
                                date = datetime.utcnow().date()  # Get the current UTC date

                                # Write to file
                                file.write(f"{latitude},{longitude},{timestamp},{date}\n")
                                file.flush()
                                self.gui.entryLocation.delete(0, END)
                                self.gui.entryLocation.insert(0, latitude + longitude)
                                if int(latitude) == 0 and int(longitude) == 0:
                                    print("Unknow location")
                                else:
                                    print(f"Logged: Latitude: {latitude}, Longitude: {longitude}, Timestamp: {timestamp}, Date: {date}")
                            else:
                                self.gui.entryLocation.delete(0, END)
                                self.gui.entryLocation.insert(0, 'Unknow')
                                print(f"Received NMEA sentence without location data: {line.strip()}")
                        except pynmea2.ParseError:
                            print(f"Failed to parse line: {line.strip()}")
                    i += 1
                    time.sleep(0.5)
        except serial.SerialException as e:
            print(f"Could not connect to GPS: {e}")
        finally:
            if gps and gps.is_open:
                gps.close()
                print("GPS connection closed.")

   # ---Start system prepaere for running test-----------------------------------------------------------------------------------
    def startsystem(self):
        self.lamppid_t = LampPID(setPoint_t, lastsetPoint_t, stopheatTemp_t, self.inPut_t, self.outPut_t)
        self.lamppid_b = LampPID(setPoint_b, lastsetPoint_b, stopheatTemp_b, self.inPut_b, self.outPut_b)
        self.resetData()
        self.running = True
        self.isFinishLAMP = False
        self.isStart = False  # Not Start running detection
        self.startTime = time.time()

        self.gui.btStart.config(state=DISABLED)
        # --- In active Results frame
        self.gui.btLampFigs.config(state=DISABLED)
        self.gui.btTempFig.config(state=DISABLED)
        self.gui.btDerAbs.config(state=DISABLED)
        self.gui.btAbsFigs.config(state=DISABLED)
        self.gui.btReport.config(state=DISABLED)
        self.gui.btSendRS.config(state=DISABLED)

        optionMode = self.gui.modeVar.get()
        if optionMode != 'Select Mode':
            self.gui.lampInterval.delete(0, END)
            self.expMode = optionMode
            if optionMode == 'COV':
                self.gui.lampInterval.insert(0, '50')
                self.lampIntervalset = 3000  # 50 min for real sample
                # self.rateLimit = 10000         # update on 20220228
                # self.noiseThreshold = 800.0
                self.expPeriod = 50
            elif optionMode == 'Sal':
                self.gui.lampInterval.insert(0, '50')
                self.lampIntervalset = 3000  # 50 min for real sample
                # self.rateLimit = 10000
                # self.noiseThreshold = 800.0
                self.expPeriod = 50
            elif optionMode == 'Cam':
                self.gui.lampInterval.insert(0, '60')
                self.lampIntervalset = 3600  # 60 min for real sample
                # self.rateLimit = 10000
                # self.noiseThreshold = 800.0
                self.expPeriod = 60
            else:
                optionMode = 'Custom'
                mess.showinfo("Set LAMP interval", "Set the custom LAMP interval")
                self.gui.lampInterval.insert(0, '50')
                # self.rateLimit = 10000
                # self.noiseThreshold = 800.0
                self.expPeriod = 50
                self.gui.txtDisplay.insert(END,
                                           "\n\n Running on Custom mode. Make sure that you put LAMP interval already..." +
                                           "\n or default by 50 minutes." +
                                           "\n\n Wait for running...")
                self.gui.lampInterval.focus()

            self.gui.modeOpMenu.config(state=DISABLED)

            # Prepare system ready for experiment
            self.inPut_t, self.inPut_b = self.readtemp()

            # Check over-heat
            if ((self.inPut_b > (setPoint_b + 3)) or (self.inPut_t > (setPoint_t + 3))):
                self.coolingControl()

            self.startTimepre = time.time()  # time that starts prepare system
            self.gui.btStop.config(state=ACTIVE)
            GPIO.output(heaterSafe, GPIO.HIGH)  # Set heaterSafe ON
            GPIO.output(FAN, GPIO.LOW)

            while (self.inPut_b < (setPoint_b - 2)) and (self.running == True):
                self.gui.txtDisplay.delete('1.0', END)
                self.gui.txtDisplay.insert(END, "Running on " + optionMode + " mode. \n" +
                                           "LAMP interval will be " + self.gui.lampInterval.get() + " minutes. \n" +
                                           "Wait for system ready for running test ... \n")
                self.gui.txtDisplay.insert(END, "Heating up...     " + "\n")
                self.inPut_t, self.inPut_b = self.readtemp()
                self.gui.entrytoptemp.delete(0, END)
                self.gui.entrybottomtemp.delete(0, END)
                self.gui.entrytoptemp.insert(END, str(self.inPut_t) + "  DegC")
                self.gui.entrybottomtemp.insert(END, str(self.inPut_b) + "  DegC")
                self.make_fig_topbottom_temperature()
                self.heaterControl()
                time.sleep(0.5)

            self.timeBeginReached = time.time()  # Start counting lamp_interval time
            self.gui.btRun.config(state=ACTIVE)

            # Keep heating for max 10 hours until Run button is pressed
            while (self.inPut_b >= (setPoint_b - 2.5)) and (self.isStart == False) and (self.running == True):
                self.make_fig_topbottom_temperature()
                self.inPut_t, self.inPut_b = self.readtemp()
                self.gui.entrytoptemp.delete(0, END)
                self.gui.entrybottomtemp.delete(0, END)
                self.gui.entrytoptemp.insert(END, str(self.inPut_t) + "  DegC")
                self.gui.entrybottomtemp.insert(END, str(self.inPut_b) + "  DegC")
                self.gui.txtDisplay.delete('1.0', END)
                self.gui.txtDisplay.insert(END, "System ready" + "\n")
                self.gui.txtDisplay.insert(END, "Put the chip in" + "\n")
                self.gui.txtDisplay.insert(END, "Press \'Run\' button to to start" + "\n")
                self.heaterControl()
                time.sleep(0.5)

        else:
            self.gui.btStart.config(state=ACTIVE)
            mess.showinfo("Invalid mode", "Please select a valid running mode...")

# --------------------------------------------------------------------------------------
    def readtemp(self):
        tempflag = True
        while tempflag == True:
            try:
                # Attempt to read the temperature
                temperatureT = sensor1.temperature
                time.sleep(0.1)  # Delay 100 ms between readings
                temperatureB = sensor2.temperature
            except RuntimeError as e:
                # Handle the "short circuit to ground" error
                pwmt.start(0)  # Start Top heater with 0% duty cycle (off)
                pwmb.start(0)  # Start Bottom heater with 0% duty cycle (off)
                time.sleep(1)  # Wait before retrying

            except Exception as e:
                # Handle unexpected errors
                print(f"Unexpected error: {e}")
                pwmt.start(0)  # Start Top heater with 0% duty cycle (off)
                pwmb.start(0)  # Start Bottom heater with 0% duty cycle (off)
                break  # Stop program if it's a critical error
            else:
                tempflag = False

        return temperatureT, temperatureB

# --------------------------------------------------------------------------------------
    def heaterControl(self):
        # Read temperatures from thermocouples
        self.temp_t, self.temp_b = self.readtemp()

        # check error or NAN from the thermocouplers max31855
        while ((self.temp_t <= 10.0) or math.isnan(self.temp_t)):
            time.sleep(0.1)  # 100 ms
            self.temp_t = self.readtemp()[0]

        while ((self.temp_b <= 10.0) or math.isnan(self.temp_b)):
            time.sleep(0.1)  # 100 ms
            self.temp_b = self.readtemp()[1]

        # Update inputs for PID controllers
        self.lamppid_t.our_input = self.temp_t
        self.lamppid_b.our_input = self.temp_b

        # Temperature calibration and PID configuration
        self.lamppid_t.temp_cal()
        self.lamppid_b.temp_cal()

        self.lamppid_t.set_pid_gain(Kp, Ki, Kd)
        self.lamppid_b.set_pid_gain(Kp, Ki, Kd)

        # Execute PID computation
        self.lamppid_t.pid()
        self.lamppid_b.pid()
        # Simulate PWM output for the heaters
        # Equivalent to analogWrite(pin, value), where value is from 0 to 255
        duty_cyclet = (self.lamppid_t.our_output / 255.0) * 100  # Convert 0-255 to 0-100% duty cycle
        pwmt.ChangeDutyCycle(duty_cyclet)  # top heater control using PWM
        duty_cycleb = (self.lamppid_b.our_output / 255.0) * 100  # Convert 0-255 to 0-100% duty cycle
        pwmb.ChangeDutyCycle(duty_cycleb)  # bottom heater control using PWM

        # Timing calculations
        self.lamppid_t.time_cal(self.lampInterval, self.lastPointInterval)
        self.lamppid_b.time_cal(self.lampInterval, self.lastPointInterval)

    # --------------------------------------------------------------------------------------
    def coolingControl(self):
        GPIO.output(heaterSafe, GPIO.LOW)  # Set heaterSafe OFF
        pwmt.start(0)  # Start Top heater with 0% duty cycle (off)
        pwmb.start(0)  # Start Bottom heater with 0% duty cycle (off)
        self.inPut_t, self.inPut_b = self.readtemp()
        while (self.inPut_b > 60 or self.inPut_t > 60):
            plt.pause(0.1)
            GPIO.output(FAN, GPIO.HIGH)
            self.gui.txtDisplay.delete('1.0', END)
            self.gui.txtDisplay.insert(END, "Cooling down..." + "\n")
            self.gui.entrytoptemp.delete(0, END)
            self.gui.entrybottomtemp.delete(0, END)
            self.gui.entrytoptemp.insert(END, str(self.inPut_t) + "  DegC")
            self.gui.entrybottomtemp.insert(END, str(self.inPut_b) + "  DegC")
            time.sleep(1)
            self.inPut_t, self.inPut_b = self.readtemp()
        GPIO.output(FAN, GPIO.LOW)

    # ---------- Run LAMP --------------------------------------
    def timeCheck(self, curTime):
        self.cur = curTime
        self.timeDiff = round(float(time.time()) * 1000, 2) - self.cur
        return self.timeDiff

    def runKit(self):
        self.runKitTime = round(float(time.time()) * 1000, 2)
        # time count in milisecond
        # Basic procedure for aquiring measurements: 1) Turn on LED and wait a bit (250 ms). 2) Assign analog input to corresponding well number. 3) Turn off LED.
        while (self.timeCheck(self.runKitTime) <= 250):
            LED1.value = True
            while (self.timeCheck(self.runKitTime) <= 250):
                time.sleep(0.05)

        while (self.timeCheck(self.runKitTime) > 250 and self.timeCheck(self.runKitTime) <= 500):
            self.well_6 = adc1.read_adc(0, gain=GAIN)
            self.well_5 = adc1.read_adc(1, gain=GAIN)
            LED1.value = False
            LED2.value = True
            while (self.timeCheck(self.runKitTime) > 250 and self.timeCheck(self.runKitTime) <= 500):
                time.sleep(0.05)

        while (self.timeCheck(self.runKitTime) > 500 and self.timeCheck(self.runKitTime) <= 750):
            self.well_3 = adc1.read_adc(2, gain=GAIN)
            self.well_1 = adc1.read_adc(3, gain=GAIN)
            self.well_2 = adc2.read_adc(0, gain=GAIN)
            self.well_4 = adc3.read_adc(3, gain=GAIN)
            LED2.value = False
            LED3.value = True
            while (self.timeCheck(self.runKitTime) > 500 and self.timeCheck(self.runKitTime) <= 750):
                time.sleep(0.05)

        while (self.timeCheck(self.runKitTime) > 750 and self.timeCheck(self.runKitTime) <= 1000):
            self.well_7 = adc2.read_adc(1, gain=GAIN)
            self.well_8 = adc2.read_adc(2, gain=GAIN)
            self.well_10 = adc2.read_adc(3, gain=GAIN)
            self.well_9 = adc3.read_adc(2, gain=GAIN)
            LED3.value = False
            LED4.value = True
            while (self.timeCheck(self.runKitTime) > 750 and self.timeCheck(self.runKitTime) <= 1000):
                time.sleep(0.05)

        self.well_11 = adc3.read_adc(0, gain=GAIN)
        self.well_12 = adc3.read_adc(1, gain=GAIN)
        LED4.value = False

        # Sending the relevant data to the serial, including time stamps:-
        self.runKitTime = time.time()
        self.timer = round(self.runKitTime - self.timeChipIn, 2)
        self.dataline = str(self.timer) + " | " + str(self.inPut_b) + " | " + str(self.well_1) + " | " + str(
            self.well_2) + " |  " + str(self.well_3) + " | " + str(self.well_4) + " | " + str(
            self.well_5) + " | " + str(self.well_6) + " | " + str(self.well_7) + " | " + str(self.well_8) + " | " + str(
            self.well_9) + " | " + str(self.well_10) + " | " + str(self.well_11) + " | " + str(self.well_12)
        self.add_dataline()  # save dataline to csv file
    # -------------------------------remaining time------------------------------------------
    def remainTime(self, interval):
        self.interval = interval
        self.curTime = time.time()
        if (interval + self.timeBeginReached) >= self.curTime:
            delta = interval + self.timeBeginReached - self.curTime
            self.timeLeftMin = delta // 60
            self.timePassed = interval // 60 - self.timeLeftMin
            self.timeLeftSec = delta % 60
        return self.timeLeftMin, self.timeLeftSec, self.timePassed

    # --------------------------------------------------------------------------------------
    def LAMPcontrol(self):

        # Temperature saving
        self.inPut_t, self.inPut_b = self.readtemp()
        if ((self.inPut_b > 100) or (self.inPut_t > 100)):
            plt.pause(0.1)
            self.gui.txtDisplay.delete('1.0', END)
            self.gui.txtDisplay.insert(END, "Over heat!" + "\n")
            self.gui.txtDisplay.insert(END, "Cooled down..." + "\n")
            GPIO.output(heaterSafe, GPIO.LOW)  # Set heaterSafe OFF
            GPIO.output(FAN, GPIO.HIGH)
            time.sleep(300)  # delay 5 min
            self.coolingControl()
            self.gui.txtDisplay.insert(END, "Cooling down..." + "\n")

        # Run Control heater
        if self.isStart:
            self.heaterControl()
            if not self.isFinishLAMP:
                self.curTimerun = time.time()
                if (self.lampInterval + self.timeBeginReached >= self.curTimerun):
                    self.remainTime(self.lampInterval)
                    self.gui.entryRemain.delete(0, END)
                    self.gui.entrytoptemp.delete(0, END)
                    self.gui.entrybottomtemp.delete(0, END)
                    self.gui.entryRemain.insert(END, str(int(self.timeLeftMin)) + ":" + str(int(self.timeLeftSec)))
                    self.gui.entrytoptemp.insert(END, str(self.inPut_t) + "  DegC")
                    self.gui.entrybottomtemp.insert(END, str(self.inPut_b) + "  DegC")
                else:
                    self.isFinishLAMP = True
            else:
                self.heaterControl()
                self.gui.txtDisplay.insert(END, "Stopping..." + "\n")
                self.remainTime(self.setTimeFan)
                self.gui.entryRemain.delete(0, END)
                self.gui.entrytoptemp.delete(0, END)
                self.gui.entrybottomtemp.delete(0, END)
                self.gui.entryRemain.insert(END, str(int(self.timeLeftMin)) + ":" + str(int(self.timeLeftSec)))
                self.gui.entrytoptemp.insert(END, str(self.inPut_t) + "  DegC")
                self.gui.entrybottomtemp.insert(END, str(self.inPut_b) + "  DegC")
                time.sleep(0.8)

    # --------------------------------------------------------------------------------------
    def runDetect(self):  # Start running LAMP detection
        self.isStart = True  # Start running detection
        self.running = True
        self.isStopping = False
        self.gui.btStart.config(state=DISABLED)
        self.gui.btRun.config(state=DISABLED)
        self.gui.btStop.config(state=ACTIVE)
        self.isFileOpen = False
        self.isCalDerivation = False
        self.expStartAt = self.gui.get_datetime()

        # Set LAMP and Fan time
        self.timeChipIn = time.time()  # The moment putting chip in
        self.lampInterval = self.lampIntervalset
        #self.lampInterval = 600  # For test only
        self.lampInterval += self.timeChipIn - self.timeBeginReached
        self.setTimeFan = self.lampInterval + self.lastPointInterval + 30  # Cooling Fan ON after 30 second heaters off
        self.startDetect = time.time()

        while self.running:
            plt.clf()
            self.expPeriod = 50
            if self.gui.lampInterval:
                self.expPeriod = int(self.gui.lampInterval.get())
                #self.expPeriod = 10  # For test only
            timing = self.expPeriod * 60 - 2
            self.resetData()
            self.initTxt()

            # flags using for receiving data from kit
            isReceived = False  # true if read data for the first time
            isIntensity = False

            while self.isStart:  # while loop that loops forever
                buffer_string = ''
                if self.running:
                    if isReceived == False:
                        isReceived = True
                        self.startTime = time.time()  # time that starts recording data
                        isCorrectStartPoint = False
                    else:
                        self.inPut_t, self.inPut_b = self.readtemp()
                        self.runTime = time.time()  # realtime of loop. Stop recording data after 50 minutes
                        self.runKit()
                        self.LAMPcontrol()
                        buffer_string = self.dataline
                        self.gui.txtDisplay.insert(END, buffer_string + "\n")

                        lines = buffer_string.rstrip()
                        lines = lines.split('|')
                        deltaTime = self.runTime - self.startTime

                        if deltaTime < timing:
                            if len(lines) == 14:
                                timestamps.append(round(float(lines[0]) / 60.0, 2))
                                temperatures.append(lines[1])  # temperature
                                data1.append(float(lines[2]))  # well
                                data2.append(float(lines[3]))
                                data3.append(float(lines[4]))
                                data4.append(float(lines[5]))
                                data5.append(float(lines[6]))
                                data6.append(float(lines[7]))
                                data7.append(float(lines[8]))
                                data8.append(float(lines[9]))
                                data9.append(float(lines[10]))
                                data10.append(float(lines[11]))
                                data11.append(float(lines[12]))
                                data12.append(float(lines[13]))
                                line = []
                                line.extend(
                                    (timestamps[-1], temperatures[-1], data1[-1], data2[-1], data3[-1], data4[-1], \
                                     data5[-1], data6[-1], data7[-1], \
                                     data8[-1], data9[-1], data10[-1], data11[-1], data12[-1]))
                                data.append(line)
                                if (float(lines[0]) > 5.0) and (not isCorrectStartPoint):
                                    timing = timing - float(lines[0])
                                    isCorrectStartPoint = True
                                if not isIntensity:
                                    drawnow(self.make_fig)
                                    plt.pause(.000001)
                                    if deltaTime >= 300:  # after 5 mins
                                        isIntensity = True

                                        ref1 = np.mean(data1[-11:-1])
                                        ref2 = np.mean(data2[-11:-1])
                                        ref3 = np.mean(data3[-11:-1])
                                        ref4 = np.mean(data4[-11:-1])
                                        ref5 = np.mean(data5[-11:-1])
                                        ref6 = np.mean(data6[-11:-1])
                                        ref7 = np.mean(data7[-11:-1])
                                        ref8 = np.mean(data8[-11:-1])
                                        ref9 = np.mean(data9[-11:-1])
                                        ref10 = np.mean(data10[-11:-1])
                                        ref11 = np.mean(data11[-11:-1])
                                        ref12 = np.mean(data12[-11:-1])

                                if isIntensity == True:
                                    timestampsAb.append(float(timestamps[-1]))
                                    ab1.append(data1[-1] - ref1)
                                    ab2.append(data2[-1] - ref2)
                                    ab3.append(data3[-1] - ref3)
                                    ab4.append(data4[-1] - ref4)
                                    ab5.append(data5[-1] - ref5)
                                    ab6.append(data6[-1] - ref6)
                                    ab7.append(data7[-1] - ref7)
                                    ab8.append(data8[-1] - ref8)
                                    ab9.append(data9[-1] - ref9)
                                    ab10.append(data10[-1] - ref10)
                                    ab11.append(data11[-1] - ref11)
                                    ab12.append(data12[-1] - ref12)
                                    drawnow(self.make_fig_intensity)
                                    plt.pause(.000001)
                        else:
                            if self.isStopping == False:
                                self.isStopping = True
                                self.startTimestop = time.time()  # time that starts stop system for final heat
                            self.make_fig_topbottom_temperaturestop()
                            # Checking time to start cooling Fan and finish detecting
                            self.curTimeFan = time.time() - self.timeBeginReached
                            if ((self.curTimeFan > self.setTimeFan) and (self.inPut_b > setPointEnd_b)):
                                self.coolingControl()
                                self.stopDetect()
                                self.isStart = False  # End test

    # --------------------------------------------------------------------------------------
    def stopDetect(self):
        GPIO.output(heaterSafe, GPIO.LOW)  # Set heaterSafe OFF
        pwmt.start(0)  # Start with 0% duty cycle (off)
        pwmb.start(0)  # Start with 0% duty cycle (off)
        # GPIO.output(FAN, GPIO.LOW)
        self.gui.btStop.config(state=DISABLED)
        self.gui.btRun.config(state=DISABLED)
        self.gui.btStart.config(state=ACTIVE)

        # --- Active Results frame
        self.gui.btLampFigs.config(state=ACTIVE)
        self.gui.btTempFig.config(state=ACTIVE)
        self.gui.btDerAbs.config(state=ACTIVE)
        self.gui.btAbsFigs.config(state=ACTIVE)
        self.gui.btReport.config(state=ACTIVE)
        self.gui.btSendRS.config(state=ACTIVE)

        self.gui.modeOpMenu.config(state=NORMAL)
        self.expStopAt = self.gui.get_datetime()
        self.expPeriod = self.expPeriod
        self.expSampleID = self.gui.entrysampleID.get()
        self.gui.txtDisplay.delete('1.0', END)
        self.gui.txtDisplay.insert(END, " \n Disconnect...")
        if time.time() - self.startTime < int(self.expPeriod) * 60 - 3:
            self.gui.txtDisplay.insert(END, "\n Process was terminated before expected time... ")

        self.running = False
        try:
            self.derivativeRaw()
            self.findRates()
            self.findPeakWidth()
            self.createFinalReport()
            self.write_to_file()
            self.save_to_csv()
        except:
            self.write_to_file()
            self.save_to_csv()

# --------------------------------------------------------------------------------------
    def createFinalReport(self):
        self.gui.frameFinalResults()
        self.gui.txtResults.insert(END,
                                   'System ID:' + 4 * ' ' + self.gui.entrysystemID.get() + '\n' 
                                   'User name:' + 4 * ' ' + self.gui.entryusername.get() + '\n' 
                                   'User phone:' + 4 * ' ' + self.gui.entryuserphone.get() + '\n' 
                                   'Sample ID:' + 4 * ' ' + self.gui.entrysampleID.get() + '\n' 
                                   'Location:' + 4 * ' ' + self.gui.entryLocation.get() + '\n')

        self.gui.txtResults.insert(END, 'System starts at: ' + self.expStartAt + '\n')
        self.gui.txtResults.insert(END, 'System stops at: ' + self.expStopAt + '\n')
        
        try:
            self.gui.txtResults.insert(END, 'Date and Time of test: ' + self.tail + '\n\n')  # To get csv file date and time
        except:
            self.gui.txtResults.insert(END, 'Date and Time of test: ' + self.gui.get_datetime() + '\n')  # To get current date and time
            
        self.gui.txtResults.insert(END, 'Test type: ' + self.expMode + '\n')
        self.gui.txtResults.insert(END, 'Interval: ' + str(self.expPeriod) + ' minutes\n')
        
        try:
            self.gui.txtResults.insert(END, 'From data file: ' + self.tail + '\n\n')
        except:
            self.gui.txtResults.insert(END, 'Direct from device... \n\n')
        
        gap1 = 3 * ' '
        gap2 = 6 * ' '

        self.gui.txtResults.insert(END, gap1 + '1A ' + self.sign[0] + gap2 + '1B ' + self.sign[1] + gap2 + \
                                   '1C ' + self.sign[6] + gap2 + '1D ' + self.sign[7] + '\n')

        self.gui.txtResults.insert(END, gap1 + '2A ' + self.sign[2] + gap2 + '2B ' + self.sign[3] + gap2 + \
                                   '2C ' + self.sign[8] + gap2 + '2D ' + self.sign[9] + '\n')

        self.gui.txtResults.insert(END, gap1 + '3A ' + self.sign[4] + gap2 * 4 + '  3D ' + self.sign[10] + '\n')
        self.gui.txtResults.insert(END, gap1 + '4A ' + self.sign[5] + gap2 * 4 + '  4D ' + self.sign[11] + '\n\n')

        well_name = ['1A', '1B', '2A', '2B', '3A', '4A', '1C', '1D', '2C', '2D', '3D', '4D']
        for i in range(len(self.sign)):
            if self.sign[i] == '+':
                self.gui.txtResults.insert(END, 'Sample ' + well_name[i] + ' is positive, at ' + str(
                    self.timePositive[i]) + ' minutes.' + '\n')
            else:
                self.gui.txtResults.insert(END, 'Sample ' + well_name[i] + ' is negative' + '\n')

            # --------------------------------------------------------------------------------------

    def initTxt(self):
        self.gui.txtDisplay.delete('1.0', END)
        self.gui.txtDisplay.insert(END,
                                   	'System ID:' + 4 * ' ' + self.gui.entrysystemID.get() + '\n' 
                                   	'User name:' + 4 * ' ' + self.gui.entryusername.get() + '\n' 
									'User phone:' + 3 * ' ' + self.gui.entryuserphone.get() + '\n' 
									'Sample ID:' + 4 * ' ' + self.gui.entrysampleID.get() + '\n' 
									'Location:' + 5 * ' ' + self.gui.entryLocation.get() + '\n')

        self.oldtime = time.time()
        self.startSysTime = self.gui.get_datetime()
        self.gui.txtDisplay.insert(END, 'System starts at: ' + self.startSysTime + '\n')
        self.gui.txtDisplay.insert(END, "Test type:     " + self.gui.modeVar.get() + "\n")
        self.gui.txtDisplay.insert(END, "Interval:      " + str(self.expPeriod) + " minutes. \n")
        self.gui.txtDisplay.insert(END, 'Data...' + '\n\n')
        gap = '    |    '
        self.gui.txtDisplay.insert(END, \
                                   '[Time' + '  | ' + 'Temp' + ' |   ' + '1A' + gap + '1B' + gap + '2A' + gap \
                                   + '2B ' + gap + '3A ' \
                                   + gap + '4A' + gap + '1C' + gap + '1D' + gap + '2C' + gap \
                                   + '2D' + gap + '3D' + gap + '4D  ]' + '\n')

    # --------------------------------------------------------------------------------------
    def resetData(self):
        del timestamps[:], temperatures[:], data[:], data1[:], data2[:], data3[:], data4[:], \
            data5[:], data6[:], data7[:], data8[:], data9[:], data10[:], data11[:], data12[:]
        del timestampspre[:], temperaturesT[:], temperaturesB[:], temperaturesTstop[:], temperaturesBstop[:], timestampsstop[:]
        del timestampsAb[:], ab[:], ab1[:], ab2[:], ab3[:], ab4[:], ab5[:], ab6[:], ab7[:], ab8[:], ab9[:], ab10[:], ab11[:], ab12[:]
        del timestampsDer[:], der[:], der1[:], der2[:], der3[:], der4[:], der5[:], der6[:], \
            der7[:], der8[:], der9[:], der10[:], der11[:], der12[:]
        del timestampsG[:], gruppe[:], gruppe1[:], gruppe2[:], gruppe3[:], gruppe4[:], gruppe5[:], gruppe6[:], \
            gruppe7[:], gruppe8[:], gruppe9[:], gruppe10[:], gruppe11[:], gruppe12[:]

    # --------------------------------------------------------------------------------------
    def make_fig(self):
        plt.clf()
        plt.title("Live graph of sensor data of ID " + self.expSampleID)
        plt.grid(True)
        plt.ylabel('Well')
        plt.xlabel("Time in minutes")
        plt.plot(timestamps, data1, label='1A', color='b', linestyle="--")
        plt.plot(timestamps, data2, label='1B', color='g', linestyle="-.")
        plt.plot(timestamps, data3, label='2A', color='r', linestyle=":")
        plt.plot(timestamps, data4, label='2B', color='c', linestyle="-.")
        plt.plot(timestamps, data5, label='3A', color='m', linestyle="-.")
        plt.plot(timestamps, data6, label='4A', color='y')
        plt.plot(timestamps, data7, label='1C', color='k')
        plt.plot(timestamps, data8, label='1D', color='b')
        plt.plot(timestamps, data9, label='2C', color='g')
        plt.plot(timestamps, data10, label='2D', color='r')
        plt.plot(timestamps, data11, label='3D', color='c')
        plt.plot(timestamps, data12, label='4D', color='m')
        plt.legend()

    # --------------------------------------------------------------------------------------
    def make_fig_temperature(self):
        plt.clf()
        plt.title('Temperature in Celcius Degree')
        plt.grid(True)
        plt.ylabel('Temperature')
        plt.xlabel("Time in minutes")
        plt.plot(timestamps, temperatures, label='temperature')
        plt.legend()

    # ------------------- Plot top and bottom temperature for system preparation----------------------------------------
    def make_fig_topbottom_temperature(self):
        plt.clf()
        self.tempC_T, self.tempC_B = self.readtemp()
        startTimeprefig = self.startTimepre
        temperaturesT.append(self.tempC_T)  # temperature top heater array
        temperaturesB.append(self.tempC_B)  # temperature bottom heater array
        runTimepre = time.time()  # realtime of loop.
        deltaTimepre = runTimepre - startTimeprefig
        timestampspre.append(round(float(deltaTimepre) / 60.0, 2))
        drawnow(self.make_fig_temperaturepre)
        plt.pause(0.1)

    # --------------------------------------------------------------------------------------
    def make_fig_temperaturepre(self):
        plt.clf()
        plt.title('Temperature in Celcius Degree')
        plt.grid(True)
        plt.ylabel('Temperature')
        plt.xlabel("Time in minutes")
        plt.plot(timestampspre, temperaturesT, label='Top heater', color='b', linestyle="--")
        plt.plot(timestampspre, temperaturesB, label='Bottom heater', color='g', linestyle="-.")
        plt.legend()

    # ------------------- Plot top and bottom temperature for stoping the system----------------------------------------
    def make_fig_topbottom_temperaturestop(self):
        plt.clf()
        self.tempC_T, self.tempC_B = self.readtemp()
        startTimestopfig = self.startTimestop
        temperaturesTstop.append(self.tempC_T)  # temperature top heater array
        temperaturesBstop.append(self.tempC_B)  # temperature bottom heater array
        runTimestop = time.time()  # realtime of loop.
        deltaTimestop = runTimestop - startTimestopfig
        timestampsstop.append(round(float(deltaTimestop) / 60.0, 2))
        drawnow(self.make_fig_temperaturestop)
        plt.pause(0.1)

    # --------------------------------------------------------------------------------------
    def make_fig_temperaturestop(self):
        plt.clf()
        plt.title('Temperature in Celcius Degree')
        plt.grid(True)
        plt.ylabel('Temperature')
        plt.xlabel("Time in minutes")
        plt.plot(timestampsstop, temperaturesTstop, label='Top heater', color='b', linestyle="--")
        plt.plot(timestampsstop, temperaturesBstop, label='Bottom heater', color='g', linestyle="-.")
        plt.legend()
    # --------------------------------------------------------------------------------------
    def make_fig_intensity(self):
        plt.clf()
        plt.title("Intensity of ID " + self.expSampleID)
        plt.grid(True)
        plt.xlabel("Time in minutes")
        plt.plot(timestampsAb, ab1, label='1A', color='b', linestyle="--")
        plt.plot(timestampsAb, ab2, label='1B', color='g', linestyle="-.")
        plt.plot(timestampsAb, ab3, label='2A', color='r', linestyle=":")
        plt.plot(timestampsAb, ab4, label='2B', color='c', linestyle="-.")
        plt.plot(timestampsAb, ab5, label='3A', color='m', linestyle="-.")
        plt.plot(timestampsAb, ab6, label='4A', color='y')
        plt.plot(timestampsAb, ab7, label='1C', color='k')
        plt.plot(timestampsAb, ab8, label='1D', color='b')
        plt.plot(timestampsAb, ab9, label='2C', color='g')
        plt.plot(timestampsAb, ab10, label='2D', color='r')
        plt.plot(timestampsAb, ab11, label='3D', color='c')
        plt.plot(timestampsAb, ab12, label='4D', color='m')
        plt.legend()

    # --------------------------------------------------------------------------------------
    def make_fig_all(self):
        fig, axes = plt.subplots(1, 2, figsize=(11, 5))
        axes[0].set_title("Derivation of ID " + self.expSampleID)
        axes[0].grid(True)
        axes[0].set_xlabel("Time in minutes")
        axes[0].plot(timestampsDer, der1, label='1A', color='b', linestyle="--")
        axes[0].plot(timestampsDer, der2, label='1B', color='g', linestyle="-.")
        axes[0].plot(timestampsDer, der3, label='2A', color='r', linestyle=":")
        axes[0].plot(timestampsDer, der4, label='2B', color='c', linestyle="-.")
        axes[0].plot(timestampsDer, der5, label='3A', color='m', linestyle="-.")
        axes[0].plot(timestampsDer, der6, label='4A', color='y')
        axes[0].plot(timestampsDer, der7, label='1C', color='k')
        axes[0].plot(timestampsDer, der8, label='1D', color='b')
        axes[0].plot(timestampsDer, der9, label='2C', color='g')
        axes[0].plot(timestampsDer, der10, label='2D', color='r')
        axes[0].plot(timestampsDer, der11, label='3D', color='c')
        axes[0].plot(timestampsDer, der12, label='4D', color='m')

        axes[1].set_title("Intensity of ID " + self.expSampleID)
        axes[1].grid(True)
        axes[1].set_xlabel("Time in minutes")
        axes[1].plot(timestampsAb, ab1, label='1A', color='b', linestyle="--")
        axes[1].plot(timestampsAb, ab2, label='1B', color='g', linestyle="-.")
        axes[1].plot(timestampsAb, ab3, label='2A', color='r', linestyle=":")
        axes[1].plot(timestampsAb, ab4, label='2B', color='c', linestyle="-.")
        axes[1].plot(timestampsAb, ab5, label='3A', color='m', linestyle="-.")
        axes[1].plot(timestampsAb, ab6, label='4A', color='y')
        axes[1].plot(timestampsAb, ab7, label='1C', color='k')
        axes[1].plot(timestampsAb, ab8, label='1D', color='b')
        axes[1].plot(timestampsAb, ab9, label='2C', color='g')
        axes[1].plot(timestampsAb, ab10, label='2D', color='r')
        axes[1].plot(timestampsAb, ab11, label='3D', color='c')
        axes[1].plot(timestampsAb, ab12, label='4D', color='m')
        plt.legend()

    # make fig all using matbackend
    def make_fig_abs_der(self):
        fig = Figure(figsize=(11, 5))
        # root.title('POC-LAMP' + '>> ' + self.pickedFilename)
        frame_graph = Frame(Toplevel())
        plot_canvas = FigureCanvasTkAgg(fig, master=frame_graph)
        plot_canvas.draw()
        plot_canvas.get_tk_widget().pack(side=TOP, fill=BOTH, expand=1)
        toolbar = NavigationToolbar2Tk(plot_canvas, frame_graph)
        toolbar.update()
        plot_canvas._tkcanvas.pack(side=TOP, fill=BOTH, expand=1)
        # label = Label(frame_graph, text=self.).pack(side=TOP, fill=BOTH, expand=1)
        frame_graph.pack()

        abs_plots = fig.add_subplot(121)
        der_plots = fig.add_subplot(122)
        der_plots.set_title("Derivation of ID " + self.expSampleID)
        der_plots.grid(True)
        der_plots.set_xlabel("Time in minutes")
        der_plots.set_ylabel("Signal from sensor")
        der_plots.plot(timestampsDer, der1, label='1A', color='b', linestyle="--")
        der_plots.plot(timestampsDer, der2, label='1B', color='g', linestyle="-.")
        der_plots.plot(timestampsDer, der3, label='2A', color='r', linestyle=":")
        der_plots.plot(timestampsDer, der4, label='2B', color='c', linestyle="-.")
        der_plots.plot(timestampsDer, der5, label='3A', color='m', linestyle="-.")
        der_plots.plot(timestampsDer, der6, label='4A', color='y')
        der_plots.plot(timestampsDer, der7, label='1C', color='k')
        der_plots.plot(timestampsDer, der8, label='1D', color='b')
        der_plots.plot(timestampsDer, der9, label='2C', color='g')
        der_plots.plot(timestampsDer, der10, label='2D', color='r')
        der_plots.plot(timestampsDer, der11, label='3D', color='c')
        der_plots.plot(timestampsDer, der12, label='4D', color='m')

        abs_plots.set_title("Intensity of ID " + self.expSampleID)
        abs_plots.grid(True)
        abs_plots.set_xlabel("Time in minutes")
        abs_plots.set_ylabel("Intensity")
        abs_plots.plot(timestampsAb, ab1, label='1A', color='b', linestyle="--")
        abs_plots.plot(timestampsAb, ab2, label='1B', color='g', linestyle="-.")
        abs_plots.plot(timestampsAb, ab3, label='2A', color='r', linestyle=":")
        abs_plots.plot(timestampsAb, ab4, label='2B', color='c', linestyle="-.")
        abs_plots.plot(timestampsAb, ab5, label='3A', color='m', linestyle="-.")
        abs_plots.plot(timestampsAb, ab6, label='4A', color='y')
        abs_plots.plot(timestampsAb, ab7, label='1C', color='k')
        abs_plots.plot(timestampsAb, ab8, label='1D', color='b')
        abs_plots.plot(timestampsAb, ab9, label='2C', color='g')
        abs_plots.plot(timestampsAb, ab10, label='2D', color='r')
        abs_plots.plot(timestampsAb, ab11, label='3D', color='c')
        abs_plots.plot(timestampsAb, ab12, label='4D', color='m')

        abs_plots.legend()
        der_plots.legend()

    # #--------------------------------------------------------------------------------------
    def make_fig_derivation(self):
        plt.clf()
        plt.title("Derivation of ID " + self.expSampleID)
        plt.grid(True)
        plt.xlabel("Time in minutes")

        plt.plot(timestampsDer, der1, label='1A', color='b', linestyle="--")
        plt.plot(timestampsDer, der2, label='1B', color='g', linestyle="-.")
        plt.plot(timestampsDer, der3, label='2A', color='r', linestyle=":")
        plt.plot(timestampsDer, der4, label='2B', color='c', linestyle="-.")
        plt.plot(timestampsDer, der5, label='3A', color='m', linestyle="-.")
        plt.plot(timestampsDer, der6, label='4A', color='y')
        plt.plot(timestampsDer, der7, label='1C', color='k')
        plt.plot(timestampsDer, der8, label='1D', color='b')
        plt.plot(timestampsDer, der9, label='2C', color='g')
        plt.plot(timestampsDer, der10, label='2D', color='r')
        plt.plot(timestampsDer, der11, label='3D', color='c')
        plt.plot(timestampsDer, der12, label='4D', color='m')
        plt.legend()

    # --------------------------------------------------------------------------------------
    def make_fig_derivation_gruppe(self):
        plt.clf()
        plt.title("Derivation grupped")
        plt.grid(True)
        plt.xlabel("Time in minutes")

        plt.plot(timestampsG, gruppe1, label='1A', color='b', linestyle="--")
        plt.plot(timestampsG, gruppe2, label='1B', color='g', linestyle="-.")
        plt.plot(timestampsG, gruppe3, label='2A', color='r', linestyle=":")
        plt.plot(timestampsG, gruppe4, label='2B', color='c', linestyle="-.")
        plt.plot(timestampsG, gruppe5, label='3A', color='m', linestyle="-.")
        plt.plot(timestampsG, gruppe6, label='4A', color='y')
        plt.plot(timestampsG, gruppe7, label='1C', color='k')
        plt.plot(timestampsG, gruppe8, label='1D', color='b')
        plt.plot(timestampsG, gruppe9, label='2C', color='g')
        plt.plot(timestampsG, gruppe10, label='2D', color='r')
        plt.plot(timestampsG, gruppe11, label='3D', color='c')
        plt.plot(timestampsG, gruppe12, label='4D', color='m')
        plt.legend()

    # --------------------------------------------------------------------------------------
    def callFigLamp(self, event):
        plt.clf()
        drawnow(self.make_fig)
        plt.pause(0.1)

    def callFigTemp(self, event):
        plt.clf()
        drawnow(self.make_fig_temperature)
        plt.pause(0.1)

    def callFigAbs(self):
        plt.clf()
        drawnow(self.make_fig_intensity)
        plt.pause(0.1)

    def callFigDer(self):
        plt.clf()
        drawnow(self.make_fig_derivation)
        plt.pause(0.1)

    # ------Save to csv file-----------------------------------------------------
    def add_dataline(self):
        # Create a single dataline as a list
        datalinecsv = [
            self.timer, self.inPut_b, self.inPut_t,self.well_1, self.well_2, self.well_3,
            self.well_4, self.well_5, self.well_6, self.well_7, self.well_8,
            self.well_9, self.well_10, self.well_11, self.well_12
        ]
        # Append the dataline to the list of datalines
        self.datalines.append(datalinecsv)

    def save_to_csv(self):
        current_time = str(datetime.now())  # yyyy-mm-dd hh:mm ---> need to remove ':' to write file on window
        current_time = current_time[0:13] + 'h' + current_time[14:16]
        path = os.getcwd() + '/Rawdata'
        if not os.path.isdir(path):
            os.mkdir(path)

        self.filename = path + '/' + str(current_time) + ' _' + str(self.expSampleID) + '.csv'

        # Prepare metadata and header
        metadata = [
            ["System ID", self.gui.entrysystemID.get()],
            ["User name", self.gui.entryusername.get()],
            ["User phone", self.gui.entryuserphone.get()],
            ["Sample ID", self.gui.entrysampleID.get()],
            ["Location", self.gui.entryLocation.get()],
            ["Date and Time of test", self.gui.get_datetime()],
            ["Test type", self.expMode],
            ["Interval", self.expPeriod]
        ]

        # Define the CSV header
        header = [
            "TIMER", "BOTTOM", "TOP", "WELL 1A", "WELL 1B", "WELL 2A", "WELL 2B",
            "WELL 3A", "WELL 4A", "WELL 1C", "WELL 1D", "WELL 2C",
            "WELL 2D", "WELL 3D", "WELL 4D"
        ]

        # Write the datalines to a CSV file
        with open(self.filename, mode='w', newline='') as file:
            writer = csv.writer(file)

            # Write metadata as separate rows
            writer.writerows(metadata)

            # Add a blank row (optional) to separate metadata from the header
            writer.writerow([])
            
            # Write the header row
            writer.writerow(header)  
            
            # Write all datalines
            writer.writerows(self.datalines)

        #print(f"Data saved to {filename}.")

    # ------Save to excel file-----------------------------------------------------
    def write_to_file(self):
        current_time = str(datetime.now())  # yyyy-mm-dd hh:mm ---> need to remove ':' to write file on window
        current_time = current_time[0:13] + 'h' + current_time[14:16]
        if not self.isCSV:
            path = os.getcwd() + '/DATA ONLINE'
        else:
            path = os.getcwd() + '/DATA CSV'
        if not os.path.isdir(path):
            os.mkdir(path)

        self.filename = path + '/' + str(current_time) + ' _' + str(self.expSampleID) + '.xlsx'

        workbook = xlsxwriter.Workbook(self.filename)
        worksheet1 = workbook.add_worksheet()  # final report
        worksheet2 = workbook.add_worksheet()  # for raw data
        worksheet3 = workbook.add_worksheet()  # for intensity data
        worksheet4 = workbook.add_worksheet()  # for derivation data
        worksheet5 = workbook.add_worksheet()  # for charts of Intensity and Derivation
        worksheet6 = workbook.add_worksheet()  # for charts of Heating
        worksheet7 = workbook.add_worksheet()  # charts of raw LAMP

        chartAb = workbook.add_chart({'type': 'line'})
        chartHeat = workbook.add_chart({'type': 'line'})
        chartLAMP = workbook.add_chart({'type': 'line'})
        chartDer = workbook.add_chart({'type': 'line'})

        bold = workbook.add_format({'bold': True})

        # writing final report
        worksheet1.write('A1', 'General report', bold)
        worksheet1.write('H1', 'Samples Name', bold)
        worksheet1.write('A2', "User Name:" + 6 * " " + self.gui.entryusername.get())
        worksheet1.write('A3', "Sample ID:" + 4 * " " + self.expSampleID)
        worksheet1.write('A4', "Location:" + 5 * " " + self.gui.entryLocation.get())
        worksheet1.write('A5', "System starts at: " + self.expStartAt)
        worksheet1.write('A6', "System stops at: " + self.expStopAt)
        worksheet1.write('A7', "Running Mode:    " + self.expMode)
        worksheet1.write('A8', "Time of Experiment: " + str(self.expPeriod) + " minutes")
        worksheet1.write('A9', " ")
        gap1 = 3 * ' '
        gap2 = 6 * ' '
        worksheet1.write('A11', gap1 + '1A ' + self.sign[0] + gap2 + '1B ' + self.sign[1] + gap2 + \
                         '1C ' + self.sign[6] + gap2 + '1D ' + self.sign[7])

        worksheet1.write('A12', gap1 + '2A ' + self.sign[2] + gap2 + '2B ' + self.sign[3] + gap2 + \
                         '2C ' + self.sign[8] + gap2 + '2D ' + self.sign[9])

        worksheet1.write('A13', gap1 + '3A ' + self.sign[4] + gap2 * 5 + '   3D ' + self.sign[10])
        worksheet1.write('A14', gap1 + '4A ' + self.sign[5] + gap2 * 5 + '   4D ' + self.sign[11])
        well_name = ['1A', '1B', '2A', '2B', '3A', '4A', '1C', '1D', '2C', '2D', '3D', '4D']
        pos = 15
        for i in range(len(self.sign)):
            if self.sign[i] == '+':
                worksheet1.write('A' + str(pos), 'Sample ' + well_name[i] + ' is positive, at ' + str(
                    self.timePositive[i]) + ' minutes.')
                pos += 1
        row = 1
        col = 7
        for well, name in zip(well_name, self.samplesName):
            worksheet1.write(row, col, well)
            worksheet1.write(row, col + 1, name)
            row += 1

        # writing raw data
        worksheet2.write('A1', 'Timestamp', bold)
        worksheet2.write('B1', 'Temperature', bold)
        worksheet2.write('C1', '1A', bold)
        worksheet2.write('D1', '1B', bold)
        worksheet2.write('E1', '2A', bold)
        worksheet2.write('F1', '2B', bold)
        worksheet2.write('G1', '3A', bold)
        worksheet2.write('H1', '4A', bold)
        worksheet2.write('I1', '1C', bold)
        worksheet2.write('J1', '1D', bold)
        worksheet2.write('K1', '2C', bold)
        worksheet2.write('L1', '2D', bold)
        worksheet2.write('M1', '3D', bold)
        worksheet2.write('N1', '4D', bold)

        row = 1
        col = 0
        for line in data:
            for i in range(len(line)):
                worksheet2.write(row, col + i, float(line[i]))
            row += 1

        # Worksheet 3 for saving intensity data
        worksheet3.write('A1', 'Timestamp', bold)
        worksheet3.write('B1', 'Ab 1A', bold)
        worksheet3.write('C1', 'Ab 1B', bold)
        worksheet3.write('D1', 'Ab 2A', bold)
        worksheet3.write('E1', 'Ab 2B', bold)
        worksheet3.write('F1', 'Ab 3A', bold)
        worksheet3.write('G1', 'Ab 4A', bold)
        worksheet3.write('H1', 'Ab 1C', bold)
        worksheet3.write('I1', 'Ab 1D', bold)
        worksheet3.write('J1', 'Ab 2C', bold)
        worksheet3.write('K1', 'Ab 2D', bold)
        worksheet3.write('L1', 'Ab 3D', bold)
        worksheet3.write('M1', 'Ab 4D', bold)

        row = 1
        for timestamps, ab_1, ab_2, ab_3, ab_4, ab_5, ab_6, ab_7, ab_8, ab_9, ab_10, ab_11, ab_12 \
                in zip(timestampsAb, ab1, ab2, ab3, ab4, ab5, ab6, ab7, ab8, ab9, ab10, ab11, ab12):
            worksheet3.write(row, col, timestamps)
            worksheet3.write(row, col + 1, ab_1)
            worksheet3.write(row, col + 2, ab_2)
            worksheet3.write(row, col + 3, ab_3)
            worksheet3.write(row, col + 4, ab_4)
            worksheet3.write(row, col + 5, ab_5)
            worksheet3.write(row, col + 6, ab_6)
            worksheet3.write(row, col + 7, ab_7)
            worksheet3.write(row, col + 8, ab_8)
            worksheet3.write(row, col + 9, ab_9)
            worksheet3.write(row, col + 10, ab_10)
            worksheet3.write(row, col + 11, ab_11)
            worksheet3.write(row, col + 12, ab_12)
            row += 1

            # Worksheet 4 for saving derivation data
        worksheet4.write('A1', 'Timestamp', bold)
        worksheet4.write('B1', 'Der 1A', bold)
        worksheet4.write('C1', 'Der 1B', bold)
        worksheet4.write('D1', 'Der 2A', bold)
        worksheet4.write('E1', 'Der 2B', bold)
        worksheet4.write('F1', 'Der 3A', bold)
        worksheet4.write('G1', 'Der 4A', bold)
        worksheet4.write('H1', 'Der 1C', bold)
        worksheet4.write('I1', 'Der 1D', bold)
        worksheet4.write('J1', 'Der 2C', bold)
        worksheet4.write('K1', 'Der 2D', bold)
        worksheet4.write('L1', 'Der 3D', bold)
        worksheet4.write('M1', 'Der 4D', bold)

        row = 1
        for timestamps, der_1, der_2, der_3, der_4, der_5, der_6, der_7, der_8, der_9, der_10, der_11, der_12 \
                in zip(timestampsDer, der1, der2, der3, der4, der5, der6, der7, der8, der9, \
                       der10, der11, der12):
            worksheet4.write(row, col, timestamps)
            worksheet4.write(row, col + 1, der_1)
            worksheet4.write(row, col + 2, der_2)
            worksheet4.write(row, col + 3, der_3)
            worksheet4.write(row, col + 4, der_4)
            worksheet4.write(row, col + 5, der_5)
            worksheet4.write(row, col + 6, der_6)
            worksheet4.write(row, col + 7, der_7)
            worksheet4.write(row, col + 8, der_8)
            worksheet4.write(row, col + 9, der_9)
            worksheet4.write(row, col + 10, der_10)
            worksheet4.write(row, col + 11, der_11)
            worksheet4.write(row, col + 12, der_12)
            row += 1

        # adding chart: LAMP, heating, Intensity
        # define colors
        colors = ['black', 'blue', 'brown', 'green', 'cyan', 'pink', 'purple', 'yellow', \
                  'red', 'gray', 'navy', 'lime']
        numOfValues = len(ab1)
        colName = ['B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M']
        chartAb.set_title({
            'name': 'Intensity',
            'name_font': {
                'name': 'Calibri',
                'color': 'blue',
            },
        })
        chartAb.set_x_axis({
            'name': 'LAMP interval for ' + str(self.expPeriod) + ' minutes',
            'name_font': {
                'name': 'Courier New',
                'color': '#92D050'
            },
            'num_font': {
                'name': 'Arial',
                'color': '#00B0F0',
            },
        })
        for colname, color in zip(colName, colors):
            chartAb.add_series({'name': 'Sheet3!$' + colname + '$1',
                                'categories': '=Sheet3!$A$2:$A$' + str(numOfValues),
                                'values': '=Sheet3!$' + colname + '$2:$' + colname + '$' + str(numOfValues),
                                'line': {'color': color, 'width': 1.5}, })
        worksheet5.insert_chart('A2', chartAb)

        # adding chart derivation
        numOfValues = len(der1)
        chartDer.set_title({
            'name': 'Derivation',
            'name_font': {
                'name': 'Calibri',
                'color': 'red',
            },
        })
        chartDer.set_x_axis({
            'name': 'LAMP interval for ' + str(self.expPeriod) + ' minutes',
            'name_font': {
                'name': 'Courier New',
                'color': '#92D050'
            },
            'num_font': {
                'name': 'Arial',
                'color': '#00B0F0',
            },
        })
        for colname, color in zip(colName, colors):
            chartDer.add_series({'name': 'Sheet4!$' + colname + '$1',
                                 'categories': '=Sheet4!$A$2:$A$' + str(numOfValues),
                                 'values': '=Sheet4!$' + colname + '$2:$' + colname + '$' + str(numOfValues),
                                 'line': {'color': color, 'width': 1.5}, })
        worksheet5.insert_chart('J2', chartDer)

        # ------- HEATS chart-----------------------------------------------------------------------------------------------
        numOfValues = len(data1)
        chartHeat.add_series({'name': 'Heating',
                              'categories': '=Sheet2!$a$2:$A$' + str(numOfValues),
                              'values': '=Sheet2!$B$2:B$' + str(numOfValues),
                              'line': {'width': 1.5}, })
        worksheet6.insert_chart('A2', chartHeat)

        # -------LAMPs charts-----------------------------------------------------------------------------------------------
        numOfValues = len(data1)
        colName = ['C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N']
        chartLAMP.set_title({
            'name': 'LAMP',
            'name_font': {
                'name': 'Calibri',
                'color': 'red',
            },
        })
        chartLAMP.set_x_axis({
            'name': 'LAMP interval for ' + str(self.expPeriod) + ' minutes',
            'name_font': {
                'name': 'Courier New',
                'color': '#92D050'
            },
            'num_font': {
                'name': 'Arial',
                'color': '#00B0F0',
            },
        })
        for colname, color in zip(colName, colors):
            chartLAMP.add_series({'name': 'Sheet2!$' + colname + '$1',
                                  'categories': '=Sheet2!$a$2:$A$' + str(numOfValues),
                                  'values': '=Sheet2!$' + colname + '$2:$' + colname + '$' + str(numOfValues),
                                  'line': {'color': color, 'width': 1.5}, })
        worksheet7.insert_chart('A2', chartLAMP)

        workbook.close()
        self.isCSV = False

    # -------------------Process button click when open raw data file ----------------------------------------
    def processfile(self):

        optionMode = self.gui.OpenVar.get()
        if optionMode != 'Select Mode':
            self.isModeSelected = True
            self.expMode = optionMode

            if self.gui.checkVar.get():
                self.expPeriodCut = int(self.gui.lampInterval.get())
                self.expMode = 'Custom'
            else:
                if self.expMode == 'COV':
                    self.expPeriodCut = 50  # 50 miute limit for COV
                elif self.expMode == 'Sal':
                    self.expPeriodCut = 50  # 50 miute limit for Sal
                elif self.expMode == 'Cam':
                    self.expPeriodCut = 60  # 60 miute limit for Cam
                else:
                    self.expPeriodCut = int(self.expPeriod)  # time for experiment in cuctom mode

            self.readCsv()
        else:
            mess.showinfo("Running mode invalid", "Please select a running mode...")

# --------------- READ CSV FILE -----------------------------------------------------------------------------------------------------
    def readCsv(self):
        index = 0
        if self.isFileOpen and self.isModeSelected:
            if self.pickedFilename.endswith('.CSV') or self.pickedFilename.endswith('.csv'):
                self.resetData()
                plt.clf()
                with open(self.pickedFilename, 'r') as csv_file:
                    csv_reader = csv.reader(csv_file, delimiter=',')  # returns list
                    line_count = 0
                    temp = []
                    for row in csv_reader:
                        if line_count <= 6:
                            if len(row) == 1:
                                temp.append(row[0])
                            line_count += 1
                        else:
                            if (len(row) > 4) and (round(float(row[0]) / 60.0, 2) <= self.expPeriodCut):
                                timestamps.append(round(float(row[0]) / 60.0, 2))
                                temperatures.append(float(row[1]))  # temperature
                                data1.append(float(row[3]))  # well
                                data2.append(float(row[4]))
                                data3.append(float(row[5]))
                                data4.append(float(row[6]))
                                data5.append(float(row[7]))
                                data6.append(float(row[8]))
                                data7.append(float(row[9]))
                                data8.append(float(row[10]))
                                data9.append(float(row[11]))
                                data10.append(float(row[12]))
                                data11.append(float(row[13]))
                                data12.append(float(row[14]))
                                line = []
                                line.extend(
                                    (timestamps[-1], temperatures[-1], data1[-1], data2[-1], data3[-1], data4[-1], \
                                     data5[-1], data6[-1], data7[-1], \
                                     data8[-1], data9[-1], data10[-1], data11[-1], data12[-1]))
                                data.append(line)
                    #self.expStartAt = str(temp[0][22:])
                    self.expPeriod = temp[1][20:23]
                    #self.expMode = str(temp[1][39:])
                    #self.expSampleID = str(temp[2][11:])

                    # For test only----------
                    #'System ID:' + self.gui.entrysystemID.get()
                    #'User name:' + self.gui.entryusername.get()
                    #'User phone:' + self.gui.entryuserphone.get()
                    self.expSampleID = self.gui.entrysampleID.get()
                    #'Location:' + self.gui.entryLocation.get()
                    #self.expStartAt = self.gui.get_datetime()
                    self.expMode = self.expMode
                    #'Interval: ' + str(self.expPeriod)
                    # End test data ------------------

                for i in range(len(timestamps)):
                    if index == 0:
                        if timestamps[i] > 4.98:  # start calculation time at 5 min
                            index = i
                lastIndex = index + 12

                ref1 = np.mean(data1[index:lastIndex])
                ref2 = np.mean(data2[index:lastIndex])
                ref3 = np.mean(data3[index:lastIndex])
                ref4 = np.mean(data4[index:lastIndex])
                ref5 = np.mean(data5[index:lastIndex])
                ref6 = np.mean(data6[index:lastIndex])
                ref7 = np.mean(data7[index:lastIndex])
                ref8 = np.mean(data8[index:lastIndex])
                ref9 = np.mean(data9[index:lastIndex])
                ref10 = np.mean(data10[index:lastIndex])
                ref11 = np.mean(data11[index:lastIndex])
                ref12 = np.mean(data12[index:lastIndex])

                for j in range(len(data1[index:])):
                    i = index + j
                    timestampsAb.append(timestamps[i])
                    ab1.append(data1[i] - ref1)
                    ab2.append(data2[i] - ref2)
                    ab3.append(data3[i] - ref3)
                    ab4.append(data4[i] - ref4)
                    ab5.append(data5[i] - ref5)
                    ab6.append(data6[i] - ref6)
                    ab7.append(data7[i] - ref7)
                    ab8.append(data8[i] - ref8)
                    ab9.append(data9[i] - ref9)
                    ab10.append(data10[i] - ref10)
                    ab11.append(data11[i] - ref11)
                    ab12.append(data12[i] - ref12)

                self.isFileOpen = False
                self.isModeSelected = False
                self.isCalDerivation = False
                self.isCSV = True
                self.gui.OpenOpMenu.config(state=DISABLED)
                self.gui.btProcess.config(state=DISABLED)

                # --- Active Results frame
                self.gui.btLampFigs.config(state=ACTIVE)
                self.gui.btTempFig.config(state=ACTIVE)
                self.gui.btDerAbs.config(state=ACTIVE)
                self.gui.btAbsFigs.config(state=ACTIVE)
                self.gui.btReport.config(state=ACTIVE)
                self.gui.btSendRS.config(state=ACTIVE)

                try:
                    self.derivativeRaw()
                    self.findRates()
                    self.findPeakWidth()
                    self.createFinalReport()
                    self.write_to_file()
                except:
                    self.write_to_file()
        else:
            plt.clf()
            self.make_fig_abs_der()

    # --------------- Select Mode when Open file -----------------------------
    def ModeSelected(self):
        if self.isFileOpen:
            if self.pickedFilename.endswith('.CSV') or self.pickedFilename.endswith('.csv'):
                self.resetData()
                plt.clf()
                with open(self.pickedFilename, 'r') as csv_file:
                    csv_reader = csv.reader(csv_file, delimiter=',')  # returns list
                    line_count = 0
                    temp = []
                    for row in csv_reader:
                        if line_count <= 6:
                            if len(row) == 1:
                                temp.append(row[0])
                            line_count += 1

                    self.expPeriod = temp[1][20:23]
                    self.expMode = str(temp[1][39:])

                    if self.expMode != 'COV' and self.expMode != 'Sal' and self.expMode != 'Cam':
                        self.gui.OpenOpMenu.config(state=ACTIVE)
                        self.gui.btProcess.config(state=ACTIVE)
                        self.isModeSelected = False
                        mess.showinfo("Select running mode", "Please select a running mode...")
                    else:
                        self.isModeSelected = True

                        if self.gui.checkVar.get():
                            self.expPeriodCut = int(self.gui.lampInterval.get())
                        else:
                            if self.expMode == 'COV':
                                self.expPeriodCut = 50  # 50 miute limit for COV
                            elif self.expMode == 'Sal':
                                self.expPeriodCut = 50  # 50 miute limit for Sal
                            elif self.expMode == 'Cam':
                                self.expPeriodCut = 60  # 60 miute limit for Cam

                        self.readCsv()
        else:
            plt.clf()
            self.make_fig_abs_der()

    # ------------------FIND MIN VALUE OF SLOPE WITH LIMIT-----------------------
    def findMin(self, npArr, index, limit):
        npArr = npArr
        index = index
        limit = limit
        minVal = npArr[index]
        for i in range(len(npArr[index:])):
            temp = npArr[index:][i]
            if temp > limit and minVal > temp:
                minVal = temp
        return minVal

    # -----------------------------------------------------------------------------------------------
    def findRates(self):
        i = 0
        for j in range(len(timestamps)):
            if i == 0:
                if timestamps[j] >= 5:  # start calculation time at 5 min
                    i = j
        maxPeak = []
        minPeak = []
        refPeak = []
        lowLimit = 100.0  # Chip possition error at 100

        minPeak.extend((self.findMin(data1, i, lowLimit), self.findMin(data2, i, lowLimit),
                        self.findMin(data3, i, lowLimit), self.findMin(data4, i, lowLimit) \
                            , self.findMin(data5, i, lowLimit), self.findMin(data6, i, lowLimit),
                        self.findMin(data7, i, lowLimit), self.findMin(data8, i, lowLimit) \
                            , self.findMin(data9, i, lowLimit), self.findMin(data10, i, lowLimit),
                        self.findMin(data11, i, lowLimit), self.findMin(data12, i, lowLimit)))

        maxPeak.extend((np.max(data1[i:]), np.max(data2[i:]), np.max(data3[i:]), np.max(data4[i:]), np.max(data5[i:]),
                        np.max(data6[i:]),
                        np.max(data7[i:]), np.max(data8[i:]), np.max(data9[i:]), np.max(data10[i:]), np.max(data11[i:]),
                        np.max(data12[i:])))

        lastIndex = i + 12
        refPeak.extend((np.mean(data1[i:lastIndex]), np.mean(data2[i:lastIndex]), np.mean(data3[i:lastIndex]),
                        np.mean(data4[i:lastIndex]), np.mean(data5[i:lastIndex]), np.mean(data6[i:lastIndex]),
                        np.mean(data7[i:lastIndex]), np.mean(data8[i:lastIndex]), np.mean(data9[i:lastIndex]),
                        np.mean(data10[i:lastIndex]), np.mean(data11[i:lastIndex]), np.mean(data12[i:lastIndex])))

        self.rate = []
        for i in range(len(maxPeak)):
            temp = (maxPeak[i] - minPeak[i])
            self.rate.append(temp)

    # --------------- DERIVATION OF RAW SLOPES-----------------------------------------------------------
    def derivativeRaw(self):
        if not self.isCalDerivation:
            # calculate mean signal
            index = 0
            for i in range(len(timestamps)):
                if index == 0:
                    if timestamps[i] > 5:  # start calculation time at 5 min
                        index = i
            a = int(len(data1[index:]) / 10) # 10 data point average
            id1 = 0
            id2 = 0
            for j in range(0, a):
                id1 = j * 10
                id2 = (j + 1) * 10 - 1
                idMiddle = id1 + 5
                timestampsG.append(timestamps[index:][idMiddle])
                gruppe1.append(np.mean(data1[index:][id1:id2]))
                gruppe2.append(np.mean(data2[index:][id1:id2]))
                gruppe3.append(np.mean(data3[index:][id1:id2]))
                gruppe4.append(np.mean(data4[index:][id1:id2]))
                gruppe5.append(np.mean(data5[index:][id1:id2]))
                gruppe6.append(np.mean(data6[index:][id1:id2]))
                gruppe7.append(np.mean(data7[index:][id1:id2]))
                gruppe8.append(np.mean(data8[index:][id1:id2]))
                gruppe9.append(np.mean(data9[index:][id1:id2]))
                gruppe10.append(np.mean(data10[index:][id1:id2]))
                gruppe11.append(np.mean(data11[index:][id1:id2]))
                gruppe12.append(np.mean(data12[index:][id1:id2]))

            # calculate derivation of mean signals
            for i in range(0, len(gruppe1) - 1):
                # for i in range(1, len(gruppe1)-1):
                # preId = i-1
                preId = i
                lastId = i + 1
                timestampsDer.append(timestampsG[i])
                # deltaTime = timestampsG[lastId] - timestampsG[preId]
                deltaTime = 1.0  # for average sampling point at 30
                der1.append(abs(gruppe1[lastId] - gruppe1[preId]) / deltaTime)
                der2.append(abs(gruppe2[lastId] - gruppe2[preId]) / deltaTime)
                der3.append(abs(gruppe3[lastId] - gruppe3[preId]) / deltaTime)
                der4.append(abs(gruppe4[lastId] - gruppe4[preId]) / deltaTime)
                der5.append(abs(gruppe5[lastId] - gruppe5[preId]) / deltaTime)
                der6.append(abs(gruppe6[lastId] - gruppe6[preId]) / deltaTime)
                der7.append(abs(gruppe7[lastId] - gruppe7[preId]) / deltaTime)
                der8.append(abs(gruppe8[lastId] - gruppe8[preId]) / deltaTime)
                der9.append(abs(gruppe9[lastId] - gruppe9[preId]) / deltaTime)
                der10.append(abs(gruppe10[lastId] - gruppe10[preId]) / deltaTime)
                der11.append(abs(gruppe11[lastId] - gruppe11[preId]) / deltaTime)
                der12.append(abs(gruppe12[lastId] - gruppe12[preId]) / deltaTime)

            self.isCalDerivation = True
        self.make_fig_abs_der()

    # --------Find derivative peak whitout peakWidthLimit - peakWidthLimit = 0 minute- The same with POD-LAMP firmware--------
    def findPeakWidth(self):
        self.maxDer = []
        maxDerTime = []

        if self.gui.checkVar.get():
            self.rateLimit = float(self.gui.enRate.get())
            self.noiseThreshold = float(self.gui.enNoiseThres.get())
        else:

            if self.expMode == 'COV':
                self.rateLimit = 8000
                self.noiseThreshold = 350.0
            elif self.expMode == 'Sal':
                self.rateLimit = 8000
                self.noiseThreshold = 350.0
            elif self.expMode == 'Cam':
                self.rateLimit = 8000
                self.noiseThreshold = 350.0
            else:
                self.expMode = 'Custom'
                self.rateLimit = 8000
                self.noiseThreshold = 350.0

        self.maxDer.extend((np.max(der1), np.max(der2), np.max(der3), np.max(der4), np.max(der5), np.max(der6), \
                       np.max(der7), np.max(der8), np.max(der9), np.max(der10), np.max(der11), np.max(der12)))

        maxDerTime.extend((timestampsDer[np.argmax(der1)], timestampsDer[np.argmax(der2)],
                           timestampsDer[np.argmax(der3)], timestampsDer[np.argmax(der4)],
                           timestampsDer[np.argmax(der5)], timestampsDer[np.argmax(der6)], \
                           timestampsDer[np.argmax(der7)], timestampsDer[np.argmax(der8)],
                           timestampsDer[np.argmax(der9)], timestampsDer[np.argmax(der10)],
                           timestampsDer[np.argmax(der11)], timestampsDer[np.argmax(der12)]))

        print("rate: ", self.rate)
        print("derivative: ", self.maxDer)

        for i in range(0, 12):
            if self.rate[i] > self.rateLimit:
                if self.maxDer[i] > self.noiseThreshold:
                    self.sign[i] = '+'
                    self.timePositive[i] = str(maxDerTime[i])
                else:
                    self.sign[i] = '-'
            else:
                self.sign[i] = '-'

# --------------------------------------------------------------------------

if __name__ == "__main__":
    app = ThreadedAction(root)

    root.mainloop()
