"""
Emulates an iPhone on a Cynthion.

Used to get a MFI device (such as DJI Mavic Pro, DJI Goggles N3, ...) to present
themselves in the same way they would to an iPhone.

For usage instructions, see usb_mobile_protocol.md#spoof-role-switch.
"""

import sys
from facedancer import *
from facedancer import main

@use_inner_classes_automatically
class MockiPhone(USBDevice):
    """
    Minimal representation of an iPhone to get the target MFI device to issue a
    role switch request.
    """
    vendor_id            : int = 0x05AC # Apple, Inc.
    product_id           : int = 0x12A8 # iPhone SE (1st generation) (other PIDs work too)

    # Minimum 1 configuration with 1 interface is required
    class DefaultConfiguration(USBConfiguration):
        class DefaultInterface(USBInterface):
            pass

    @vendor_request_handler()
    def handle_control_request_1(self, request):
        print(f"Received vendor request: {request}")
        if request.request == 0x51:
            print("Role switch request received.")
            request.acknowledge(blocking=True)
            self.handle_bus_reset()
            print("Pretended there was a bus reset to get out of the way")
            print("Exiting. You should now see your target device in `lsusb` on the host.")
            sys.exit(0)
        else:
            request.stall()

main(MockiPhone)
