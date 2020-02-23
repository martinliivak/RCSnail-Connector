import numpy as np


class JoystickCar2:
    def __init__(self, configuration, update_override=None):
        # units in percentage range 0..1
        self.steering = 0.0
        self.throttle = 0.0
        self.braking = 0.0
        self.gear = 0
        self.d_steering = 0.0
        self.d_throttle = 0.0
        self.d_braking = 0.0
        self.d_gear = 0

        self.p_steering = 0.0

        self.linear_command = 0.0
        self.d_linear = 0.0
        self.steering_command = 0.0

        # telemetry
        self.batVoltage_mV = 0

        self.__override_enabled = update_override is not None and configuration.model_override_enabled
        self.__update_override = update_override

    async def update(self, steering_command, linear_command):
        try:
            self.__update_gear(self.__override_enabled)
            self.__update_steering(steering_command, self.__override_enabled)
            self.__update_linear_movement(linear_command, self.__override_enabled)

            if self.__override_enabled:
                await self.__update_override(self, (steering_command, linear_command))
        except Exception as ex:
            print("Car update exception: {}".format(ex))

    def __update_gear(self, control_override: bool):
        if not control_override:
            self.gear = self.d_gear

    def __update_steering(self, steering_command, control_override: bool):
        self.d_steering = steering_command - self.steering_command

        if not control_override:
            self.steering_command = steering_command

            if self.d_steering < 0.0:
                self.steering = max(-1.0, self.steering + self.d_steering)
            elif self.d_steering > 0.0:
                self.steering = min(1.0, self.steering + self.d_steering)

    def gear_up(self):
        if self.d_gear == -1:
            self.d_gear = 0
        elif self.d_gear == 0:
            self.d_gear = 1

    def gear_down(self):
        if self.d_gear == 1:
            self.d_gear = 0
        elif self.d_gear == 0:
            self.d_gear = -1

    def __update_linear_movement(self, linear_command, control_override: bool):
        self.d_linear = linear_command - self.linear_command

        if not control_override:
            self.linear_command = linear_command

        if self.d_linear == 0.0:
            self.d_throttle = 0.0
        elif self.d_linear > 0.0 and self.gear is not 0:
            self.__accelerate(control_override)
        elif self.d_linear < 0.0 and self.gear is not 0:
            self.__decelerate(control_override)

    def __accelerate(self, control_override: bool):
        self.d_throttle = self.d_linear
        if not control_override:
            self.throttle = min(1.0, self.throttle + self.d_throttle)

    def __decelerate(self, control_override: bool):
        self.d_throttle = -1.0 * np.abs(self.d_linear)
        if not control_override:
            self.throttle = max(0.0, self.throttle + self.d_throttle)

    def ext_update(self, predict_dict, commands):
        steering_command, linear_command = commands

        # TODO when decision on diffs is in, this can simply update from values directly
        if predict_dict['update_mode'] == 'supervisor':
            self.__update_gear(False)
            self.__update_linear_movement(linear_command, False)
            self.__update_steering(steering_command, False)
        elif predict_dict['update_mode'] == 'steer':
            self.__update_gear(False)
            self.__update_linear_movement(linear_command, False)
            self.__update_steering(steering_command, True)
            self.steering = np.clip(predict_dict['d_steering'], -1.0, 1.0)
        elif predict_dict['update_mode'] == 'steer_diff':
            self.__update_gear(False)
            self.__update_linear_movement(linear_command, False)
            self.__update_steering(steering_command, True)
            self.__ext_update_steer_diff(predict_dict['d_steering'])
        else:
            self.gear = predict_dict['d_gear']
            self.__ext_update_steer_diff(predict_dict['d_steering'])
            self.__ext_update_throttle_diff(predict_dict['d_throttle'])

            self.linear_command = linear_command
            self.steering_command = steering_command

        if 'p_steering' in predict_dict:
            self.p_steering = predict_dict['p_steering']

    def __ext_update_steer_diff(self, steering_diff):
        if steering_diff < 0:
            self.steering = max(-1.0, self.steering + steering_diff)
        else:
            self.steering = min(1.0, self.steering + steering_diff)

    def __ext_update_throttle_diff(self, throttle_diff):
        if throttle_diff < 0:
            self.throttle = max(0.0, self.throttle + throttle_diff)
        else:
            self.throttle = min(1.0, self.throttle + throttle_diff)