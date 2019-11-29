import numpy as np
from multiprocessing import Event

from src.utilities.car_controls import CarControls, CarControlDiffs
from src.utilities.message import Message
from zmq import Socket


class Interceptor:
    def __init__(self, configuration, data_queue: Socket):
        self.kill_event = Event()
        self.renderer = None
        self.resolution = (configuration.recording_width, configuration.recording_height)
        self.publisher = data_queue

        self.frame = None
        self.telemetry = None
        self.expert_updates = CarControlDiffs(0, 0.0, 0.0, 0.0)
        self.car_controls = CarControls(0, 0.0, 0.0, 0.0)

        self.runtime_training_enabled = configuration.runtime_training_enabled
        self.model_override_enabled = configuration.model_override_enabled

        if self.runtime_training_enabled:
            self.aggregation_count = 0

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
            self.__send_data_to_model()
            predicted_updates = self.prediction_queue.get(block=True, timeout=1)

            if predicted_updates is not None:
                car.gear = predicted_updates.d_gear
                car.ext_update_steering(predicted_updates.d_steering)
                car.ext_update_linear_movement(predicted_updates.d_throttle, predicted_updates.d_braking)
        except Exception as ex:
            print("Prediction exception: {}".format(ex))

    def __send_data_to_model(self):
        if not self.kill_event.is_set():
            self.model_queue.put(Message("predicting", (self.frame, self.telemetry)))
