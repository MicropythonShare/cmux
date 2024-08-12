import network
import urequests
from time import sleep, ticks_diff, ticks_ms
# from ubinascii import hexlify

from cmux import cmux

from modem import send_at, startModem

    
uartModem = startModem()

# Start cmux
cmux7608 = cmux(uartModem)
print(f"CMUX protocol started: {cmux7608.cmuxProtocolStarted}")
print(f"Channel 0 status: {cmux7608.channels[0].status}")
print()

cmux7608.openChannel(channel=1)
print(f"Channel 1 status: {cmux7608.channels[1].status}")
print(f"Channel 1 V.24 signals: {cmux7608.channels[1].v24Signals}")
print(f"Channel 1 uaReceived: {cmux7608.channels[1].uaReceived}")
print()

print("Cleaning initializing garbage from channel 1...")
response = True
while response:
    if cmux7608.channels[1].virtualUARTconn.ucUART.any(timeout_ms=4000):
        response = cmux7608.channels[1].virtualUARTconn.ucUART.read()
        print(f"From channel 1: {response}")
    else:
        response = None
print()

cmux7608.openChannel(channel=2)
print(f"Channel 2 status: {cmux7608.channels[2].status}")
print(f"Channel 2 V.24 signals: {cmux7608.channels[2].v24Signals}")
print(f"Channel 2 uaReceived: {cmux7608.channels[2].uaReceived}")
print()

# Send AT command via channel 1
response = cmux7608.send_at("AT", channel=1)
print(f"AT command response on channel 1: {response}")
print()

# Send AT command via channel 2
response = cmux7608.send_at("ATI", channel=2)
print(f"AT command response on channel 2: {response}")
print()

# Start PPP on channel 1
response = cmux7608.send_at("ATD*99#", channel=1)
print(f"AT command response on channel 1 to activate PPP: {response}")

# Attach the physical UART to channel 1 for PPP
# cmux7608.channels[1].pppUart = uartCmux1
# cmux7608.channels[1].pppUart.write("Starting PPP")

# Start PPPoS protocol
print("Start PPPoS protocol")
ppp = network.PPP(cmux7608.channels[1].virtualUARTconn.ucUART)
ppp.active(True)
ppp.connect()

while not ppp.isconnected():
    sleep(0.2)
print(f"IP config: ({', '.join(ppp.ifconfig())})")

while True:
    # Send AT command on channel 1 again
    # response = cmux7608.send_at("AT", channel=1)
    # print(f"AT command response on channel 1: {response}")
    # print()

    # Send a request via PPP on channel 1
    print(urequests.get(url="http://checkip.amazonaws.com/"))
    print()

    # Send AT command via channel 2 again
    response = cmux7608.send_at("ATI", channel=2)
    print(f"AT command response on channel 2: {response}")
    print()

    sleep(3)
