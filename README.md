# Reverse Engineering DJI's Proprietary Protocols

 - [DJI UDP protocol](udp_protocol.md): Documentation for DJI's UDP protocol
 - [DJI MB protocol](mb_protocol.md): [*Placeholder*] Documentation for DJI's ubiquitous MB protocol (also known as **DUML protocol**)
 - [DJI USB protocol](usb_protocol.md): Documentation for the USB protocol that is used to get collision avoidance video feed during calibration.
 - `recv_vid.py`: Minimal demo to receive video from a Mavic Pro over WiFi
 - `recv_vid_usb.py`: Minimal demo to receive video from the collision avoidance cameras over USB
 - `udp_log_to_md_log.py`: Converts from UDP packet captures (.pcap files) to packet captures that contain only the DJI MB Protocol packets. These can then be analyzed in Wireshark with the [DJI MB protocol dissector](https://github.com/o-gs/dji-firmware-tools/tree/master/comm_dissector).
