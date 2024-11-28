import time
import math

class LampPID:
    def __init__(self, set_point, last_set_point, stop_heat_temp, input_val, output_val):
        # Initialization, where set_point, last_set_point, stop_heat_temp, input_val, and output_val are references (lists of length 1)
        self.our_set_point = set_point
        self.our_last_set_point = last_set_point
        self.our_stop_heater_point = stop_heat_temp
        self.our_input = input_val
        self.our_output = output_val

        self.last_input = 0.0

        # Logic control
        self.set_point_reached = False
        self.set_point_not_run = True
        self.last_set_point_reached = False
        self.last_set_point_not_run = True

        # Time control
        self.previous_millis = 0.0
        self.timer_last_set_point = 0.0
        self.set_point_time = 0.0
        self.set_time = 1000.0
        self.last_time = self.millis() - self.set_time

        # PID gain variables
        self.kp = 0.0
        self.ki = 0.0
        self.kd = 0.0

        # PID control variables
        self.ITerm = 0.0
        self.Derror = 0.0

    def millis(self):
        # Placeholder for a time function (mimicking Arduino's millis()).
        #import time
        return int(round(time.time() * 1000))

    def set_pid_gain(self, Kp, Ki, Kd):
        our_set_time = self.set_time / 1000.0
        self.kp = Kp
        self.ki = Ki * our_set_time
        self.kd = Kd / our_set_time

    def temp_cal(self):
        if self.our_input > (self.our_set_point - 2):
            self.set_point_reached = True
        self.current_millis = self.millis()

    def pid(self):
        now = self.millis()
        time_change = now - self.last_time

        if time_change > self.set_time:
            input_val = self.our_input
            error = self.our_set_point - input_val  # Calculate error 
            self.ITerm += self.ki * error
            self.Derror = input_val - self.last_input

            # Check for integral windup and correct limits
            self.ITerm = min(max(self.ITerm, 0), 255)

            # Preparing the output variable
            output = self.kp * error + self.ITerm + self.Derror * self.kd

            # Limit the output between 0 and 255
            output = min(max(output, 0), 255)

            if math.isnan(output):	# Check to prevent interruption from NaN values
                return False
            
            self.our_output = output
            self.last_input = input_val
            self.last_time = now

            return True
        else:
            return False

    def time_cal(self, lamp_interval, last_point_interval):
        self.lamp_interval = lamp_interval*1000  # millis second
        self.last_point_interval = last_point_interval*1000  # millis second

        if self.set_point_reached and self.set_point_not_run:
            self.set_point_not_run = False
            self.set_point_time = self.current_millis

        if (self.current_millis - self.set_point_time >= self.lamp_interval) and not self.set_point_not_run:
            self.our_set_point = self.our_last_set_point
            self.set_point_time = self.current_millis

        if self.our_input > (self.our_last_set_point - 1):
            self.last_set_point_reached = True

        if self.last_set_point_reached and self.last_set_point_not_run:
            self.last_set_point_not_run = False
            self.timer_last_set_point = self.current_millis

        if (self.current_millis - self.timer_last_set_point >= self.last_point_interval) and not self.last_set_point_not_run:
            self.our_set_point = self.our_stop_heater_point  # Stop heating
            
