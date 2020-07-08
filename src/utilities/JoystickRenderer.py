import asyncio
import time
import pygame
from av import VideoFrame

from src.utilities import JoystickCar


class JoystickRenderer:
    def __init__(self, config, screen, car: JoystickCar):
        self.window_width = 1000   # wtf figure this diff out later config.window_width
        self.window_height = config.window_height
        self.bottom_height_diff = 15
        self.right_width_diff = 20

        self.FPS = config.FPS
        self.latest_frame = None
        self.screen = screen
        self.car = car

        self.model_override_enabled = config.model_override_enabled

        self.black = (0, 0, 0)
        self.white = (255, 255, 255)
        self.grey = (92, 92, 92)
        self.red = (255, 0, 0)
        self.green = (0, 153, 0)
        self.blue = (0, 128, 255)

        self.font = pygame.font.SysFont('Roboto', 20)

        self.controller = pygame.joystick.Joystick(0)
        self.throttle_axis = 5
        self.steering_axis = 0
        self.gear_up_button = 3
        self.gear_down_button = 2
        self.manual_control_toggle_button = 1

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
            elif event.type == pygame.JOYBUTTONDOWN:
                if self.controller.get_button(self.gear_up_button):
                    self.car.gear_up()
                elif self.controller.get_button(self.gear_down_button):
                    self.car.gear_down()
                elif self.controller.get_button(self.manual_control_toggle_button):
                    self.car.manual_override_toggle()
        asyncio.get_event_loop().stop()

    def draw(self, steering, throttle):
        # Steering gauge:
        if self.car.steering < 0:
            steer_gauge = pygame.Rect((self.car.steering + 1.0) / 2.0 * self.window_width, self.window_height - self.bottom_height_diff,
                                      -self.car.steering * self.window_width / 2, 15)
            steer_gauge_inner = pygame.Rect((steering + 1.0) / 2.0 * self.window_width, self.window_height - 5,
                                            -steering * self.window_width / 2, 5)
        else:
            steer_gauge = pygame.Rect(self.window_width / 2, self.window_height - self.bottom_height_diff,
                                      self.car.steering * self.window_width / 2, 15)
            steer_gauge_inner = pygame.Rect(self.window_width / 2, self.window_height - 5,
                                      steering * self.window_width / 2, 5)
        pygame.draw.rect(self.screen, self.grey, steer_gauge)
        pygame.draw.rect(self.screen, self.green, steer_gauge_inner)

        # Throttle gauge:
        throttle_gauge = pygame.Rect(self.window_width - 50, (1.0 - self.car.throttle) * self.window_height - self.bottom_height_diff,
                                     15, self.window_height * self.car.throttle)
        throttle_gauge_inner = pygame.Rect(self.window_width - 40, (1.0 - throttle) * self.window_height - self.bottom_height_diff,
                                           5, self.window_height * throttle)
        pygame.draw.rect(self.screen, self.grey, throttle_gauge)
        pygame.draw.rect(self.screen, self.green, throttle_gauge_inner)

        # Voltage text
        if self.car.batVoltage_mV >= 0:
            voltage_text = '{0} mV'.format(self.car.batVoltage_mV)
            self.render_text(voltage_text, x=5, y=self.window_height - 35, color=self.white)

        gear_text = 'G: {0}'.format(self.car.gear)
        self.render_text(gear_text, x=5, y=50, color=self.green)

        pred_text = 'P: {0:.3f}'.format(self.car.p_steering)
        self.render_text(pred_text, x=5, y=75, color=self.white)

        manual_override_text = 'manual override' if self.car.manual_override else ''
        self.render_text(manual_override_text, x=5, y=25, color=self.red)

    def render_text(self, text, x, y, color):
        texture = self.font.render(text, True, color)
        self.screen.blit(texture, (x, y))

    async def render(self, rcs):
        sent_steering, sent_throttle = None, None
        should_send = False
        should_resend = True

        current_time = time.time()
        frame_size = (640, 480)
        ovl = pygame.Overlay(pygame.YV12_OVERLAY, frame_size)
        ovl.set_location(pygame.Rect(0, 0, self.window_width - self.right_width_diff, self.window_height - self.bottom_height_diff))
        try:
            while True:
                pygame.event.pump()
                last_time, current_time = current_time, time.time()
                await asyncio.sleep(1 / self.FPS - (current_time - last_time))  # tick

                steering = self.controller.get_axis(self.steering_axis)
                throttle = (self.controller.get_axis(self.throttle_axis) + 1.0) / 2.0

                # should_resend is True until sending car state succeeds, at which point it's set to False.
                # If we receive new controls, should_send is set to True, otherwise it's False.
                if self.model_override_enabled:
                    if should_send or should_resend:
                        sent_steering, sent_throttle = steering, throttle

                        should_resend = self.car.update_car_state(sent_steering, sent_throttle)
                    should_send = await self.car.update_car_controls(sent_steering, sent_throttle)
                else:
                    self.car.update_car_state(steering, throttle)
                await rcs.updateControl(self.car.gear, self.car.steering, self.car.throttle, self.car.braking)

                self.screen.fill(self.black)
                if isinstance(self.latest_frame, VideoFrame):
                    image_to_ndarray = self.latest_frame.to_rgb().to_ndarray()
                    surface = pygame.surfarray.make_surface(image_to_ndarray.swapaxes(0, 1))
                    height = self.window_height - self.bottom_height_diff
                    width = height * self.latest_frame.width // self.latest_frame.height
                    x = (self.window_width - self.right_width_diff - width) // 2
                    y = 0
                    scaled_frame = pygame.transform.scale(surface, (width, height))
                    self.screen.blit(scaled_frame, (x, y))

                self.draw(steering, throttle)
                pygame.display.flip()
        except Exception as ex:
            print("Rendering exception: {}".format(ex))

    def handle_new_frame(self, frame):
        self.latest_frame = frame

    def handle_new_telemetry(self, telemetry):
        if self.car is not None:
            self.car.batVoltage_mV = telemetry["b"]
