import numpy as np
from zmq.asyncio import Socket

from commons.car_controls import CarControlUpdates, CarControls
from commons.common_zmq import send_array_with_json


class Interceptor:
    def __init__(self, config, data_queue: Socket, controls_queue: Socket):
        self.renderer = None
        self.resolution = (config.frame_width, config.frame_height)
        self.data_queue = data_queue
        self.controls_queue = controls_queue

        self.frame = None
        self.telemetry = None
        self.expert_updates = None
        self.car_controls = CarControls(0, 0.0, 0.0, 0.0)

        self.expert_supervision_enabled = config.expert_supervision_enabled

    def set_renderer(self, renderer):
        self.renderer = renderer

    def new_frame(self, frame):
        self.renderer.handle_new_frame(frame)

        if frame is not None:
            self.frame = self.__convert_frame(frame)

    def __convert_frame(self, frame):
        return np.array(frame.to_image().resize(self.resolution)).astype(np.float32)

    def new_telemetry(self, telemetry):
        self.renderer.handle_new_telemetry(telemetry)
        self.telemetry = telemetry

    async def car_update_override(self, car, commands):
        try:
            if self.frame is None or self.telemetry is None:
                return

            self.expert_updates = CarControlUpdates(car.gear, car.d_steering, car.d_throttle, car.d_braking, True)

            if self.expert_supervision_enabled:
                send_array_with_json(self.data_queue, self.frame, (self.telemetry, self.expert_updates.to_dict()))
            else:
                send_array_with_json(self.data_queue, self.frame, self.telemetry)

            await self.__update_car_from_predictions(car, commands)
        except Exception as ex:
            print("Car override exception: {}".format(ex))

    async def __update_car_from_predictions(self, car, commands):
        try:
            prediction_ready = await self.controls_queue.poll(timeout=20)

            if prediction_ready:
                predicted_updates = await self.controls_queue.recv_json()

                if predicted_updates is not None:
                    #print("updates: {}".format(predicted_updates))
                    car.ext_update(predicted_updates, commands)
        except Exception as ex:
            print("Prediction exception: {}".format(ex))
