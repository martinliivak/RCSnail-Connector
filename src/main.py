import os
import datetime
import asyncio
import pygame
import logging
import zmq
from zmq.asyncio import Context

from rcsnail import RCSnail

from commons.common_zmq import initialize_publisher, initialize_subscriber
from commons.configuration_manager import ConfigurationManager

from src.pipeline.interceptor import Interceptor
from src.utilities.JoystickCar2 import JoystickCar2
from src.utilities.KeyboardCar import KeyboardCar
from src.utilities.JoystickRenderer2 import JoystickRenderer2
from src.utilities.KeyboardRenderer import KeyboardRenderer


def get_training_file_name(path_to_training):
    date = datetime.datetime.today().strftime("%Y_%m_%d")
    files_from_same_date = list(filter(lambda file: date in file, os.listdir(path_to_training)))

    return date + "_test_" + str(int(len(files_from_same_date) / 2 + 1))


def main(context: Context):
    config_manager = ConfigurationManager()
    config = config_manager.config
    rcs = RCSnail()
    rcs.sign_in_with_email_and_password(os.getenv('RCS_USERNAME', ''), os.getenv('RCS_PASSWORD', ''))

    loop = asyncio.get_event_loop()

    data_queue = context.socket(zmq.PUB)
    loop.run_until_complete(initialize_publisher(data_queue, config.data_queue_port))

    controls_queue = context.socket(zmq.SUB)
    loop.run_until_complete(initialize_subscriber(controls_queue, config.controls_queue_port))

    pygame_event_queue = asyncio.Queue()
    pygame.init()
    pygame.display.set_caption("RCSnail Connector")

    screen = pygame.display.set_mode((config.window_width, config.window_height))
    interceptor = Interceptor(config, data_queue, controls_queue)
    car = JoystickCar2(config, send_car_state=interceptor.send_car_state, recv_car_controls=interceptor.recv_car_controls)
    renderer = JoystickRenderer2(config, screen, car)
    renderer.init_controllers()
    interceptor.set_renderer(renderer)

    pygame_task = loop.run_in_executor(None, renderer.pygame_event_loop, loop, pygame_event_queue)
    render_task = asyncio.ensure_future(renderer.render(rcs))
    event_task = asyncio.ensure_future(renderer.register_pygame_events(pygame_event_queue))
    queue_task = asyncio.ensure_future(rcs.enqueue(loop, interceptor.new_frame, interceptor.new_telemetry, track=config.track))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Closing due to keyboard interrupt.")
    finally:
        queue_task.cancel()
        pygame_task.cancel()
        render_task.cancel()
        event_task.cancel()
        pygame.quit()
        asyncio.ensure_future(rcs.close_client_session())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

    context = Context()
    main(context)
    context.destroy()
