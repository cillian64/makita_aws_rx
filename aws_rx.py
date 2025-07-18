import bluetooth
import time
from micropython import const
from machine import Pin

# The interrupts we receive from the bluetooth library
_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)

# From https://en.wikipedia.org/wiki/Makita_AWS#Implementation
AWS_POWERON     = "05 FF FC 33 03 05".replace(" ", "").lower()
AWS_INITIALISED = "05 FF FD 33 06 06".replace(" ", "").lower()
AWS_WAITING     = "05 FF FC 33 03 06".replace(" ", "").lower()
AWS_TRIGGER     = "05 FF FD AA 03 06".replace(" ", "").lower()
AWS_PAIRING     = "05 FF FF 33 0C 07".replace(" ", "").lower()
AWS_UNPAIR      = "05 FF EF 33 18 08".replace(" ", "").lower()

led = machine.Pin("LED", machine.Pin.OUT)

class BLEScanner:
    def __init__(self, ble):
        self._ble = ble
        self._ble.active(True)  # Activate BLE radio
        self._ble.irq(self._irq)  # Set IRQ handler

        self._scan_callback = None

    def _irq(self, event, data):
        """ Callback for interrupts from the BTLE library """

        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data

            # print(f"Scan result: addr_type {addr_type}, addr {addr.hex()}, adv_type {adv_type}, rssi {rssi}, adv_data {adv_data.hex()}")

            adv_data_str = str(adv_data.hex())
            if adv_data_str.startswith("020106"):
                remain = adv_data_str[6:]
                if remain == AWS_POWERON:
                    print("AWS poweron")
                    led.off()
                elif remain == AWS_INITIALISED:
                    print("AWS initialised")
                    led.off()
                elif remain == AWS_WAITING:
                    print("AWS waiting")
                    led.off()
                elif remain == AWS_TRIGGER:
                    print("AWS trigger")
                    led.on()
                elif remain == AWS_PAIRING:
                    print("AWS pairing")
                    led.off()
                elif remain == AWS_UNPAIR:
                    print("AWS unpair")
                    led.off()

        elif event == _IRQ_SCAN_DONE:
            print("Scan done")
            if self._scan_callback:
                self._scan_callback()

    def scan(self, callback=None):
        """ Start a BTLE scan.  Callback is called when scan finishes."""
        print("scan: starting scan")
        self._scan_callback = callback

        # In theory this should scan indefinitely so we don't need the callback and loop
        self._ble.gap_scan(0, 100000, 100000)


if __name__ == "__main__":
    ble = bluetooth.BLE()
    scanner = BLEScanner(ble)
    while(True):
        scanning = True

        def scan_finished_cb():
            global scanning
            scanning = False

        scanner.scan(callback=scan_finished_cb)

        while scanning:
            time.sleep_ms(100)
