import _thread
from time import sleep, ticks_diff, ticks_ms

from .cmux_constants import *
from .cmux_handler import cmux_handler
from .virtual_uart import VitualUARTConn


def send_at(uart, at_cmd, timeout_secs=0, debug_mode=True):
    
    # Send AT command. Waiting time for response is configurable (seconds).

    timeout_ms = timeout_secs * 1000
    uart.read()  # Clean buffer
    print(at_cmd)
    at_cmd = at_cmd + "\r\n"
    at_cmd_bytes = bytes(at_cmd, 'utf-8')
    sentBytes = uart.write(at_cmd_bytes)

    if debug_mode:
        data = b''
        isDone = False
        startTime = ticks_ms()
        while not isDone:
            while not uart.any() and ticks_diff(ticks_ms(), startTime) < timeout_ms:
                sleep(0.1)
            if ticks_diff(ticks_ms(), startTime) > timeout_ms:
                isDone = True
            nextData = uart.read()
            if nextData:
                data = data + nextData
        if not data:
            print("...No response")
            return False
        else:
            print(data.decode("utf-8"))
            return data.decode("utf-8")


class CmuxChannel():
    def __init__(self):
        self.virtualUARTconn = VitualUARTConn("ucUART", "modemUART", 8192)
        self.uaReceived = False
        self.status = CHANNEL_CLOSED
        self.v24Signals = None
        self.pppUart = None


    def clear_uarts_buffers(self):
        while self.virtualUARTconn.ucUART.any():
            self.virtualUARTconn.ucUART.read()
        while self.virtualUARTconn.modemUART.any():
            self.virtualUARTconn.modemUART.read()


class cmux():
    def __init__(self, physicalUART):
        self.physicalUART = physicalUART
        self.physicalUartBufferIn = b''
        self.cmuxProtocolStarted = False
        self.channels = []
        for channel in range(0, 5):
            self.channels.append(CmuxChannel())

        # Tabla de CRC precomputada
        self.crctable = [
            0x00, 0x91, 0xE3, 0x72, 0x07, 0x96, 0xE4, 0x75, 0x0E, 0x9F, 0xED, 0x7C, 0x09, 0x98, 0xEA, 0x7B,
            0x1C, 0x8D, 0xFF, 0x6E, 0x1B, 0x8A, 0xF8, 0x69, 0x12, 0x83, 0xF1, 0x60, 0x15, 0x84, 0xF6, 0x67,
            0x38, 0xA9, 0xDB, 0x4A, 0x3F, 0xAE, 0xDC, 0x4D, 0x36, 0xA7, 0xD5, 0x44, 0x31, 0xA0, 0xD2, 0x43,
            0x24, 0xB5, 0xC7, 0x56, 0x23, 0xB2, 0xC0, 0x51, 0x2A, 0xBB, 0xC9, 0x58, 0x2D, 0xBC, 0xCE, 0x5F,
            0x70, 0xE1, 0x93, 0x02, 0x77, 0xE6, 0x94, 0x05, 0x7E, 0xEF, 0x9D, 0x0C, 0x79, 0xE8, 0x9A, 0x0B,
            0x6C, 0xFD, 0x8F, 0x1E, 0x6B, 0xFA, 0x88, 0x19, 0x62, 0xF3, 0x81, 0x10, 0x65, 0xF4, 0x86, 0x17,
            0x48, 0xD9, 0xAB, 0x3A, 0x4F, 0xDE, 0xAC, 0x3D, 0x46, 0xD7, 0xA5, 0x34, 0x41, 0xD0, 0xA2, 0x33,
            0x54, 0xC5, 0xB7, 0x26, 0x53, 0xC2, 0xB0, 0x21, 0x5A, 0xCB, 0xB9, 0x28, 0x5D, 0xCC, 0xBE, 0x2F,
            0xE0, 0x71, 0x03, 0x92, 0xE7, 0x76, 0x04, 0x95, 0xEE, 0x7F, 0x0D, 0x9C, 0xE9, 0x78, 0x0A, 0x9B,
            0xFC, 0x6D, 0x1F, 0x8E, 0xFB, 0x6A, 0x18, 0x89, 0xF2, 0x63, 0x11, 0x80, 0xF5, 0x64, 0x16, 0x87,
            0xD8, 0x49, 0x3B, 0xAA, 0xDF, 0x4E, 0x3C, 0xAD, 0xD6, 0x47, 0x35, 0xA4, 0xD1, 0x40, 0x32, 0xA3,
            0xC4, 0x55, 0x27, 0xB6, 0xC3, 0x52, 0x20, 0xB1, 0xCA, 0x5B, 0x29, 0xB8, 0xCD, 0x5C, 0x2E, 0xBF,
            0x90, 0x01, 0x73, 0xE2, 0x97, 0x06, 0x74, 0xE5, 0x9E, 0x0F, 0x7D, 0xEC, 0x99, 0x08, 0x7A, 0xEB,
            0x8C, 0x1D, 0x6F, 0xFE, 0x8B, 0x1A, 0x68, 0xF9, 0x82, 0x13, 0x61, 0xF0, 0x85, 0x14, 0x66, 0xF7,
            0xA8, 0x39, 0x4B, 0xDA, 0xAF, 0x3E, 0x4C, 0xDD, 0xA6, 0x37, 0x45, 0xD4, 0xA1, 0x30, 0x42, 0xD3,
            0xB4, 0x25, 0x57, 0xC6, 0xB3, 0x22, 0x50, 0xC1, 0xBA, 0x2B, 0x59, 0xC8, 0xBD, 0x2C, 0x5E, 0xCF
        ]

        # Send the AT command to start CMUX protocol
        maxFrameZize = 1500
        if "OK" in send_at(self.physicalUART, f"AT+CMUX=0,0,5,{maxFrameZize},0,0,600", timeout_secs=1):
            self.cmuxProtocolStarted = True
            # Start parallel thread to handle the cmux protocol layer
            started = False
            while not started:
                try:
                    _thread.start_new_thread(cmux_handler, (self,))
                    started = True
                except Exception as error:
                    print("Error starting _cmux_handler thread: " +  str(error))
                    sleep(0.050)

            # Open channel 0:
            if not self.openChannel(channel=0):
                # Channel 0 failed to open, let's stop the thread
                self.cmuxProtocolStarted = False


    def fcs(self, message):
        """
        Calcula el FCS para un buffer dado.

        :param message: El message de entrada como una lista o bytes.
        :return: El byte FCS calculado.
        """
        fcs = 0xFF
        for b in message:
            fcs = self.crctable[fcs ^ b]
        return (0xFF - fcs).to_bytes(1, "big")


    def check_fcs(self, message, received_fcs):
        """
        Verifica el FCS para un buffer dado.

        :param message: El message de entrada como una lista o bytes.
        :return: True si el FCS es correcto; False en caso contrario.
        """
        fcs = 0xFF
        for b in message:
            fcs = self.crctable[fcs ^ b]
        fcs = self.crctable[fcs ^ received_fcs]

        # La constante 'CF' es el orden invertido de '11110011'
        return fcs == 0xCF
    

    def openChannel(self, channel):
        self.channels[channel].clear_uarts_buffers()
        self.channels[channel].uaReceived = False
        if type(channel) == int and channel >= 0 and channel <= 4:
            self.channels[channel].status = CHANNEL_CLOSED
            self.channels[channel].v24Signals = 0x03

            # Send cmux SABM message to Open channel
            print(f"Opening channel {channel}")
            addressByte = (channel << 2 | 3).to_bytes(1, "big")
            address_control_length = addressByte + b'\x3F\x01'
            self.physicalUART.write(b'\xF9' + address_control_length + self.fcs(address_control_length) + b'\xF9')
            
            # Wait for UA response
            n = 0
            sleep(0.2)
            while not self.channels[channel].uaReceived and n < 3:
                sleep(0.2)
                n = n + 1
            if self.channels[channel].uaReceived:
                # UA response received --> channel is open
                if channel > 0:
                    self.channels[channel].status = CHANNEL_OPEN_NOT_READY

                    # Send MSC message to set V.24 signals enabling the channel
                    address_control_length = b'\x03\xEF\x09'
                    self.physicalUART.write(b'\xF9' + address_control_length +
                                            b'\xE3\x05' + addressByte + b'\x0D' +
                                            self.fcs(address_control_length) + b'\xF9')
                    
                    # Wait for response to MSC message
                    n = 0
                    sleep(0.2)
                    while self.channels[channel].v24Signals == 0x03 and n < 3:
                        sleep(0.2)
                        n = n + 1
                    if self.channels[channel].v24Signals == 0x0D:
                        # Positive MSC message received. Data channel is ready to be used
                        self.channels[channel].status = CHANNEL_READY
                else:
                    # Control channel (0) is ready to be used
                    self.channels[channel].status = CHANNEL_READY
            return self.channels[channel].status
        else:
            raise Exception("Channel must be an int from 0 to 4")


    def send_at(self, at_cmd, channel=None, timeout_secs=0.5):
        timeout_ms = timeout_secs * 1000
        
        # UIH frame example for "AT" command: b'\xF9\x07\xEF\x09AT\r\n\x58\xF9'

        # Send AT command into a cmux frame
        addressByte = (channel << 2 | 3).to_bytes(1, "big")
        length = (len(at_cmd) + 2 << 1 | 1).to_bytes(1, "big")
        address_control_length = addressByte + b'\xEF' + length
        message = b'\xF9' + address_control_length + at_cmd + "\r\n" + self.fcs(address_control_length) + b'\xF9'
        self.physicalUART.write(message)

        # Receive the unpacked response in the virtual channel
        completeResponse = ""
        ucUART = self.channels[channel].virtualUARTconn.ucUART
        if self.channels[channel].virtualUARTconn.wait_any(ucUART, timeout_ms=timeout_ms):
            data = self.channels[channel].virtualUARTconn.ucUART.read()
            while data:
                # Response example for "AT" command over channel 1 containing 2 segments (flags removed by the split):
                #   AT\r\r\r\nOK\r\n
                completeResponse = completeResponse + data.decode("utf-8")
                sleep(0.1)
                self.channels[channel].virtualUARTconn.wait_any(ucUART, timeout_ms=timeout_ms)
                data = self.channels[channel].virtualUARTconn.ucUART.read()
        return completeResponse
