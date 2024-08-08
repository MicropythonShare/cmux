from io import BytesIO
from time import sleep, ticks_diff, ticks_ms

from .cmux_constants import CHANNEL_CLOSED


class VirtualUART(BytesIO):
    def __init__(self, timeout_ms=3000):
        self.buffer_in = BytesIO(2048)
        self.buffer_out = BytesIO(2048)
        self.timeout_ms = timeout_ms
        self.uaReceived = False
        self.status = CHANNEL_CLOSED
        self.v24Signals = None
        self.pppUart = None
        
        super().__init__()


    def input(self, buf):
        # This simulates data coming in via the rx pin
        self.buffer_in.write(buf)


    def output(self):
        # This simulates data going out via the tx pin
        size = self.buffer_out.tell()
        self.buffer_out.seek(0)
        data = self.buffer_out.read(size)
        self.buffer_out.seek(0)
        
        return data


    def clear_buffer_in(self):
        self.buffer_in.seek(0)


    def clear_buffer_out(self):
        self.buffer_out.seek(0)


    def any(self):
        startTime = ticks_ms()
        while ticks_diff(ticks_ms(), startTime) < self.timeout_ms:
            if self.buffer_in.tell() > 0:
                return self.buffer_in.tell()
            else:
                sleep(0.1)


    def read(self, nbytes=-1):
        if nbytes > -1:
            currentSize = self.buffer_in.tell()
            if nbytes > currentSize:
                nbytes = currentSize
            self.buffer_in.seek(0)
            data = self.buffer_in.read(nbytes)
            remaining = self.buffer_in.read(currentSize - self.buffer_in.tell())
            self.buffer_in.seek(0)
            self.buffer_in.write(remaining)
        else:
            size = self.buffer_in.tell()
            self.buffer_in.seek(0)
            data = self.buffer_in.read(size)
            self.buffer_in.seek(0)
        
        return data


    def readinto(self, buf, nbytes=-1):
        buf = self.read(nbytes)


    def write(self, buf):
        return self.buffer_out.write(buf)
