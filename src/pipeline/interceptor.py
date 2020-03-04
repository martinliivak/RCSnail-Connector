import numpy as np
from cv2 import flip
from datetime import datetime
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

        self.expert_supervision_enabled = config.expert_supervision_enabled

    def set_renderer(self, renderer):
        self.renderer = renderer

    def new_frame(self, frame):
        self.renderer.handle_new_frame(frame)

        if frame is not None:
            self.frame = self.__convert_frame(frame)

    def __convert_frame(self, frame):
        # for some forsaken reason it needs to be flipped here.
        return flip(np.array(frame.to_image().resize(self.resolution), dtype=np.float32), 1)

    def new_telemetry(self, telemetry):
        self.renderer.handle_new_telemetry(telemetry)
        self.telemetry = telemetry

    def send_car_state(self, car):
        """Returns whether or not it should try sending state again."""
        try:
            if self.frame is None or self.telemetry is None:
                return True

            self.expert_updates = CarControlUpdates(car.d_gear, car.d_steering, car.d_throttle, car.d_braking)
            self.telemetry['conn_time'] = int(datetime.now().timestamp() * 1000)
            if self.expert_supervision_enabled:
                send_array_with_json(self.data_queue, self.frame, (self.telemetry, self.expert_updates.to_dict()))
            else:
                send_array_with_json(self.data_queue, self.frame, self.telemetry)

            return False
        except Exception as ex:
            print("Car state send exception: {}".format(ex))

    async def recv_car_controls(self):
        try:
            prediction_ready = await self.controls_queue.poll(timeout=5)

            if prediction_ready:
                predicted_updates = await self.controls_queue.recv_json()

                if predicted_updates is not None:
                    return predicted_updates
            else:
                return None
        except Exception as ex:
            print("Car control receive exception: {}".format(ex))
