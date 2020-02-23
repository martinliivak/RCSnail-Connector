import asyncio
import time
import pygame
from av import VideoFrame

from src.utilities import JoystickCar


class JoystickRenderer:
    def __init__(self, screen, car: JoystickCar):
        self.window_width = 1000
        self.window_height = 480
        self.FPS = 30
        self.latest_frame = None
        self.screen = screen
        self.car = car

        self.black = (0, 0, 0)
        self.white = (255, 255, 255)
        self.red = (255, 0, 0)
        self.green = (0, 255, 0)
        self.blue = (0, 0, 255)

        self.font = pygame.font.SysFont('Roboto', 15)

        self.controller = pygame.joystick.Joystick(0)
        self.throttle_axis = 1
        self.steering_axis = 3

    def init_controllers(self):
        self.controller.init()

    def pygame_event_loop(self, loop, event_queue):
        while True:
            event = pygame.event.wait()
            asyncio.run_coroutine_threadsafe(event_queue.put(event), loop=loop)

    async def register_pygame_events(self, event_queue):
        while True:
            event = await event_queue.get()
            if event.type == pygame.QUIT:
                print("event", event)
                break
            elif event.type == pygame.KEYDOWN or event.type == pygame.KEYUP:
                if event.key == pygame.K_ESCAPE:
                    break
        asyncio.get_event_loop().stop()

    def draw(self):
        # Steering gauge:
        if self.car.steering < 0:
            R = pygame.Rect((self.car.steering + 1.0) / 2.0 * self.window_width,
                            self.window_height - 10,
                            -self.car.steering * self.window_width / 2,
                            10)
        else:
            R = pygame.Rect(self.window_width / 2, self.window_height - 10,
                            self.car.steering * self.window_width / 2, 10)
        pygame.draw.rect(self.screen, self.green, R)

        # Acceleration/braking gauge:
        if self.car.gear == 1:
            if self.car.throttle > 0.0:
                R = pygame.Rect(self.window_width - 20, 0,
                                10, self.window_height / 2 * self.car.throttle / 1.0)
                R = R.move(0, self.window_height / 2 - R.height)
                pygame.draw.rect(self.screen, self.green, R)
            if self.car.braking > 0.0:
                R = pygame.Rect(self.window_width - 20, self.window_height / 2,
                                10, self.window_height / 2 * self.car.braking / 1.0)
                pygame.draw.rect(self.screen, self.red, R)
        elif self.car.gear == -1:
            if self.car.throttle > 0.0:
                R = pygame.Rect(self.window_width - 20, self.window_height / 2,
                                10, self.window_height / 2 * self.car.throttle / 1.0)
                pygame.draw.rect(self.screen, self.green, R)
            if self.car.braking > 0.0:
                R = pygame.Rect(self.window_width - 20, 0,
                                10, self.window_height / 2 * self.car.braking / 1.0)
                R = R.move(0, self.window_height / 2 - R.height)
                pygame.draw.rect(self.screen, self.red, R)

        if self.car.batVoltage_mV >= 0:
            voltage_text = '{0} mV'.format(self.car.batVoltage_mV)
            self.render_text(voltage_text, x=5, y=self.window_height - 25, color=self.white)

        gear_text = 'G: {0}'.format(self.car.gear)
        self.render_text(gear_text, x=5, y=50, color=self.white)

        pred_text = 'P: {0:.3f}'.format(self.car.p_steering)
        self.render_text(pred_text, x=5, y=75, color=self.white)

    def render_text(self, text, x, y, color):
        texture = self.font.render(text, True, color)
        self.screen.blit(texture, (x, y))

    async def render(self, rcs):
        current_time = 0
        frame_size = (640, 480)
        ovl = pygame.Overlay(pygame.YV12_OVERLAY, frame_size)
        ovl.set_location(pygame.Rect(0, 0, self.window_width - 20, self.window_height - 10))
        while True:
            try:
                pygame.event.pump()
                last_time, current_time = current_time, time.time()
                await asyncio.sleep(1 / self.FPS - (current_time - last_time))  # tick

                steering = self.controller.get_axis(self.steering_axis)
                # Throttle axis is inverted so the physical layout makes more sense
                throttle = -1.0 * self.controller.get_axis(self.throttle_axis)

                await self.car.update(steering, throttle)
                await rcs.updateControl(self.car.gear, self.car.steering, self.car.throttle, self.car.braking)
                self.screen.fill(self.black)
                if isinstance(self.latest_frame, VideoFrame):
                    image_to_ndarray = self.latest_frame.to_rgb().to_ndarray()
                    surface = pygame.surfarray.make_surface(image_to_ndarray.swapaxes(0, 1))
                    height = self.window_height - 10
                    width = height * self.latest_frame.width // self.latest_frame.height
                    x = (self.window_width - 20 - width) // 2
                    y = 0
                    scaled_frame = pygame.transform.scale(surface, (width, height))
                    self.screen.blit(scaled_frame, (x, y))

                self.draw()
                pygame.display.flip()
            except Exception as ex:
                print("Rendering exception: {}".format(ex))

    def handle_new_frame(self, frame):
        self.latest_frame = frame

    def handle_new_telemetry(self, telemetry):
        if self.car is not None:
            self.car.batVoltage_mV = telemetry["b"]
