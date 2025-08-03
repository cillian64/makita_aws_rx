import bluetooth
import time
from micropython import const
from machine import Pin
import time


pin_pico_led = machine.Pin("LED", machine.Pin.OUT)
pin_led      = machine.Pin(15, machine.Pin.OUT)
pin_relay    = machine.Pin(10, machine.Pin.OUT)
pin_sw       = machine.Pin(14, machine.Pin.IN)

# Timeouts, all in milliseconds
TIMEOUT_TOOL_SEEN = 5000
# Doubles as a run-on timer
TIMEOUT_TOOL_ACTIVE = 2000


class BLEScanner:
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
    def __init__(self, ble, receiver):
        self._ble = ble
        self._ble.active(True)  # Activate BLE radio
        self._ble.irq(self._irq)  # Set IRQ handler
        self.receiver = receiver

        self._scan_callback = None

    def _irq(self, event, data):
        """ Callback for interrupts from the BTLE library """

        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data

            # print(f"Scan result: addr_type {addr_type}, addr {addr.hex()}, "
            #       f"adv_type {adv_type}, rssi {rssi}, "
            #       f"adv_data {adv_data.hex()}")

            adv_data_str = str(adv_data.hex())
            if adv_data_str.startswith("020106"):
                remain = adv_data_str[6:]
                if remain == self.AWS_POWERON:
                    # Don't count tool as "seen" if the AWS chip is off.
                    pass
                elif remain == self.AWS_INITIALISED:
                    self.receiver.boop_tool_seen()
                elif remain == self.AWS_WAITING:
                    self.receiver.boop_tool_seen()
                elif remain == self.AWS_TRIGGER:
                    self.receiver.boop_tool_active()
                elif remain == self.AWS_PAIRING:
                    # Pairing is unimplemented
                    self.receiver.boop_tool_seen()
                elif remain == self.AWS_UNPAIR:
                    # Pairing is unimplemented
                    self.receiver.boop_tool_seen()

        elif event == _IRQ_SCAN_DONE:
            print("Scan done")
            if self._scan_callback:
                self._scan_callback()

    def scan(self, callback=None):
        """ Start a BTLE scan.  Callback is called when scan finishes."""
        print("scan: starting scan")
        self._scan_callback = callback

        # In theory this should scan indefinitely so we don't need the
        # scan-completed callback and loop
        self._ble.gap_scan(0, 100000, 100000)


class AwsReceiver:
    def __init__(self):
        # time.ticks_ms() when a tool was last seen, or None if never seen
        self.time_tool_seen = None

        # time.ticks_ms() when a tool was last active, or None if never active
        self.time_tool_active = None

        # Override switch
        self.override = False
        self.override_sw_state = 1

        # State for LED flash patterns
        self.led_ticker = 0

    def boop_tool_seen(self):
        """ Call this when a tool is seen """
        self.time_tool_seen = time.ticks_ms()

    def boop_tool_active(self):
        """ Call this when a tool is active """
        self.time_tool_seen = time.ticks_ms()
        self.time_tool_active = time.ticks_ms()

    def tick(self):
        """ Look at inputs and set outputs. LED flashing patterns assume that
        this function will be called at a constant 200ms interval. """

        self.led_ticker += 1

        # Note that override switch is active-low.
        if self.override_sw_state and not pin_sw.value():
            self.override = not self.override
            print("Override set to {}".format(self.override))
        self.override_sw_state = pin_sw.value()

        if self.override:
            pin_pico_led.on()
            pin_relay.on()

            # Override: LED constant on
            pin_led.on()
            return

        now = time.ticks_ms()
        time_since_seen = time.ticks_diff(now, self.time_tool_seen)
        time_since_active = time.ticks_diff(now, self.time_tool_active)

        if time_since_active < TIMEOUT_TOOL_ACTIVE:
            # Active stuff
            #print("State: active")
            pin_pico_led.on()
            pin_relay.on()

            # Tool active: LED constant on
            pin_led.on()
        elif time_since_seen < TIMEOUT_TOOL_SEEN:
            # Seen stuff
            #print("State: seen")
            pin_pico_led.off()
            pin_relay.off()

            # Tool seen pattern: 25% on 75% off with 800ms period
            if self.led_ticker % 4 == 0:
                pin_led.on()
            else:
                pin_led.off()
        else:
            # Idle stuff
            #print("State: idle")
            pin_pico_led.off()
            pin_relay.off()

            # Idle pattern: 10% on, 90% off, with 2000ms period
            if self.led_ticker % 10 == 0:
                pin_led.on()
            else:
                pin_led.off()


if __name__ == "__main__":
    ble = bluetooth.BLE()
    receiver = AwsReceiver()
    scanner = BLEScanner(ble, receiver)

    # Input switch seems to do weird things at startup
    time.sleep_ms(2000)

    while(True):
        scanning = True

        def scan_finished_cb():
            global scanning
            scanning = False

        scanner.scan(callback=scan_finished_cb)

        while scanning:
            # A constant 200ms tick is really convenient but does mean the
            # button isn't very responsive.  A really hacky gross (but simple)
            # way to fix this is just to abort the sleep if the button is
            # pressed
            for _ in range(10):
                if not pin_sw.value():  # Switch is active-low
                    break
                time.sleep_ms(20)
            receiver.tick()
