#!/bin/python
#
# This script receives and displays the video feed from the forward and downward
# facing collision avoidance cameras.
# The drone must be connected directly via USB.
# Attempting to run this script with the remote control results in a timeout error.
#
# For documentation of the protocol see usb_protocol.md.
#

import usb.core
import usb.util
import time
import struct
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import threading

while True:
    print("Looking for device (make sure it's plugged in via USB)...")
    device = usb.core.find(idVendor=0x2CA3)
    if not device is None:
        break
    time.sleep(1)

print("found device")

cfg = device.get_active_configuration()

interfaces = [i for i in cfg.interfaces() if i.bInterfaceClass == 255 and i.bInterfaceSubClass == 67]
vendor_interfaces = [i for i in cfg.interfaces() if i.bInterfaceClass == 255]
if len(interfaces) == 0:
    print("vendor interface subclass 67 not found - trying any vendor specific interface")
    interfaces = vendor_interfaces

if len(interfaces) == 0:
    print("no compatible interface found")

print("vendor-specific interfaces: {}".format(vendor_interfaces))
print("compatible interfaces: {}".format(interfaces))

ep_out = usb.util.find_descriptor(interfaces[0], custom_match = lambda e: e.bEndpointAddress & 0x80 == 0x00)
ep_in = usb.util.find_descriptor(interfaces[0], custom_match = lambda e: e.bEndpointAddress & 0x80 == 0x80)

print("using endpoints 0x{:02X} and 0x{:02X}".format(ep_out.bEndpointAddress, ep_in.bEndpointAddress))

# See usb_protocol.md for details
cameras = [
    1, 1, 0, 0, 0, 0, 0, 0, 0, 0,
    1, 1, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
]

handshake1 = [0x55, 0xaa, 0x00, 0x27, 0xc8, 0x00, 0x00, 0x00, 0x09, 0xe4, 0x15, 0x5f] + list(struct.pack("<" + "I" * len(cameras), *cameras))
print(len(handshake1))
handshake2 = [
    0x55, 0xaa, 0x09, 0x3c, 0x00, 0x00, 0x00, 0x00, 0xbc, 0xdd, 0x33, 0x60
]

print(ep_out.write(handshake1[:12]))
print(ep_out.write(handshake1[12:]))
print(ep_out.write(handshake2))

receiving = [True]
last_frame = [None]

def receive():
    global receiving

    remaining_length = 0
    packet = None

    while receiving[0]:
        part = ep_in.read(400000, 1000)

        if packet is None:
            if list(part[0:2]) != [0x55,0xaa]:
                print("bad magic number")
                continue
            if len(part) < 12:
                print("packet too short")
                continue

            remaining_length = struct.unpack('<I', part[4:8])[0] + 12
            packet = []

        if not packet is None:
            packet += part
            remaining_length -= len(part)

            if remaining_length < 0:
                print("packet too long")
                remaining_length = 0
                packet = None
            elif remaining_length == 0:
                rows = int((len(packet)-208-12)/320)
                print("received frame with {} rows".format(rows))
                last_frame[0] = np.array(list(packet[12:-208])).reshape(rows,320)
                packet = None

threading.Thread(target = receive).start()

try:
    while last_frame[0] is None:
        time.sleep(0.1)

    fig = plt.figure()
    im = plt.imshow(last_frame[0], cmap='gray')

    def animate(i):
        a = im.get_array()
        im.set_array(last_frame[0])
        return [im]
    
    anim = matplotlib.animation.FuncAnimation(fig, animate, interval=50, blit=True)
    plt.show()

finally:
    receiving[0] = False
