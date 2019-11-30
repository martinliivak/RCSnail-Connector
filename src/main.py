import os
import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import zmq
from zmq import Context, Socket

from commons.common_zmq import send_array, initialize_synced_pubs
from commons.configuration_manager import ConfigurationManager

import pygame
import logging
from rcsnail import RCSnail

from src.pipeline.interceptor import Interceptor
from src.utilities.pygame_utils import Car, PygameRenderer


def get_training_file_name(path_to_training):
    date = datetime.datetime.today().strftime("%Y_%m_%d")
    files_from_same_date = list(filter(lambda file: date in file, os.listdir(path_to_training)))

    return date + "_test_" + str(int(len(files_from_same_date) / 2 + 1))


def main(context: Context):
    config_manager = ConfigurationManager()
    config = config_manager.config

    rcs = RCSnail()
    rcs.sign_in_with_email_and_password(os.getenv('RCS_USERNAME', ''), os.getenv('RCS_PASSWORD', ''))

    data_queue = context.socket(zmq.PUB)
    initialize_synced_pubs(context, data_queue, config.data_queue_port)

    for i in range(10):
        x = np.random.rand(3, 2)
        send_array(queue=data_queue, data=x)

    return
    loop = asyncio.get_event_loop()
    pygame_event_queue = asyncio.Queue()

    pygame.init()
    pygame.display.set_caption("RCSnail Connector")

    screen = pygame.display.set_mode((config.window_width, config.window_height))
    interceptor = Interceptor(config, data_queue)
    car = Car(config, update_override=interceptor.car_update_override)
    renderer = PygameRenderer(screen, car)
    interceptor.set_renderer(renderer)

    executor = ThreadPoolExecutor(max_workers=32)
    pygame_task = loop.run_in_executor(executor, renderer.pygame_event_loop, loop, pygame_event_queue)
    render_task = asyncio.ensure_future(renderer.render(rcs))
    event_task = asyncio.ensure_future(renderer.register_pygame_events(pygame_event_queue))
    queue_task = asyncio.ensure_future(rcs.enqueue(loop, interceptor.intercept_frame, interceptor.intercept_telemetry))

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

