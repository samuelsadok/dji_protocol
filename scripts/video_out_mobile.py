"""
Outputs a video stream from a DJI device that is in "mobile/MFI" mode.

Before using this script, the DJI device must be spoofed into thinking it is
connected to an iPhone (see `emulate_iphone.py`).

Tested with DJI Mavic Pro (1st Gen) and DJI Goggles N3. Please let me know if
it works with other devices too.

For documentation about the protocol, see usb_mobile_protocol.md.

Usage:

Test if you get packets:
  python3 -u video_out_mobile.py > /dev/null
Stats will be printed on stderr.

Pipe into a video player:
  python3 -u video_out_mobile.py | ffplay -vf "setpts=PTS-STARTPTS" -fflags nobuffer -flags low_delay -f h264 -i -
The ffplay flags are chosen to minimize latency and play frames as quickly as they come in.
"""

from dataclasses import dataclass
import threading
import time
from typing import Dict
import usb.core
import usb.util
import sys

DJI_VID = 0x2ca3

VIDEO_STREAM_ID = 0x574A # verified on Mavic Pro (1st Gen) and Goggles N3
LOGICLINK_MAGIC = (0x55, 0xCC)

MAGIC_PACKETS = [
    [
        # USB encapsulation header
        0x55, 0xcc, 0x49, 0x57, 0x2d, 0x00, 0x00, 0x00,
        # DUML header
        0x55, 0x2d, 0x04, 0xf2, 0x02, 0x28, 0xf3, 0xfe, 0x40, 0x00, 0x99,
        # DUML payload
        0x02, 0x02, 0x00, 0x00, 0xd5, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x13, 0x00, 0x0d, 0x00, 0x63, 0x61, 0x6d, 0x63, 0x61, 0x70, 0x5f, 0x63, 0x6f, 0x6d, 0x6d, 0x6f, 0x6e, 0x00, 0x00, 0x00, 0x00, 0xd0, 0x93,
        # DUML CRC16
        0x92, 0x3a
    ],
    [
        # USB encapsulation header
        0x55, 0xcc, 0x49, 0x57, 0x1b, 0x00, 0x00, 0x00,
        # DUML header
        0x55, 0x1b, 0x04, 0x75, 0x02, 0x3c, 0xf4, 0xfe, 0x40, 0x00, 0x88,
        # DUML payload
        0x17, 0x00, 0x00, 0x23, 0x00, 0x41, 0x50, 0x50, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x58, 0xa6,
        # DUML CRC16
        0x34, 0x18
    ]
]

start_time = time.monotonic()

# Name "logic link" derived from the interface string "com.dji.logiclink"
@dataclass
class LogicLinkPacket:
    port: int
    payload: bytes

@dataclass
class StreamStats:
    packet_count: int = 0
    total_bytes: int = 0

class LogicLinkDecoder:
    def __init__(self):
        self.buffer = bytearray()
        self.byte_pos = 0 # corresponding to the start of the buffer
        self.packet_num = 0 # corresponding to the start of the buffer
        self.stream_stats: Dict[int, StreamStats] = {}

    def put(self, data: bytes):
        self.buffer.extend(data)

        while len(self.buffer) >= 8:
            assert (data[0], data[1]) == LOGICLINK_MAGIC, f"Bad magic after {self.byte_pos} bytes: {self.buffer[0]:02X} {self.buffer[1]:02X}"
            assert self.buffer[6] == 0 and self.buffer[7] == 0, f"Non-zero unknown field after {self.byte_pos} bytes: {self.buffer[6]:02X} {self.buffer[7]:02X}"
            length = self.buffer[4] | (self.buffer[5] << 8)
            if len(self.buffer) < 8 + length:
                break # packet not complete yet

            packet = LogicLinkPacket(
                port=self.buffer[2] | (self.buffer[3] << 8),
                payload=self.buffer[8:8 + length]
            )

            stream_stats = self.stream_stats.setdefault(packet.port, StreamStats())
            stream_stats.packet_count += 1
            stream_stats.total_bytes += len(packet.payload)
            self.packet_num += 1

            yield packet

            if packet.port == VIDEO_STREAM_ID:
                sys.stdout.buffer.write(packet.payload)

            self.buffer = self.buffer[8 + length:]
            self.byte_pos += 8 + length

def decode_logiclink_packet(data: bytes, packet_num: int):
    assert data[0] == LOGICLINK_MAGIC and data[1] == LOGICLINK_MAGIC, (
        f"Bad magic at packet {packet_num}: {data[0]:02X} {data[1]:02X}."
        "This can happen after abnormal termination of the connection. "
        "Restarting the script once or twice usually fixes this."
    )
    assert data[6] == 0 and data[7] == 0, f"Non-zero tail at packet {packet_num}: {data[6]:02X} {data[7]:02X}"
    length = data[4] | (data[5] << 8) # length without header

    assert length <= (len(data) - 8), f"Payload overruns packet {packet_num}: expected {length} bytes, got {len(data) - 8} bytes."
    assert length >= (len(data) - 8), f"Packet {packet_num} exceeds payload: expected {length} bytes, got {len(data) - 8} bytes. Trailing bytes: {data[8+length:8+length+10].hex()}"

    return LogicLinkPacket(
        port=data[2] | (data[3] << 8),
        payload=data[8:]
    )

def send_magic_packets(out_ep):
    packets = MAGIC_PACKETS
    sys.stderr.write(f"Sending {len(packets)} magic packets...\n")
    for packet in packets:
        out_ep.write(packet)
    sys.stderr.write("Magic packets sent\n")

def print_stats(all_stats, longest_transfer: int):
    sys.stderr.write(f"[{time.monotonic() - start_time:.2f}s] stats:\n")
    sys.stderr.write(f"  Longest transfer: {longest_transfer} bytes\n")
    for port_num, stats in sorted(all_stats.items()):
        port_lo = port_num & 0xFF
        port_hi = (port_num >> 8) & 0xFF
        sys.stderr.write(f"  Port {port_num} ({port_lo:02X} {port_hi:02X}): {stats.packet_count} packets, {stats.total_bytes} bytes\n")

def send_loop(out_ep: usb.core.Endpoint, interval: float = 5.0):
    while True:
        send_magic_packets(out_ep)
        time.sleep(interval)

def receive_loop(in_ep: usb.core.Endpoint):
    last_print_time = 0
    longest_transfer = 0

    decoder = LogicLinkDecoder()

    while True:
        raw_packet = bytes(in_ep.read(100000, timeout=10000)) # usb.core.USBError: [Errno 84] Overflow?

        longest_transfer = max(longest_transfer, len(raw_packet))

        packets = list(decoder.put(raw_packet))

        now = time.monotonic()
        if now - last_print_time > 0.1:
            print_stats(decoder.stream_stats, longest_transfer)
            last_print_time = now

def main():
    if sys.stdout.isatty():
        sys.stderr.write("Warning: stdout is a TTY. This script outputs binary data and is intended to be piped into a file or video player.\n")
        sys.exit(1)

    device = usb.core.find(idVendor=DJI_VID)
    if device is None:
        sys.exit("DJI device not found")

    cfg = device.get_active_configuration()

    sys.stderr.write(f"Found device\n")
    sys.stderr.write(f"Configuration: {cfg}\n")

    intf = usb.util.find_descriptor(
        cfg,
        custom_match=lambda i: i.bInterfaceNumber == 1 and i.bAlternateSetting == 1
    )
    if intf is None:
        sys.exit("Interface 1 alt 1 not found in configuration")

    out_ep = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
    )
    in_ep = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
    )

    sys.stderr.write(f"Running on interface {intf.bInterfaceNumber}, IN endpoint {in_ep.bEndpointAddress:02X}, OUT endpoint {out_ep.bEndpointAddress:02X}\n")

    usb.util.claim_interface(device, intf.bInterfaceNumber)
    device.set_interface_altsetting(intf.bInterfaceNumber, intf.bAlternateSetting)

    interface_string = usb.util.get_string(device, intf.iInterface)
    sys.stderr.write(f"Interface string: {interface_string}\n")

    if interface_string == "com.dji.common":
        sys.stderr.write("Assuming DJI Mavic Pro or similar. No magic packets required.\n")
    elif interface_string == "com.dji.logiclink":
        sys.stderr.write("Assuming DJI Goggles N3 or similar. Starting magic packet send loop.\n")
        send_thread = threading.Thread(target=send_loop, args=(out_ep,), daemon=True)
        send_thread.start()
    else:
        sys.stderr.write(f"Unknown interface string: {interface_string}.\n")
        sys.exit(1)

    receive_loop(in_ep)

if __name__ == "__main__":
    main()
