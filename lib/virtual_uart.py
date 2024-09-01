from micropython import RingIO
from time import sleep, ticks_diff, ticks_ms

try:
    from typing import Union, Tuple
except:
    pass


def addProperty(theObject, name, value):
    vars = {
        "value": value,
        "theObject": theObject
    }
    exec("theObject.{} = value".format(name), vars)


class VitualUARTConn():
    """
    Creates a virtual UART connection object consisting in two virtual UARTs, where the crossed physical connection
    between rx and tx is represented by two ringbuffers that are crossed between the two AURTs, so that what is
    written to one UART can be read from the other and viceversa.
    """
    def __init__(self, uart1_name, uart2_name, buffer_size: Union[int, Tuple[int, int]]=256):
        try:
            size_a, size_b = buffer_size
        except TypeError:
            size_a = size_b = buffer_size

        # Create the two virtual UARTs with one buffer in loopback between tx and rx
        # Each buffer size as requested (or 256 by default)
        vUART_a = RingIO(size_a)
        vUART_b = RingIO(size_b)
        
        # Add the two virtual UARTs as properties of the VitualUARTConn using the requested custom names
        addProperty(self, uart1_name, vUART_a)
        addProperty(self, uart2_name, vUART_b)
        
        # Link the UARTs crossing their buffers tx1-rx2, rx1-tx2
        vUART_a.link(vUART_b)
        
        
    def getUARTs(self):
        return [prop for prop in dir(self) if isinstance(getattr(self, prop), RingIO)]
    
    
    def wait_any(self, uart, timeout_ms=0):
        startTime = ticks_ms()
        while not uart.any() and ticks_diff(ticks_ms(), startTime) < timeout_ms:
            sleep(0.1)
        return uart.any()
