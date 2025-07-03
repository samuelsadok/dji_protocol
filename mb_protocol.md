# DJI Proprietary Message Bus Protocol

(ok I don't actually know what the "mb" stands for but it appears in the `dji_mb_ctrl` utility on some drones)

This is a stub page for DJI's widespread proprietary protocol, generally known as DUML. This protocol is used by most DJI components to communicate with each other, including the mobile app and DJI Assistant. It is easily recognizable by the byte `0x55` at the start of each packet (often `0x55 0x?? 0x04 ...`).

Resources:
- [Wireshark Dissector](https://github.com/o-gs/dji-firmware-tools/tree/master/comm_dissector)
- [Format description](https://www.push-force.dev/article/73)
- Routing tables: see `/system/etc/dji.json` on the DJI device's file system
