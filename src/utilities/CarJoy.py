import numpy as np


class CarJoy:
    def __init__(self, configuration, update_override=None):
        # units in percentage range 0..1
        self.steering = 0.0
        self.throttle = 0.0
        self.braking = 0.0
        self.gear = 0
        self.d_steering = 0.0
        self.d_throttle = 0.0
        self.d_braking = 0.0

        self.linear_command = 0.0
        self.d_linear = 0.0
        self.steering_command = 0.0

        # telemetry
        self.batVoltage_mV = 0

        self.__override_enabled = update_override is not None and configuration.model_override_enabled
        self.__update_override = update_override

    async def update(self, steering_command, linear_command):
        try:
            self.__update_steering(steering_command, self.__override_enabled)
            self.__update_linear_movement(linear_command, self.__override_enabled)

            if self.__override_enabled:
                await self.__update_override(self, (steering_command, linear_command))
        except Exception as ex:
            print("Car update exception: {}".format(ex))

    def __update_steering(self, steering_command, control_override: bool):
        self.d_steering = steering_command - self.steering_command
        self.steering_command = steering_command

        if not control_override:
            if self.d_steering < 0.0:
                self.steering = max(-1.0, self.steering + self.d_steering)
            elif self.d_steering > 0.0:
                self.steering = min(1.0, self.steering + self.d_steering)

    def __update_linear_movement(self, linear_command, control_override: bool):
        self.d_linear = linear_command - self.linear_command

        if (self.linear_command <= 0.0 <= linear_command or self.linear_command >= 0.0 >= linear_command) and not control_override:
            self.gear = 0
        self.linear_command = linear_command

        if self.d_linear == 0.0:
            self.d_throttle = 0.0
        elif self.d_linear > 0.0:
            if self.gear == 0:  # start drive forward
                self.__takeoff(1, control_override)
            elif self.gear == -1:
                self.__decelerate(control_override)
            elif self.gear == 1:
                self.__accelerate(control_override)
        elif self.d_linear < 0.0:
            if self.gear == 0:  # start drive backward
                self.__takeoff(-1, control_override)
            elif self.gear == -1:
                self.__accelerate(control_override)
            elif self.gear == 1:
                self.__decelerate(control_override)

    def __takeoff(self, gear, control_override: bool):
        self.d_throttle = self.d_linear * self.gear
        if not control_override:
            self.gear = gear
            self.throttle = 0.0

    def __accelerate(self, control_override: bool):
        self.d_throttle = self.d_linear * self.gear
        if not control_override:
            self.throttle = min(1.0, self.throttle + self.d_throttle)

    def __decelerate(self, control_override: bool):
        self.d_throttle = -1 * np.abs(self.d_linear)
        if not control_override:
            self.throttle = max(0.0, self.throttle + self.d_throttle)

    def ext_update(self, predict_dict, commands):
        steering_command, linear_command = commands

        if predict_dict['supervisor']:
            self.__update_linear_movement(linear_command, False)
            self.__update_steering(steering_command, False)
        else:
            self.gear = predict_dict['d_gear']
            self.throttle = min(1.0, self.throttle + predict_dict['d_throttle'])
            self.braking = min(1.0, self.braking + predict_dict['d_braking'])

            if predict_dict['d_steering'] < 0:
                self.steering = max(-1.0, self.steering + predict_dict['d_steering'])
            else:
                self.steering = min(1.0, self.steering + predict_dict['d_steering'])
