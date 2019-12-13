import numpy as np

from commons.common_zmq import send_array_with_json

from src.utilities.car_controls import CarControls, CarControlDiffs
from zmq import Socket


class Interceptor:
    def __init__(self, configuration, data_queue: Socket, controls_queue: Socket):
        self.renderer = None
        self.resolution = (configuration.recording_width, configuration.recording_height)
        self.data_queue = data_queue
        self.controls_queue = controls_queue

        self.frame = None
        self.telemetry = None
        self.expert_updates = CarControlDiffs(0, 0.0, 0.0, 0.0)
        self.car_controls = CarControls(0, 0.0, 0.0, 0.0)

        self.model_override_enabled = configuration.model_override_enabled

    def set_renderer(self, renderer):
        self.renderer = renderer

    def intercept_frame(self, frame):
        self.renderer.handle_new_frame(frame)

        if frame is not None:
            self.frame = self.__convert_frame(frame)

    def __convert_frame(self, frame):
        return np.array(frame.to_image().resize(self.resolution)).astype(np.float32)

    def intercept_telemetry(self, telemetry):
        self.telemetry = telemetry
        send_array_with_json(self.data_queue, self.frame, self.telemetry)

    async def car_update_override(self, car):
        try:
            self.expert_updates = CarControlDiffs(car.gear, car.d_steering, car.d_throttle, car.d_braking)
            self.car_controls = CarControls(car.gear, car.steering, car.throttle, car.braking)

            if self.model_override_enabled and self.frame is not None and self.telemetry is not None:
                self.__update_car_from_predictions(car)
        except Exception as ex:
            print("Override exception: {}".format(ex))

    def __update_car_from_predictions(self, car):
        try:
            predicted_updates = self.controls_queue.recv_json()

            if predicted_updates is not None:
                car.gear = predicted_updates.d_gear
                car.ext_update_steering(predicted_updates.d_steering)
                car.ext_update_linear_movement(predicted_updates.d_throttle, predicted_updates.d_braking)
        except Exception as ex:
            print("Prediction exception: {}".format(ex))
