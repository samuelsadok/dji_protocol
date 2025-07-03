# Reverse Engineering DJI's Proprietary Protocols

 - [DJI UDP protocol](udp_protocol.md): Documentation for DJI's UDP protocol when connected over WiFi
 - [DJI MB protocol](mb_protocol.md): Stub for DJI's ubiquitous MB protocol (also known as **DUML protocol**)
 - [DJI USB-to-PC protocol](usb_protocol.md): Documentation for the USB protocol that is used to get collision avoidance video feed during calibration.
 - [DJI USB-to-mobile protocol](usb_mobile_protocol.md): Documentation for the USB connection when a DJI device is connected to an iOS mobile device.
 - [`recv_vid.py`](recv_vid.py): Minimal demo to receive video from a Mavic Pro over WiFi
 - [`recv_vid_usb.py`](recv_vid_usb.py): Minimal demo to receive video from the collision avoidance cameras over USB
 - [`udp_log_to_md_log.py`](udp_log_to_md_log.py): Converts from UDP packet captures (.pcap files) to packet captures that contain only the DJI MB Protocol packets. These can then be analyzed in Wireshark with the [DJI MB protocol dissector](https://github.com/o-gs/dji-firmware-tools/tree/master/comm_dissector).
 - [`emulate_iphone.py`](scripts/emulate_iphone.py): Helps spoof a DJI device to connect like it would connect to an iOS device. Requires special hardware.
 - [`video_out_mobile.py`](scripts/video_out_mobile.py): Minimal demo to receive video from a DJI ground device (e.g. DJI Mavic Pro Remote Control, DJI Goggles N3) that is connected via USB in "mobile/MFI" mode.
 - [`lsusb` dumps](lsusb) of various devices
