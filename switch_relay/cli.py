import pygame

import os
import socket
import sys
from math import trunc
from time import sleep
from multiprocessing import Process, Queue

from switch_relay.mapping import BUTTONS, TRIGGERS, STICKS, DPAD_X, DPAD_Y

os.environ["SDL_VIDEODRIVER"] = "dummy"

pygame.init()
pygame.joystick.init()

switch = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def send(data):
    switch.sendall((data + "\r\n").encode())


def make_packet(command, data):
    return f"{command} {data}"


def reader_proc(queue):
    while True:
        msg = queue.get()
        send(msg)
        if msg == "DONE":
            break


def cli():
    if len(sys.argv) > 1:
        ip = sys.argv[1]
    else:
        ip = input("Enter the IP address of your Switch > ")

    pqueue = Queue()
    reader_p = Process(target=reader_proc, args=((pqueue),))
    reader_p.daemon = True
    reader_p.start()

    switch.connect((ip, 6000))
    joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]

    for joystick in joysticks:
        joystick.init()

    dpad_state = {
        "LEFT": False,
        "RIGHT": False,
        "DOWN": False,
        "UP": False,
    }

    x_names = ["LEFT", "RIGHT"]
    y_names = ["DOWN", "UP"]

    stick_state = {
        "LEFT": {
            0: "",
            1: "",
        },
        "RIGHT": {
            3: "",
            4: "",
        },
    }

    send("configure mainLoopSleepTime 0")
    send("configure buttonClickSleepTime 0")
    send("configure keySleepTime 0")
    send("configure pollRate 32000")

    while True:
        for event in pygame.event.get():
            if event.type == pygame.JOYAXISMOTION:
                if event.axis in TRIGGERS.keys():
                    if event.value > -0.9:
                        pqueue.put(make_packet("press", TRIGGERS[event.axis]))
                    else:
                        pqueue.put(make_packet("release", TRIGGERS[event.axis]))
                else:
                    stick_name = STICKS[event.axis]
                    multiplier = -32767 if event.axis not in [0, 3] else 32767

                    stick_state[stick_name][event.axis] = hex(trunc(event.value * multiplier))
                    pqueue.put(
                        make_packet(
                            "setStick",
                            "{} {} {}".format(stick_name, *stick_state[stick_name].values()),
                        )
                    )

            if event.type == pygame.JOYBUTTONDOWN:
                pqueue.put(make_packet("press", BUTTONS[event.button]))
            if event.type == pygame.JOYBUTTONUP:
                pqueue.put(make_packet("release", BUTTONS[event.button]))

            if event.type == pygame.JOYHATMOTION:
                x_val, y_val = event.value

                if x_val != 0:
                    pqueue.put(make_packet("press", "D{}".format(DPAD_X[x_val])))
                    dpad_state[DPAD_X[x_val]] = True
                else:
                    for direction in x_names:
                        if dpad_state[direction]:
                            pqueue.put(make_packet("release", f"D{direction}"))
                            dpad_state[direction] = False

                if y_val != 0:
                    pqueue.put(make_packet("press", "D{}".format(DPAD_Y[y_val])))
                    dpad_state[DPAD_Y[y_val]] = True
                else:
                    for direction in y_names:
                        if dpad_state[direction]:
                            pqueue.put(make_packet("release", f"D{direction}"))
                            dpad_state[direction] = False

        sleep(0.00001)


if __name__ == "__main__":
    cli()
