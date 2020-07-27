#!/bin/python
#
# This is a minimal proof of concept to receive video feed from a Mavic drone.
#
# The video is recorded into a file "outvid.h264" and also forwarded to
# UDP localhost:5004 for live display.
#
# Usage:
#   1. Start your drone in WiFi mode and connect your computer to the drone's WiFi.
#   2. Run this script (quit with Ctrl+C).
#      If it works you should see a debug message for every received frame.
#   3. For live display run `ffplay -sync ext -an -fast -framedrop -probesize 32 -window_title "Drone Cam" -an udp://localhost:5004`
#   4. Some players are able to directly open the recorded raw file.
#      If yours is not, convert it with `ffmpeg -i outvid.h264 outvid.mp4`.
#
# Known issues:
#   - Sometimes the handshake doesn't work and the drone doesn't respond. This
#     seems to be especially the case when you try to run the script multiple
#     times without restarting the drone. That's the drawback of using hardcoded
#     packets.
#   - If the video stream cuts out (e.g. because of unreliable network) there is
#     no handling to restart the stream.
# 

import socket
import struct

UDP_REMOTE_IP = "192.168.2.1" # Use this if the drone is connected via WiFi
#UDP_REMOTE_IP = "192.168.42.2" # Use this if the drone is connected directly via USB
UDP_REMOTE_PORT = 9003
UDP_LOCAL_PORT = 12346

# Sending this packet kicks off the video feed.
handshake_dump = bytes([
    0x30, 0x80, 0x3a, 0xdd, 0x00, 0x00, 0x00, 0x57, 0xd0, 0xe9, 0x64, 0x00, 0x64, 0x00, 0xc0, 0x05,
    0x14, 0x00, 0x00, 0x0a, 0x00, 0x64, 0x00, 0x64, 0x00, 0xc0, 0x05, 0x14, 0x00, 0x00, 0x64, 0x00,
    0x14, 0x00, 0x64, 0x00, 0xc0, 0x05, 0x14, 0x00, 0x00, 0x64, 0x00, 0x01, 0x01, 0x04, 0x0a, 0x02,
])

# This one is sent at 30Hz (same as the drone's frame rate) and apparently acknowledges the last packet of each frame.
# If you don't send this the drone will stop the video feed after ~0.5s.
keepalive4_dump = bytes([
    0x1e, 0x80, 0x3a, 0xdd, 0x00, 0x00, 0x04, 0x7d, 0x08, 0xea, 0x08, 0xea, 0x00, 0x00, 0xd0, 0xe9,
    0xd0, 0xe9, 0x00, 0x00, 0xd0, 0xe9, 0xd8, 0xe9, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
])

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP
sock.bind(("", UDP_LOCAL_PORT))

playback_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def bytes_to_hex(byte_array):
    return " ".join(["0x{:02x}".format(b) for b in byte_array])

with open("outvid.h264", "wb") as fp:
    sock.sendto(handshake_dump, (UDP_REMOTE_IP, UDP_REMOTE_PORT))
    print("sent handshake")

    seed_seq_no = (handshake_dump[0x08] | (handshake_dump[0x09] << 8))
    recv_window_start = seed_seq_no # up to (including) this sequence number all packets have been received
    recv_window_end = seed_seq_no # up to (including) this sequence number some packets have been received

    while True:
        data, addr = sock.recvfrom(2048)
        expected_length = struct.unpack("<H", data[0:2])[0] & 0x7fff
        if expected_length != len(data):
            print("unexpected packet length")
            continue

        seq_no = data[0x04] | (data[0x05] << 8)
        assert((seq_no & 0x7) == 0)
        packet_type = data[0x06]

        if packet_type == 0: # handshake response
            print("got handshake response")
        elif packet_type == 1: # data packet
            print("got data packet of size " + str(len(data)) + " B")
        elif packet_type == 2: # video packet
            frame_num = int(data[0x10])
            n_parts = int(data[0x11] & 0x7f)
            part_num = int((data[0x11] >> 7) + ((data[0x12] & 0x1f) << 1))

            print("got video frame " + str(frame_num) + " part " + str(part_num) + "/" + str(n_parts))
            print("  with header: " + bytes_to_hex(data[0:20]))

            recv_window_start = seq_no
            recv_window_end = seq_no

            # If this is the last packet of a frame send acknowledgement
            if part_num == (n_parts - 1):
                keepalive = list(keepalive4_dump)
                keepalive[0x08] = recv_window_start & 0xff # copy sequence numbers to acknowledgement packet
                keepalive[0x09] = recv_window_start >> 8
                keepalive[0x0a] = recv_window_end & 0xff
                keepalive[0x0b] = recv_window_end >> 8
                sock.sendto(bytes(keepalive), (UDP_REMOTE_IP, UDP_REMOTE_PORT))
                print("  sent ack:    " + bytes_to_hex(keepalive))
            
            fp.write(data[20:])
            playback_sock.sendto(bytes(data[20:]), ("127.0.0.1", 5004))
        else:
            print("*** unknown packet type {} ***".format(packet_type))
            exit(1)
