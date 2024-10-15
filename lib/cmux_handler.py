from time import sleep

from .cmux_constants import *


def calculateLength(buffer, lengthPosition, attempts=0):
    # Data length calculation
    lengthByte1 = buffer[lengthPosition]

    if not lengthByte1 & 1:
        # LSB is 0 --> 2 bytes for length of data (dropping LSB of lengthByte1 and joining to lengthByte2 like this:
        # lengthByte2_(lengthByte1 >> 1)
        
        lengthByte2 = buffer[lengthPosition + 1]
        
        # Will use the 8 bits of lengthByte2 but shifting one bit into MSB of shifted lengthByte1
        if lengthByte2 & 1:
            lengthByte1 = (lengthByte1 >> 1) | 128
        else:
            lengthByte1 = lengthByte1 >> 1
        lengthByte2 = lengthByte2 >> 1
        
        lengthBytes = lengthByte2.to_bytes(1, "big") + lengthByte1.to_bytes(1, "big")
        length = int.from_bytes(lengthBytes, "big")
        bytesForLength = 2
    else:
        # LSB is 1 --> 1 byte for length of data
        length = lengthByte1 >> 1
        bytesForLength = 1
        
    return length, bytesForLength


def cmux_handler(cmux):
    """
    Un thread con la instancia cmux para esta secuencia cíclica:
        - Lee la UART física:
            - Desempaqueta y procesa todos los frames UIH de control (dirigidos al canal 0 para acciones sobre cualquier canal):
                - MSN, PSC, CLD, FCoff, FCon
            - Desempaqueta y procesa otros comandos dirigidos a cualquier canal:
                - SABM, UA, DM, DISC
            - Desempaqueta frames UIH y reenvía el payload a la UART virtual del canal correspondiente (1 al 4)

        - Lee las UARTs virtuales de los 4 canales en secuencia:
            - Solo se lee la UART virtual de cada uno los canales que tengan status = CHANNEL_READY
            - Si hay data en una UART virtual revisada, la empaqueta y envía por la UART física con una UIH Frame

        - Este thread puede detenerse desde el programa principal colcando:
            cmux.cmuxProtocolStarted = False
    """

    while cmux.cmuxProtocolStarted:
        # Read the physical UART and add it to the cmux buffer
        newFrames = cmux.physicalUART.read()
        if newFrames:
            cmux.physicalUartBufferIn = cmux.physicalUartBufferIn + newFrames

        startFlagIndex = cmux.physicalUartBufferIn.find(b'\xF9', 0)
        attempts = 0
        while startFlagIndex >= 0:
            validFrame = False
            if cmux.physicalUartBufferIn[startFlagIndex : startFlagIndex + 3]== b'\xf9?\xf9':
                # Discard b'\xf9?\xf9' frame
                cmux.physicalUartBufferIn = cmux.physicalUartBufferIn[startFlagIndex + 3 : ]
                # Look for any other possible frame in the physicalUartBufferIn
                startFlagIndex = cmux.physicalUartBufferIn.find(b'\xF9', 0)
                continue

            try:
                # Try to get a frame and its basic parts
                addressByte = cmux.physicalUartBufferIn[startFlagIndex + 1]
                channel = addressByte >> 2
                controlByte = cmux.physicalUartBufferIn[startFlagIndex + 2]
                length, bytesForLength = calculateLength(cmux.physicalUartBufferIn, startFlagIndex + 3, attempts)

                if length + 5 + bytesForLength <= len(cmux.physicalUartBufferIn):
                    frame = cmux.physicalUartBufferIn[startFlagIndex : startFlagIndex + 5 + bytesForLength + length]
                    
                    if frame[0] == 0xF9 and frame[-1] == 0xF9:
                        frame = frame[1:-1]
                        fcsByte = frame[-1]
                        if channel >= 0 and channel <= 4:
                            if cmux.check_fcs(frame[0: 2 + bytesForLength], fcsByte):
                                if len(frame[2 + bytesForLength:-1]) == length:

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
                                        if frame[0] == 0x01 and frame[2 + bytesForLength] == 0xE1:
                                            # MSC frame --> Example: F9 01 EF 09 E1 05 0B 0D 9A F9
                                            mscTargetChannel = frame[-3] >> 2
                                            mscLength, bytesForMscLength = calculateLength(frame, 3 + bytesForLength)
                                            if mscLength == len(frame[3 + bytesForLength + bytesForMscLength : -1]):
                                                cmux.channels[mscTargetChannel].v24Signals = frame[-2]
                                                validFrame = True
                                            else:
                                                print(f"Invalid MSC length byte not matching data size in frame: {frame}")

                                        elif frame[0] != 0x01:
                                            # Data frame --> Example: b'\x05\xEF\x07AT\r\xB2'
                                            if cmux.channels[channel].pppUart is None:
                                                # Send data from the modem's virtual UART to the uc's virtual UART
                                                cmux.channels[channel].virtualUARTconn.modemUART.write(frame[2 + bytesForLength : -1])
                                                validFrame = True
                                            else:
                                                # Send data to the physical UART for PPP
                                                cmux.channels[channel].pppUart.write(frame[2 + bytesForLength : -1])
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
                    cmux.physicalUartBufferIn = cmux.physicalUartBufferIn[startFlagIndex + 4 + bytesForLength + length + 1 : ]
                    startFlagIndex = -1
                    # Look for any other possible frame in the physicalUartBufferIn
                    startFlagIndex = cmux.physicalUartBufferIn.find(b'\xF9', startFlagIndex + 1)
                    attempts = 0
                elif attempts < 2:
                    # Add any additional bytes from the UART (that maybe will complete a segmented frame)
                    newFrames = cmux.physicalUART.read()
                    if newFrames:
                        cmux.physicalUartBufferIn = cmux.physicalUartBufferIn + newFrames
                    attempts = attempts + 1
                else:
                    # Add any additional bytes from the UART (that maybe will complete a segmented frame)
                    newFrames = cmux.physicalUART.read()
                    if newFrames:
                        cmux.physicalUartBufferIn = cmux.physicalUartBufferIn + newFrames
                    # Look for any other possible frame in the physicalUartBufferIn
                    startFlagIndex = cmux.physicalUartBufferIn.find(b'\xF9', startFlagIndex + 1)
                    attempts = 0

            except Exception as error:
                print("Error processing an incoming frame in cmux_handler: " +  str(error))
                if attempts < 2:
                    # Add any additional bytes from the UART (that maybe will complete a segmented frame)
                    sleep(0.50)
                    newFrames = cmux.physicalUART.read()
                    if newFrames:
                        cmux.physicalUartBufferIn = cmux.physicalUartBufferIn + newFrames
                    attempts = attempts + 1
                else:
                    # Add any additional bytes from the UART (that maybe will complete a segmented frame)
                    newFrames = cmux.physicalUART.read()
                    if newFrames:
                        cmux.physicalUartBufferIn = cmux.physicalUartBufferIn + newFrames
                    # Look for any other possible frame in the physicalUartBufferIn
                    startFlagIndex = cmux.physicalUartBufferIn.find(b'\xF9', startFlagIndex + 1)
                    attempts = 0

        sleep(0.05)

        # Process output for each data channel (1 to 4)
        for channel in range(1, 5):
            if cmux.channels[channel].status == CHANNEL_READY:
                if cmux.channels[channel].pppUart is None:
                    # Read data arrived to modem's virtual UART from uc's virtual UART
                    data = cmux.channels[channel].virtualUARTconn.modemUART.read(1500)
                else:
                    # Read data from physical UART (PPP)
                    data = cmux.channels[channel].pppUart.read()
                if data:
                    # Some data to pack and send to physical UART into a cmux frame
                    addressByte = (channel << 2 | 3).to_bytes(1, "big")
                    if len(data) <= 127:
                        length = (len(data) << 1 | 1).to_bytes(1, "big")
                    else:
                        lengthBytes = len(data).to_bytes(2, "big")
                        lengthByte2 = lengthBytes[0] << 1
                        if lengthBytes[1] & 128:
                            lengthByte2 = lengthByte2 | 1
                        lengthByte1 = lengthBytes[1] << 1
                        length = lengthByte1.to_bytes(1, "big") + lengthByte2.to_bytes(1, "big")
                    address_control_length = addressByte + b'\xEF' + length
                    cmux.physicalUART.write(b'\xF9' + address_control_length + data + cmux.fcs(address_control_length) + b'\xF9')

        sleep(0.05)
