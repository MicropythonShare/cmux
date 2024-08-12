from collections import deque
from io import IOBase
from micropython import ringbuffer, const
from time import sleep, ticks_diff, ticks_ms

try:
    from typing import Union, Tuple
except:
    pass

# From micropython/py/stream.h
_MP_STREAM_ERROR = const(-1)
_MP_STREAM_FLUSH = const(1)
_MP_STREAM_SEEK = const(2)
_MP_STREAM_POLL = const(3)
_MP_STREAM_CLOSE = const(4)
_MP_STREAM_POLL_RD = const(0x0001)


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
    This could be used also somewhat similarly to a socket.socketpair in python, like a pipe
    of data that can be used to connect stream consumers (eg. asyncio.StreamWriter)
    """
    def __init__(self, uart1_name, uart2_name, buffer_size: Union[int, Tuple[int, int]]=256):
        try:
            size_a, size_b = buffer_size
        except TypeError:
            size_a = size_b = buffer_size

        a = ringbuffer(size_a)
        b = ringbuffer(size_b)
        
        # Add the two virtual UARTS (StreamPairs) as properties of the VitualUARTConn
        addProperty(self, uart1_name, StreamPair(a, b))
        addProperty(self, uart2_name, StreamPair(b, a))
        
        
    def getUARTs(self):
        return [prop for prop in dir(self) if isinstance(getattr(self, prop), StreamPair)]


class StreamPair(IOBase):

    def __init__(self, rx: ringbuffer, tx: ringbuffer):
        self.rx = rx
        self.tx = tx
        super().__init__()

    def read(self, nbytes=-1):
        return self.rx.read(nbytes)

    def readline(self):
        return self.rx.readline()

    def readinto(self, buf, limit=-1):
        return self.rx.readinto(buf, limit)

    def write(self, data):
        return self.tx.write(data)

    def seek(self, offset, whence):
        return self.rx.seek(offset, whence)

    def flush(self):
        while self.rx.any():
            self.rx.read()
        while self.tx.any():
            self.tx.read()

    def close(self):
        self.rx.close()
        self.tx.close()
        
    def clear_rx(self):
        while self.rx.any():
            self.rx.read()

    def any(self, timeout_ms=0):
        startTime = ticks_ms()
        while not self.rx.any() and ticks_diff(ticks_ms(), startTime) < timeout_ms:
            sleep(0.1)
        return self.rx.any()

    def ioctl(self, op, arg):
        if op == _MP_STREAM_POLL:
            if self.any():
                return _MP_STREAM_POLL_RD
            return 0

        elif op ==_MP_STREAM_FLUSH:
            return self.flush()
        elif op ==_MP_STREAM_SEEK:
            return self.seek(arg[0], arg[1])
        elif op ==_MP_STREAM_CLOSE:
            return self.close()

        else:
            return _MP_STREAM_ERROR
