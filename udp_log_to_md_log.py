#
# Usage Example:
#   python udp_log_to_md_log.py -i ../logs/log_wifi_mitm_2.pcap -o ../logs/log_wifi_mitm_2_mb.pcap --addr1 192.168.2.1:9003 --addr2 192.168.2.20
#
# This only considers IPv4 UDP packets between 192.168.2.1:9003 and 192.168.2.20.


import argparse
import struct

# Reference: https://wiki.wireshark.org/Development/LibpcapFileFormat

parser = argparse.ArgumentParser(description="Convert dji_udp.pcap to dji_mb.pcap "
        "where dji_udp.pcap is a network capture containing DJI UDP protocol "
        "packets and dji_mb.pcap contains the raw DJI MB protocol packets.")
parser.add_argument("-i", "--input", type=argparse.FileType('rb'), required=True)
parser.add_argument("-o", "--output", type=argparse.FileType('wb'), required=True)
parser.add_argument("--addr1", type=str)
parser.add_argument("--addr2", type=str)
parser.add_argument("-u", "--userdlt", default=0, type=int)

args = parser.parse_args()
in_fp = args.input
out_fp = args.output

def parse_addr(s):
    if s is None:
        return (None, None)
    port = None if not (':' in s) else int(s.split(':')[1])
    return (
        bytes([int(i) for i in s.split(':')[0].split('.')]),
        None if port is None else bytes([port >> 8, port & 0xff])
    )
addr1 = parse_addr(args.addr1)
addr2 = parse_addr(args.addr2)

def match_addr(addrA, addrB):
    return addrA == (addrB[0] or addrA[0], addrB[1] or addrA[1])

header = in_fp.read(24)
magic_number = struct.unpack('<I', header[:4])[0]

if (magic_number == 0xa1b2c3d4) or (magic_number == 0xa1b2c34d):
    endianness = '<'
elif (magic_number == 0xd4c3b2a1) or (magic_number == 0x4dc3b2a1):
    endianness = '>'
else:
    raise Exception("unknown magic number")

# Copy header to output file but set the link type to USER_0. This is the same
# as in https://github.com/o-gs/dji-firmware-tools/blob/master/comm_dat2pcap.py
header = header[:20] + struct.pack(endianness + 'I', 147+args.userdlt)
out_fp.write(header)

n_bad = 0
n_ignored = 0
n_good = 0
senders = {i: set() for i in range(7)}
receivers = {i: set() for i in range(7)}

while True:
    record_header = in_fp.read(16)
    if (len(record_header) < 16):
        break # end of file

    ts_sec, ts_usec, incl_len, orig_len = struct.unpack(endianness + 'IIII', record_header[:16])
    eth_packet = in_fp.read(incl_len)

    # Filter packets
    match = (
        (eth_packet[0x0c:0x0e] == bytes([0x08, 0x00])) and # is IPv4?
        (eth_packet[0x17] == 0x11) and # is UDP?
        ((match_addr((eth_packet[0x1a:0x1e], eth_packet[0x22:0x24]), addr1) and
          match_addr((eth_packet[0x1e:0x22], eth_packet[0x24:0x26]), addr2)) or
         (match_addr((eth_packet[0x1a:0x1e], eth_packet[0x22:0x24]), addr2) and
          match_addr((eth_packet[0x1e:0x22], eth_packet[0x24:0x26]), addr1)))
    )

    if not match:
        n_ignored += 1
        continue

    udp_packet = eth_packet[0x2a:]

    packet_type = udp_packet[6]
    if packet_type == 0:
        mb_offset = len(udp_packet) # no MB payload
    elif packet_type == 1:
        len1 = struct.unpack('<H', udp_packet[0x1c:0x1e])[0] # variable length resend list
        mb_offset = 0x20 + 2 * len1
    elif packet_type == 2:
        mb_offset = len(udp_packet) # no MB payload
    elif packet_type == 3:
        mb_offset = 0x14
    elif packet_type == 4 or packet_type == 6:
        len1 = struct.unpack('<H', udp_packet[0x0c:0x0e])[0] # variable length resend list
        len2 = struct.unpack('<H', udp_packet[(0x12+2*len1):(0x14+2*len1)])[0] # variable length resend list
        mb_offset = 0x1e + 2 * len1 + 2 * len2
    elif packet_type == 5:
        mb_offset = 0x14
    else:
        print("unknown packet type " + str(packet_type))
        n_bad += 1

    while (mb_offset < len(udp_packet)):
        if udp_packet[mb_offset] != 0x55:
            print("found MB packet that does not start with 0x55")
            n_bad += 1
            break
        length = (udp_packet[mb_offset + 1] + (udp_packet[mb_offset + 2] << 8)) & 0x3ff
        
        senders[packet_type].add(udp_packet[mb_offset + 4] & 0x1f)
        receivers[packet_type].add(udp_packet[mb_offset + 5] & 0x1f)

        out_fp.write(struct.pack(endianness + 'IIII', ts_sec, ts_usec, length, length))
        out_fp.write(udp_packet[mb_offset:(mb_offset + length)])

        n_good += 1
        mb_offset += length
    
print("found " + str(n_bad) + " bad input packets")
print("ignored " + str(n_ignored) + " input packets")
print("wrote " + str(n_good) + " output packets")

for packet_type in range(7):
    print("packet type {} contains mb packets from senders {} and for receivers {}".format(
        packet_type,
        senders[packet_type],
        receivers[packet_type]
    ))
