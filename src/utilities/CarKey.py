
class CarKey:
    def __init__(self, configuration, update_override=None):
        # units in percentage range 0..1
        self.steering = 0.0
        self.throttle = 0.0
        self.braking = 0.0
        self.gear = 0
        self.d_steering = 0.0
        self.d_throttle = 0.0
        self.d_braking = 0.0

        self.max_steering = 1.0
        self.max_throttle = 1.0
        self.max_braking = 1.0
        self.braking_k = 5.0            # coefficient used for virtual speed braking calc
        self.min_deceleration = 5       # speed reduction when nothing is pressed
        # units of change over one second:
        self.steering_speed = 5.0
        self.steering_dissipation_speed = 3.0
        self.acceleration_speed = 5.0
        self.dissipation_speed = 2.0
        self.braking_speed = 5.0
        # virtual speed
        self.virtual_speed = 0.0
        self.max_virtual_speed = 5.0
        # key states
        self.left_down = False
        self.right_down = False
        self.up_down = False
        self.down_down = False

        # telemetry
        self.batVoltage_mV = 0

        self.__override_enabled = update_override is not None and configuration.model_override_enabled
        self.__update_override = update_override

    async def update(self, dt):
        try:
            self.__update_steering(dt)
            self.__update_linear_movement(dt, self.__override_enabled)
            self.__update_direction(self.__override_enabled)

            if self.__override_enabled:
                await self.__update_override(self, dt)

            # calculate virtual speed
            if self.up_down == self.down_down:
                # nothing or both pressed
                self.virtual_speed = max(0.0, min(self.max_virtual_speed,
                                                  self.virtual_speed - dt * self.min_deceleration))
            else:
                self.virtual_speed = max(0.0, min(self.max_virtual_speed,
                                                  self.virtual_speed + dt * (self.throttle - self.braking_k * self.braking)))
        except Exception as ex:
            print("Car update exception: {}".format(ex))

    def __update_steering(self, dt):
        # calculate steering
        if (not self.left_down) and (not self.right_down):
            self.__passive_steering(dt)
        elif self.left_down and not self.right_down:
            self.d_steering = -dt * self.steering_speed
            if not self.__override_enabled:
                self.steering = max(-1.0, self.steering + self.d_steering)
        elif not self.left_down and self.right_down:
            self.d_steering = dt * self.steering_speed
            if not self.__override_enabled:
                self.steering = min(1.0, self.steering + self.d_steering)

    def __passive_steering(self, dt):
        if self.steering > 0.01:
            self.d_steering = -dt * self.steering_dissipation_speed
            if not self.__override_enabled:
                self.steering = max(0.0, self.steering + self.d_steering)
        elif self.steering < -0.01:
            self.d_steering = dt * self.steering_dissipation_speed
            if not self.__override_enabled:
                self.steering = min(0.0, self.steering + self.d_steering)
        else:
            self.d_steering = 0.0

    def __update_linear_movement(self, dt, is_override: bool):
        # calculating gear, throttle, braking
        if self.up_down and not self.down_down:
            if self.gear == 0:
                self.__takeoff(dt, 1, is_override)
            elif self.gear == 1:  # drive accelerating
                self.__accelerate(dt, is_override)
            elif self.gear == -1:  # reverse braking
                self.__decelerate(dt, is_override)
        elif not self.up_down and self.down_down:
            if self.gear == 0:
                self.__takeoff(dt, -1, is_override)
            elif self.gear == 1:  # drive braking
                self.__decelerate(dt, is_override)
            elif self.gear == -1:  # reverse accelerating
                self.__accelerate(dt, is_override)
        else:  # both down or both up
            self.d_throttle = -dt * self.dissipation_speed
            self.d_braking = -dt * self.dissipation_speed
            if not self.__override_enabled:
                self.throttle = max(0.0, self.throttle + self.d_throttle)
                self.braking = max(0.0, self.braking + self.d_braking)

    def __takeoff(self, dt, gear, is_override: bool):
        self.d_throttle = dt * self.acceleration_speed
        self.d_braking = max(-self.braking, -dt * self.braking_speed)
        if not is_override:
            self.gear = gear
            self.throttle = 0.0
            self.braking = max(0.0, self.braking + self.d_braking)

    def __decelerate(self, dt, is_override: bool):
        self.d_throttle = 0.0
        self.d_braking = dt * self.braking_speed
        if not is_override:
            self.throttle = 0.0
            self.braking = min(self.max_braking, self.braking + self.d_braking)

    def __accelerate(self, dt, is_override: bool):
        self.d_throttle = dt * self.acceleration_speed
        self.d_braking = max(-self.braking, -dt * self.braking_speed)
        if not is_override:
            self.throttle = min(self.max_throttle, self.throttle + self.d_throttle)
            self.braking = max(0.0, self.braking + self.d_braking)

    def __update_direction(self, is_override: bool):
        # conditions to change the direction
        if not self.up_down and not self.down_down and self.virtual_speed < 0.01 and not is_override:
            self.gear = 0

    def ext_update_linear_movement(self, predict_dict, dt):
        if predict_dict['supervisor']:
            self.__update_linear_movement(dt, False)
            self.__update_direction(False)
        else:
            self.gear = predict_dict['d_gear']
            self.throttle = min(self.max_throttle, self.throttle + predict_dict['d_throttle'])
            self.braking = min(self.max_braking, self.braking + predict_dict['d_braking'])

    def ext_update_steering(self, d_steering):
        if d_steering < 0:
            self.steering = max(-1.0, self.steering + d_steering)
        else:
            self.steering = min(1.0, self.steering + d_steering)
