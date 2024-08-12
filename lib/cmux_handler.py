from time import sleep

from .cmux_constants import *


def cmux_handler(cmux):
    """
    Una async task con la instancia cmux para esta secuencia cíclica:
        - Lee la UART física:
            - Desempaqueta y procesa todos los frames UIH de control (dirigidos al canal 0 para acciones sobre cualquier canal):
                - MSN, PSC, CLD, FCoff, FCon
            - Desempaqueta y procesa otros comandos dirigidos a cualquier canal:
                - SABM, UA, DM, DISC
            - Desempaqueta frames UIH y reenvía el payload al buffer_in del canal correspondiente (1 al 4)

        - Revisa los buffer_out de cada canal en secuencia:
            - Solo se revisa el buffer de los canales que tengan status = CHANNEL_READY
            - Si hay data en un buffer_out revisado, la empaqueta y envía por la UART física con una UIH Frame
    """

    while cmux.cmuxProtocolStarted:
        # Read the physical UART and add it to the cmux buffer
        newFrames = cmux.physicalUART.read()
        if newFrames:
            cmux.physicalUartBufferIn = cmux.physicalUartBufferIn + newFrames

        startFlagIndex = cmux.physicalUartBufferIn.find(b'\xF9')
        while startFlagIndex >= 0:
            validFrame = False
            try:
                # Try to get a frame and its basic parts
                addressByte = cmux.physicalUartBufferIn[startFlagIndex + 1]
                channel = addressByte >> 2
                controlByte = cmux.physicalUartBufferIn[startFlagIndex + 2]
                lengthByte = cmux.physicalUartBufferIn[startFlagIndex + 3]
                length = lengthByte >> 1

                if length + 6 <= len(cmux.physicalUartBufferIn):
                    frame = cmux.physicalUartBufferIn[startFlagIndex : startFlagIndex + 6 + length]

                    if frame[0] == 0xF9 and frame[-1] == 0xF9:
                        frame = frame[1:-1]
                        fcsByte = frame[-1]
                        if channel >= 0 and channel <= 4:
                            if cmux.check_fcs(frame[0:3], fcsByte):
                                if len(frame[3:-1]) == length:

                                    if controlByte == 0x3F:
                                        # SABM frame (I guess this one is never incoming)
                                        validFrame = True

                                    elif controlByte == 0x73:
                                        # UA frame --> Example: F9 07 73 01 15 F9
                                        # print(f"UA frame receive for channel {channel}")
                                        cmux.channels[channel].uaReceived = True
                                        validFrame = True

                                    elif controlByte == 0x1F:
                                        ## TODO: DM frame
                                        validFrame = True
                                    
                                    elif controlByte == 0x53:
                                        ## TODO: DISC frame
                                        validFrame = True
                                        
                                    elif controlByte == 0xEF | 0xFF: # UBLOX modem uses OxFF for controlByte?
                                        # UIH frame
                                        if frame[0] == 0x01 and frame[3] == 0xE1:
                                            # MSC frame --> Example: F9 01 EF 09 E1 05 0B 0D 9A F9
                                            mscTargetChannel = frame[-3] >> 2
                                            mscLength = frame[4] >> 1
                                            if mscLength == len(frame[5:-1]):
                                                cmux.channels[mscTargetChannel].v24Signals = frame[-2]
                                                validFrame = True
                                            else:
                                                print(f"Invalid MSC length byte not matching data size in frame: {frame}")

                                        elif frame[0] != 0x01:
                                            # Data frame --> Example: b'\x05\xEF\x07AT\r\xB2'
                                            if cmux.channels[channel].pppUart is None:
                                                # Send data from de modem's virtual UART to the uc's virtual UART
                                                cmux.channels[channel].virtualUARTconn.modemUART.write(frame[3:-1])
                                                validFrame = True
                                            else:
                                                # Send data to the physical UART for PPP
                                                cmux.channels[channel].pppUart.write(frame[3:-1])
                                                validFrame = True
                                        else:
                                            print("Unknown UIH frame: {frame}")

                                else:
                                    print(f"Invalid length byte not matching data size in frame: {frame}")
                            else:
                                print(f"Wrong FCS byte in frame: {frame}")
                        else:
                            print(f"Wrong address byte in frame: {frame}")

                # Remove the left part of the physicalUartBufferIn if a good frame was processed
                if validFrame:
                    cmux.physicalUartBufferIn = cmux.physicalUartBufferIn[startFlagIndex + 5 + length + 1 : ]
                    startFlagIndex = -1

                # Look for any other possible frame in the physicalUartBufferIn
                startFlagIndex = cmux.physicalUartBufferIn.find(b'\xF9', startFlagIndex + 1)

            except Exception as error:
                print("Error processing an incoming frame in cmux_handler: " +  str(error))
                startFlagIndex = cmux.physicalUartBufferIn.find(b'\xF9', startFlagIndex + 1)

        sleep(0.05)

        # Process output for each data channel (1 to 4)
        for channel in range(1, 5):
            if cmux.channels[channel].status == CHANNEL_READY:
                if cmux.channels[channel].pppUart is None:
                    # Read data arrived to modem's virtual UART from uc's virtual UART
                    data = cmux.channels[channel].virtualUARTconn.modemUART.read()
                else:
                    # Read data from physical UART (PPP)
                    data = cmux.channels[channel].pppUart.read()
                if data:
                    # Some data to pack and send to physical UART into a cmux frame
                    addressByte = (channel << 2 | 3).to_bytes(1, "big")
                    length = (len(data) << 1 | 1).to_bytes(1, "big")
                    address_control_length = addressByte + b'\xEF' + length
                    cmux.physicalUART.write(b'\xF9' + address_control_length + data + cmux.fcs(address_control_length) + b'\xF9')

        sleep(0.05)
