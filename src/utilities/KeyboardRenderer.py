import asyncio
import time
import pygame
from av import VideoFrame

from src.utilities import KeyboardCar


class KeyboardRenderer:
    def __init__(self, screen, car: KeyboardCar):
        self.window_width = 960
        self.window_height = 480
        self.FPS = 30
        self.latest_frame = None
        self.screen = screen
        self.car = car

        self.black = (0, 0, 0)
        self.red = (255, 0, 0)
        self.green = (0, 255, 0)
        self.blue = (0, 0, 255)

        self.font = pygame.font.SysFont('Roboto', 12)

    def init_controllers(self):
        pass

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
                elif event.key == pygame.K_LEFT:
                    self.car.left_down = event.type == pygame.KEYDOWN
                elif event.key == pygame.K_RIGHT:
                    self.car.right_down = event.type == pygame.KEYDOWN
                elif event.key == pygame.K_UP:
                    self.car.up_down = event.type == pygame.KEYDOWN
                elif event.key == pygame.K_DOWN:
                    self.car.down_down = event.type == pygame.KEYDOWN
            # print("event", event)
        asyncio.get_event_loop().stop()

    def draw(self):
        # Steering gauge:
        if self.car.steering < 0:
            R = pygame.Rect((self.car.steering + 1.0) / 2.0 * self.window_width,
                            self.window_height - 10,
                            -self.car.steering * self.window_width / 2,
                            10)
        else:
            R = pygame.Rect(self.window_width / 2,
                            self.window_height - 10,
                            self.car.steering * self.window_width / 2,
                            10)
        pygame.draw.rect(self.screen, self.green, R)

        # Acceleration/braking gauge:
        if self.car.gear == 1:
            if self.car.throttle > 0.0:
                R = pygame.Rect(self.window_width - 20,
                                0,
                                10,
                                self.window_height / 2 * self.car.throttle / self.car.max_throttle)
                R = R.move(0, self.window_height / 2 - R.height)
                pygame.draw.rect(self.screen, self.green, R)
            if self.car.braking > 0.0:
                R = pygame.Rect(self.window_width - 20,
                                self.window_height / 2,
                                10,
                                self.window_height / 2 * self.car.braking / self.car.max_braking)
                pygame.draw.rect(self.screen, self.red, R)
        elif self.car.gear == -1:
            if self.car.throttle > 0.0:
                R = pygame.Rect(self.window_width - 20,
                                self.window_height / 2,
                                10,
                                self.window_height / 2 * self.car.throttle / self.car.max_throttle)
                pygame.draw.rect(self.screen, self.green, R)
            if self.car.braking > 0.0:
                R = pygame.Rect(self.window_width - 20,
                                0,
                                10,
                                self.window_height / 2 * self.car.braking / self.car.max_braking)
                R = R.move(0, self.window_height / 2 - R.height)
                pygame.draw.rect(self.screen, self.red, R)

        # Speed gauge:
        if self.car.virtual_speed > 0.0:
            R = pygame.Rect(self.window_width - 10,
                            0,
                            10,
                            self.window_height * self.car.virtual_speed / self.car.max_virtual_speed)
            if self.car.gear >= 0:
                R = R.move(0, self.window_height - R.height)
            pygame.draw.rect(self.screen, self.green, R)

        if self.car.batVoltage_mV >= 0:
            telemetry_text = "{0} mV".format(self.car.batVoltage_mV)
            telemetry_texture = self.font.render(telemetry_text, True, self.red)
            self.screen.blit(telemetry_texture, (3, self.window_height - 14))

    async def render(self, rcs):
        current_time = 0
        frame_size = (640, 480)
        ovl = pygame.Overlay(pygame.YV12_OVERLAY, frame_size)
        ovl.set_location(pygame.Rect(0, 0, self.window_width - 20, self.window_height - 10))
        while True:
            pygame.event.pump()
            last_time, current_time = current_time, time.time()
            await asyncio.sleep(1 / self.FPS - (current_time - last_time))  # tick
            await self.car.update((current_time - last_time) / 1.0)
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

    def handle_new_frame(self, frame):
        self.latest_frame = frame

    def handle_new_telemetry(self, telemetry):
        if self.car is not None:
            self.car.batVoltage_mV = telemetry["b"]
