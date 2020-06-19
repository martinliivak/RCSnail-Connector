import numpy as np


class JoystickCar:
    def __init__(self, configuration, send_car_state=None, recv_car_controls=None):
        """Controls are in range 0..1. Gear has discrete values from {1, 0, -1}."""
        self.steering = 0.0
        self.throttle = 0.0
        self.braking = 0.0
        self.gear = 0
        self.d_steering = 0.0
        self.d_throttle = 0.0
        self.d_braking = 0.0
        self.d_gear = 0

        self.manual_override = False
        self.p_steering = 0.0

        self.linear_command = 0.0
        self.steering_command = 0.0

        # telemetry
        self.batVoltage_mV = 0

        self.__override_enabled = configuration.model_override_enabled

        if not self.__override_enabled and (send_car_state is None or recv_car_controls is None):
            raise ValueError("Override enabled, but methods are None")

        self.__send_car_state = send_car_state
        self.__recv_car_controls = recv_car_controls

    def update_car_state(self, steering_command, linear_command):
        """Returns whether or not it should try sending state again."""
        try:
            self.__update_gear(self.__override_enabled)
            self.__update_steering(steering_command, self.__override_enabled)
            self.__update_linear_movement(linear_command, self.__override_enabled)

            if self.__override_enabled:
                return self.__send_car_state(self)
        except Exception as ex:
            print("Car update exception: {}".format(ex))

    async def update_car_controls(self, steering_command, linear_command):
        """Returns whether or not we can send a new state."""
        update_dict = await self.__recv_car_controls()

        if update_dict is None:
            return False
        else:
            self.steering = update_dict['d_steering']
            self.gear = update_dict['d_gear']
            self.throttle = update_dict['d_throttle']

            self.linear_command = linear_command
            self.steering_command = steering_command

            # TODO remove this haltuura at some point
            if 'p_steering' in update_dict:
                self.p_steering = update_dict['p_steering']

            return True

    def __update_gear(self, control_override: bool):
        if not control_override:
            self.gear = self.d_gear

    def __update_steering(self, steering_command, control_override: bool):
        diff = steering_command - self.steering_command

        if diff < 0.0:
            self.d_steering = max(-1.0, self.steering + diff)
        elif diff > 0.0:
            self.d_steering = min(1.0, self.steering + diff)

        if not control_override:
            self.steering_command = steering_command
            self.steering = self.d_steering

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

    def manual_override_toggle(self):
        self.manual_override = not self.manual_override

    def __update_linear_movement(self, linear_command, control_override: bool):
        diff = linear_command - self.linear_command

        if diff > 0.0 and self.gear is not 0:
            self.d_throttle = min(1.0, self.throttle + diff)
        elif diff < 0.0 and self.gear is not 0:
            self.d_throttle = max(0.0, self.throttle + diff)

        if not control_override:
            self.linear_command = linear_command
            self.throttle = self.d_throttle
