# cmux

This library was developed and tested on an ESP32 S3 connected to a SIMCom A7608SA-H via UART. It creates
a class (cmux) to handle 4 virtual UARTs (multiplexed channels on the physical UART), plus a control channel.
Each virtual UART can be used independently to send AT commands to the A7608SA-H, or to set a transparent data 
channel to stablish PPPoS network connection.
The PPP connection is currently not working because the VirtualUART class needs to be adjusted to emulate the physical 
UART required by the Micropython PPP service (work in progress and accepting collaboration from developers to complete 
it :-) )...

The cmux class was developed following the standard definitions from 3GPP TS 07.10 V7.2.0 specifications 
(https://www.3gpp.org/ftp/Specs/archive/07_series/07.10/), and adjusted to the SIMCom modems with the help of this 
document: https://microchip.ua/simcom/2G/Application%20Notes/SIM800%20Series_Multiplexer_Application%20Note_V1.04.pdf. 

Some modems can have small variations on these specifications, this lib was done for SIMCom A7608SA-H, and it could 
requiere small changes depending on the modem to be used.
Also it is implementing for now the basic functionalities to start the cmux protocol, open the control and virtual UART 
channels, and send AT commands on them (commands mode) or tranparently pass data over a channel (data mode).

In the example, the startModem funtion is used to setup the connection to the SIMCom A7608SA-H modem via the physical UART. 
This function has to be changed if a different modem is used.

The "pppUart" property of the cmux class was included just for testing/troubleshooting porpouse. Once the "ATD*99#" 
command is sent to stablish the data mode on a channel (let's say channel 1), a physical UART can be assigned to this 
property like this:

'
cmux7608.channels[1].pppUart = uartCmux1
'

where "uartCmux1" is another physical UART configured in the ESP32. That UART can be connected to a UART on another ESP32 where 
it will be used to set the PPP network connection like this:

'
ppp = network.PPP(<The physical UART of the 2nd ESP32>)
ppp.active(True)
ppp.connect()
'

Try it, enjoy it and if you think that you can help to finish the VirtualUART class so it can be correctly used by 
the network.ppp service, please let me know. Your collaboration on this is absolutely welcome :-)
