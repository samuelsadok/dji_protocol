# DJI Proprietary Message Bus Protocol

(ok I don't actually know what the "mb" stands for but it appears in the `dji_mb_ctrl` utility on some drones)

This protocol, also known as DUML, is used by most DJI components to communicate with each other, including the mobile app and DJI Assistant. It is easily recognizable by the byte `0x55` at the start of each packet (often `0x55 0x?? 0x04 ...`).

The [Wireshark Dissector](https://github.com/o-gs/dji-firmware-tools/tree/master/comm_dissector) represents the current state of what is publicly known about this protocol.

Routing tables can be found on the aircraft and remote control at `/system/etc/dji.json`.
