from machine import Pin, UART
from time import sleep, ticks_diff, ticks_ms


def send_at(uart, at_cmd, wait_time=0, debug_mode=True):
    
    # Send AT command. Waiting time for response is configurable (seconds).

    wait_time = wait_time * 1000
    uart.read()  # Clean buffer
    print(at_cmd)
    at_cmd = at_cmd + "\r\n"
    at_cmd_bytes = bytes(at_cmd, 'utf-8')
    sentBytes = uart.write(at_cmd_bytes)

    if debug_mode:
        data = b''
        isDone = False
        while not isDone:
            startTime = ticks_ms()
            while not uart.any() and ticks_diff(ticks_ms(), startTime) < wait_time:
                sleep(0.1)
            if ticks_diff(ticks_ms(), startTime) > wait_time:
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


def startModem():
    modemPowerKeyPin = 15
    MODEM_RESET_PIN = 16
    BOARD_BAT_ADC_PIN = 4
    modemDTRPin = 7
    MODEM_RX_PIN = 18
    MODEM_TX_PIN = 17
    BAUDRATE = 115200

    # Initializes the UART
    uartModem = UART(1, BAUDRATE, tx=MODEM_TX_PIN, rx=MODEM_RX_PIN, flow=0, timeout_char=20)
    uartModem.init(BAUDRATE, bits=8, parity=None, stop=1)

    # uartCmux1 = UART(2, BAUDRATE, tx=5, rx=3, flow=0, timeout_char=20)
    # uartCmux1.init(BAUDRATE, bits=8, parity=None, stop=1)


    # Reset A7608
    modemReset = Pin(MODEM_RESET_PIN, Pin.OUT)
    modemReset.off()
    sleep(2)
    modemReset.on()
    sleep(2)

    modemDTR = Pin(modemDTRPin, Pin.OUT)
    modemDTR.on()
    sleep(0.5)
    modemDTR.off()

    # Power on the modem respecting the timing for it
    # (https://microchip.ua/simcom/LTE/A76xx/A7602/A7602E-H&A7608SA-H%20Hardware%20Design_V1.00.pdf on page 29)
    modemPowerKey = Pin(modemPowerKeyPin, Pin.OUT)
    modemPowerKey.off()
    sleep(0.5)
    modemPowerKey.on()
    sleep(1)
    modemPowerKey.off()

    # Wait for AT commands to be responsive from A7608 chip
    while not send_at(uartModem, "AT", wait_time=1):
        sleep(1)

    return uartModem
