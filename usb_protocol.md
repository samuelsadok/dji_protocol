# DJI Proprietary USB Protocol

The DJI Mavic Pro presents itself to a USB host as a composite device with several functions (aka interface associations):

 - RNDIS (2 interfaces, EP 2 IN, EP 1 IN, EP 8 OUT) - Rhis can be used for various purposes, such as FTP or the [UDP protocol](udp_protocol.md).
 - Mass Storage (1 interface, EP 3 IN, EP 9 OUT) - Exposes the SD card
 - **Vendor Specific** (1 interface, EP 4 IN, EP 10 OUT) - The subject of this document
 - CDC Serial (2 interfaces, EP 6 IN, EP 5 IN, EP 11 OUT) - Runs the [DJI MB Protocol](mb_protocol.md). Only packets addressed to "PC" (10) appear on this port.
 - Vendor Specific (EP 7 IN, EP 12 OUT)

This document only talks about the interface marked in bold. It is used during calibration with DJI Assistant 2 to get the live feed from the collision avoidance cameras.

For a demo [see here](recv_vid_usb.py).

## Overview

Each send/receive operation consists of one USB bulk transaction containing a header and zero or more USB bulk transaction containing the payload. This holds in both directions. The payload must not be in the same USB packet as the header.

## Header Format

| offset | meaning
|--------|--------------
| 0...1  | 0x55 0xaa (magic number)
| 2      | **unknown**
| 3      | **unknown** (not a CRC as it changes even when the rest of the packet is identical)
| 4...7  | length
| 8...11 | **unknown** (always 0 in packets from drone side)

## Payload Format

This only refers to the payload coming from the drone.

 1. Timestamp in microseconds (uint32): **This is part of the image data. That means the top left pixels of the first image are not transmitted.** (probably I have a wrong understanding here)
 2. Zero (uint32) **This is also part of the image data**
 3. Image Data arranged like this: 1st row of 1st image, 2nd row of 1st image, ... 1st row of second image, ...
    The length of this field in bytes can be calculated as `N*320*240` where N is the number of enabled video feeds.
 4. Sequence number (uint32): increments by 1 in every packet
 5. Timestamp in milliseconds
 6. Footer: this is a copy of the 50-entry integer list that the host sent to start the video feed


## How to get video

Two packets must be sent by the host to make the drone emit anything.

 1. Handshake1 Header: `55 aa 00 27 c8 00 00 00 09 e4 15 5f`
 2. Handshake1 Payload: this is a list of 50 32-bit integers, each of which is either 0 or 1. Each entry corresponds to a video feed and tells the drone to turn that feed on or off.

    | index   | video feed
    |---------|---------------
    | 0       | downward rear
    | 1       | downward front
    | 2...9   | **unknown**
    | 10      | forward left
    | 11      | forward right
    | 10...14 | **unknown**
    | 15      | forward depth image (brighter means closer)
    | 16...19 | **unknown**
    | 20      | downward rear
    | 21      | downward front
    | 22...29 | **unknown**
    | 30      | forward left
    | 31      | forward right
    | 32...39 | **unknown**
    | 40      | downward rear
    | 41      | downward front
    | 42...49 | **unknown**

 3. Handshake2 Header: `55 aa 09 3c 00 00 00 00 bc dd 33 60`

Now the drone will start transmitting video until it is rebooted.
The handshake can be sent again to change the set of video feeds that are transmitted.
