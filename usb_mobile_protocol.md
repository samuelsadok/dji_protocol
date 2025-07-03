# DJI USB mobile protocol

## Table of Contents

- [Overview](#overview)
- [Connection](#connection)
- [USB descriptors](#usb-descriptors)
- [Packet Format](#packet-format)
- [Streams / Port Numbers](#streams--port-numbers)
- [Starting the video stream (newer devices only)](#starting-the-video-stream-newer-devices-only)
- [Spoofing Role Switch](#spoofing-role-switch)
- [Demo](#demo)
- [Notes on Reverse Engineering](#notes-on-reverse-engineering)

## Overview

This page attempts to describe the USB protocol used by DJI devices when connected to an Apple mobile device (iPhone/iPad).
(based on reverse engineering - no affiliation with DJI.)

This protocol is used by the "DJI GO 4", "DJI Fly" and similar apps to show a live view of the Aircraft's video stream and send certain commands and control inputs to the Aircraft.

Notably, this is different from a [USB-to-PC connection](usb_protocol.md) (the DJI device presents completely different endpoints). As for Android smartphones, I don't know at the time of writing.

Only aspects which are specific to the USB-to-smartphone connection are described here.
The piggybacked DUML protocol which is found in many places throughout the DJI ecosystem is described [elsewhere](mb_protocol.md).

The claims in this document have been verified with these devices:

Device                                 | Release Year | Verified
---------------------------------------|--------------|-----------------------
DJI Goggles N3                         | 2024         | ✅
DJI O4 Air Unit                        | 2025         | N/A [1]
DJI Mavic Pro (1st gen) Remote Control | 2016         | ✅
DJI Mavic Pro (1st gen) (Aircraft)     | 2016         | N/A [1]

[1] This protocol appears to be only available on DJI devices that were actually meant to connect to a smartphone (goggles / remote controls). The Aircraft / Air Unit I tried does not support the Apple MFI handshake.

## Connection

The connection process appears to be a standard Apple MFI handshake, the details of which are not openly documented.

1. The DJI device starts in the USB Host role and the iOS device starts in USB Peripheral role
2. The DJI device starts connecting to the iOS device like any normal USB host would (set address, get device descriptor, get configuration descriptor)
3. The DJI device detects that it's an iOS device solely based on the iOS device's VID:PID (in my case `05AC:12A8`, iPhone, or `05AC:12AB`, iPad). (see also [Spoofing Role Switch](#spoofing-role-switch))
4. The DJI device sends a vendor device request with `{bmRequestType=0x40 (Host-to-device, Vendor, Device), bRequest=0x51, wValue=0x0000, wIndex=0x0000}`, which is ACK'd by the iOS device
5. Both devices switch roles. I don't have the details what exactly happens on the D+/D- lines during this line switch (e.g. if they are pulled low to indicate a reset).
6. The iOS device starts connecting to the DJI device like any normal USB host would
7. The iOS device continues with some Apple MFI-specific exchanges on Interface 0, which are presumably to authenticate that the DJI device is a genuine MFI device. However this is not mandatory to use the DJI-specific endpoints. This happens even if the iOS device screen is locked.
8. The iOS device puts Interface 1 into alternate setting 1 (see descriptors below).
9. The DJI device and the iOS device (probably the driver component that comes with the app) start sending DUML packets in both directions. This happens even if the screen is locked and the app is closed (and was killed).
10. If the Aircraft (or Air Unit) is connected, the DJI device starts streaming video to the iOS device. On some DJI devices this happens without request, and on others it happens as a result of commands from the iOS device.

## USB descriptors

The DJI device presents itself with VID:PID 2CA3:1002. Interface 1 alternate setting 1 is where the real communication happens (video stream and DUML payload). The endpoint numbers can be different between DJI devices.

Below is an overview of the actual descriptors.

- **DJI Mavic Pro (1st gen) RC**

  [Full lsusb dump](lsusb/lsusb_dji-m1p-rc_mfi.txt)

  - Device Descriptor
    ```
    12, 01, 00, 02, 00, 00, 00, 40, A3, 2C, 02, 10, 10, 03, 01, 02, 03, 01
    ```

  - Configuration Descriptor
    ```
    09, 02, 43, 00, 02, 01, 04, 80, 00,   # Configuration
    03, 09, 03,                           #   OTG info
      09, 04, 00, 00, 02, FF, F0, 00, 05, #   Interface 0 "iAP Interface"
        07, 05, 81, 02, 00, 02, 00,       #     endpoint IN 1
        07, 05, 08, 02, 00, 02, 00,       #     endpoint OUT 8
      09, 04, 01, 00, 00, FF, F0, 01, 06, #   Interface 1 alt 0 "com.dji.common"
      09, 04, 01, 01, 02, FF, F0, 01, 06, #   Interface 1 alt 1 "com.dji.common"
        07, 05, 82, 02, 00, 02, 00,       #     endpoint IN 2
        07, 05, 09, 02, 00, 02, 00        #     endpoint OUT 9
    ```

- **DJI Goggles N3**

  [Full lsusb dump](lsusb/lsusb_dji-goggles-n3_mfi.txt)

  - Device Descriptor:
    ```
    12, 01, 10, 02, 00, 00, 00, 40, A3, 2C, 02, 10, 04, 05, 01, 02, 03, 01
    ```

  - Configuration Descriptor:
    ```
    09, 02, 40, 00, 02, 01, 04, 80, 01,   # Configuration
      09, 04, 00, 00, 02, FF, F0, 00, 05, #   Interface 0 "iAP Interface"
        07, 05, 81, 02, 00, 02, 00,       #     endpoint IN 1
        07, 05, 01, 02, 00, 02, 00,       #     endpoint OUT 1
      09, 04, 01, 00, 00, FF, F0, 01, 06, #   Interface 1 alt 0 "com.dji.logiclink"
      09, 04, 01, 01, 02, FF, F0, 01, 06, #   Interface 1 alt 1 "com.dji.logiclink"
        07, 05, 82, 02, 00, 02, 00,       #     endpoint IN 2
        07, 05, 02, 02, 00, 02, 00        #     endpoint OUT 2
    ```

## Packet Format

On newer DJI devices (e.g. DJI Goggles N3), transfers in both directions (IN endpoint and OUT endpoint) follow the same structure. They consist of an encapsulation header (with a port number) and the payload.
On older DJI devices (e.g. DJI Mavic Pro 1st gen), only the IN data is encapsulated.

Encapsulation format:

offset  | meaning  
--------|------------------------------
0...1   | magic number, always `0x55 0xCC`
2...3   | port number (see below)
4...5   | payload length (excl header)
6...7   | unknown, always observed to be `0x00 0x00`
8...end | payload

One USB transfer can contain multiple encapsulation packets.

## Streams / Port Numbers

* **DJI Goggles N3**

  Port                | Direction                      | Payload
  --------------------|--------------------------------|-----------------------------------
  22346 (`0x4A 0x57`) | IN (DJI device => iOS device)  | Raw video stream. Needs to be started with start commands (see below). Can be piped into ffplay.
  30000 (`0x30 0x75`) | IN (DJI device => iOS device)  | DUML packets (`0x55 len 0x04 ...`)
  22345 (`0x49 0x57`) | OUT (iOS device => DJI device) | DUML packets (`0x55 len 0x04 ...`)

* **DJI Mavic Pro (1st gen) Remote Control**
  Port                | Direction                      | Payload
  --------------------|--------------------------------|-----------------------------------
  22346 (`0x4A 0x57`) | IN (DJI device => iOS device)  | Raw video stream. Starts automatically. Can be piped into ffplay.
  22345 (`0x49 0x57`) | IN (DJI device => iOS device)  | DUML packets (`0x55 len 0x04 ...`)
  N/A                 | OUT (iOS device => DJI device) | DUML packets (`0x55 len 0x04 ...`)

  The OUT endpoint contains raw unencapsulated DUML packets.

Only one DUML packet per USB encapslation packet was observed.

Both these devices have the same PID, so how can a program decide which protocol to use?
I don't know for sure, but my best guess would be to use the interface name ("com.dji.common" vs "com.dji.logiclink").
`bcdDevice` could be another differentiator.

## Starting the video stream (newer devices only)

On newer DJI devices, the host must send two DUML commands for the DJI device to start sending video.
(On older DJI devices this is not required, they start sending video on their own.)

The following packet dumps are for the DJI Goggles N3 (connected to O4 Air Unit Pro). On other devices they might be different.

cmd # | USB encapsulation header | DUML header | DUML payload  | DUML CRC16
--|--------------------------|-------------|---------------|-----------
1 | `55 cc 49 57 2d 00 00 00` | `55 2d 04 f2 02 28 f3 fe 40 00 99` | `02 02 00 00 d5 07 00 00 00 00 00 13 00 0d 00 63 61 6d 63 61 70 5f 63 6f 6d 6d 6f 6e 00 00 00 00 d0 93` | `92 3a`
2 | `55 cc 49 57 1b 00 00 00` | `55 1b 04 75 02 3c f4 fe 40 00 88` | `17 00 00 23 00 41 50 50 00 00 00 00 00 02 58 a6` | `34 18`

Replaying these packets 1:1 starts the video stream (if the air unit is connected).
If no further action is taken, the video stream stops after 11 seconds.
Replaying both packets at an interval of 5 seconds keeps the stream going indefinitely. (Replaying only one of them does not keep the stream going.)

(Even though these packets contain a sequence number, replaying them without bumping the sequence number works just fine)

**Reference keep-alive behavior**

This info is not needed for getting video out but here's what the real DJI + iOS device does.

- The `00 99` command (cmd #1 in the table above) is resent once a second. The payload remains the same except for the 5th byte (`0xd5` in the example above) which increments by 1 or two on every send.
- The `00 88` command (cmd #2) is not resent. Instead, a second `00 88` command is sent with a different payload. After that, it goes the other way around: the DJI device sends a `00 88` command to the iDevice once a second, which the iDevice acknowledges with the payload `1a 00 00 00 00`.

## Spoofing Role Switch

With some special hardware we can get the DJI device to connect to a normal PC in "mobile/MFI mode".

The instructions here are for a [Cynthion](https://greatscottgadgets.com/cynthion/). (Alternatively you might be able to use a Linux device with a USB port that supports both Host and Device roles, e.g. Raspberry Pi Zero.)

See [](emulate_iphone.py)

1. Install prerequisites if you haven't already:
   ```sh
   python3 -m pip install cynthion facedancer
   ```
2. Connect your Cynthion's CONTROL port to the computer and put it into device emulation mode:
   ```sh
   cynthion run facedancer
   ```
3. Power up the DJI device
4. Connect the target ports:
   ```
                    .---------------------.
    Computer ====== | CONTROL    TARGET A | ====== Computer
                    |      Cynthion       |
                    |            TARGET C | ====== DJI Device
                    `---------------------`
   ```
   (The connection "Target A === Computer" may seem the wrong way around, but this is how it worked for me. You can use a USB-A to USB-C cable for this.)

5. Run [emulate_iphone.py](scripts/emulate_iphone.py). The script will log several bus resets, but after a few seconds it should receive
   a VENDOR request from the DJI device to switch into host mode. This causes the script to quit with a success message and the Cynthion to leave the bus.

6. At this point you should see the DJI device (vendor ID `0x2ca3`) in lsusb on your computer, and it should be in "mobile/MFI" mode.

In my understanding, this procedure briefly causes some illegal conditions on the bus because the data lines D+/D- of the
target ports are physically connected so there are times at which there are three devices on the same bus.
I'm not 100% sure why it works, but in my setup it does.

Troubleshooting:
- If the script exits with "FacedancerApp failed to autodetect any Facedancer devices.", make sure you ran the `cynthion run facedancer`. Presumably you need to re-run this after power cycling the Cynthion.
- If the script quits successfully but you don't see the DJI device in lsusb
  - try rerunning the script
  - try connecting Target A to USB hub instead of the computer directly
- If you get the DJI device to successfully enumerate but it disappears after a while, try switching up the order of operations (connect both targets first, then launch script)

## Demo

1. Connect to the DJI device in mobile mode, e.g. by using the method in the previous section.
2. Make sure your DJI ground device (Goggles, Remote Control) is connected to an Aircraft / Air Unit
3. Run [video_out_mobile.py](scripts/video_out_mobile.py):
   ```sh
   python3 -u video_out_mobile.py | ffplay -vf "setpts=PTS-STARTPTS" -fflags nobuffer -flags low_delay -f h264 -i -
   ```
   This should open an `ffplay` window that shows the live stream.

## Notes on Reverse Engineering

Most of this was obtained using a [Cynthion](https://greatscottgadgets.com/cynthion/) USB analyzer.

- The following configuration worked for sniffing traffic between DJI device and iPhone:

  ```
  DJI device ===== [Target C] Cynthion [Target A] ===== iPhone
  ```

- The following configuration is known _not to work_ for sniffing traffic between DJI device and iPhone

  ```
  DJI device ===== [Target A] Cynthion [Target C] ===== iPhone
  ```

- Packetry (v0.4.0) gets slightly confused by the role switch. In the "Devices" view it will show a descriptor tree that is a mix of the iPhone's and the DJI device's descriptors. Look at the raw packets to determine the real descriptors.

- When you run `cynthion run analyzer` or `cynthion run facedancer` you might run into errors such as
  
  ```
  OSError: Failed to execute last command! (bitstream provides data past the device's SRAM array / fffffff8)
  OSError: Failed to verify device IDCODE! (error unknown / f8200100)
  ```

  Power cycling the Cynthion usually fixes this.

- Even short captures can result in very large capture files (1GB+).
  Packetry can handle them, but Wireshark (which is better at filtering tasks) becomes slow.

  Use one of these filters:
  - `usbll.pid != 0x5a && usbll.pid != 0x69 && usbll.pid != 0xa5` (filters the most spammy SOF, IN and NACK packets)
  - `usbll.pid != 0x5a && usbll.pid != 0x69 && usbll.pid != 0xa5 && usbll.pid != 0xe1  && usbll.pid != 0xd2` (filters most packets except SETUP/DATA0/1/2)

  Then export the shown packets as a new pcap file and reopen that (much smaller) file.
