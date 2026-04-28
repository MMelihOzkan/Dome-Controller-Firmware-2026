from machine import Pin, SoftI2C, I2C ,WDT
from mcp23017 import MCP23017
import ssd1306
import time
import rp2
import ujson as json

SETTINGS_FILE = "settings.txt"

# default values
settings = {
    "pre_led": 20,      # ms (LED warmup before focus)
    "focus": 100,       # ms (focus hold before shutter)
    "shutter": 70,      # ms (shutter pulse)
    "exposure": 520,    # ms (LED ON after shutter)
    "between": 500      # ms (delay between shots)
}

#Wait until initilazie
time.sleep(2)
#Set Oled I2C
i2c_oled = SoftI2C(scl=Pin(3), sda=Pin(2))
oled_width = 128
oled_height = 64
oled = ssd1306.SSD1306_I2C(oled_width, oled_height, i2c_oled)

#Set MCP Reset Pin
mcp_reset = Pin(4, Pin.OUT)
mcp_reset.value(1)
time.sleep(0.1)

#CAMERA
#Focus
cam_focus = Pin(14, Pin.OUT)
cam_focus.value(0)
#Shutter
cam_shutter = Pin(15, Pin.OUT)
cam_shutter.value(0)

mcp = None
i2c_exp = None
addr = None

#MENU
menu_items = [
    "Start RTI",
    "Tests",
    "Settings"
]

selected = 0
btn_up = Pin(7, Pin.IN, Pin.PULL_UP)
btn_down = Pin(5, Pin.IN, Pin.PULL_UP)
btn_sel = Pin(6, Pin.IN, Pin.PULL_UP)

# WATCHDOG
ENABLE_WDT = True

if ENABLE_WDT:
    from machine import WDT
    wdt = WDT(timeout=5000)
else:
    wdt = None

def feed_watchdog():
    if wdt is not None:
        try:
            wdt.feed()
        except Exception as e:
            print("WDT feed error:", e) 

#Load settings from settings.txt
def load_settings():
    global settings
    try:
        with open(SETTINGS_FILE, "r") as f:
            loaded = json.load(f)

        for key in settings:
            settings[key] = loaded.get(key, settings[key])

        print("Settings loaded:", settings)

    except Exception as e:
        print("No settings file, using defaults:", e)
        
def ensure_settings_file():
    try:
        with open(SETTINGS_FILE, "r"):
            pass
    except:
        save_settings()

#Save settings
def save_settings():
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)
    print("Settings saved:", settings)

def settings_menu():
    global settings

    items = [
        "PRE LED",
        "FOCUS",
        "SHUTTER",
        "EXPOSURE",
        "BETWEEN",
        "SAVE & EXIT"
    ]
    index = 0

    while True:
        feed_watchdog()
        oled.fill(0)
        oled.text("SETTINGS", 0, 0)

        start = 0
        if index >= 4:
            start = index - 3
        end = min(start + 5, len(items))

        for i in range(start, end):
            item = items[i]
            prefix = ">" if i == index else " "

            if item == "PRE LED":
                val = "{}ms".format(settings["pre_led"])
            elif item == "FOCUS":
                val = "{}ms".format(settings["focus"])
            elif item == "SHUTTER":
                val = "{}ms".format(settings["shutter"])
            elif item == "EXPOSURE":
                val = "{}ms".format(settings["exposure"])
            elif item == "BETWEEN":
                val = "{}ms".format(settings["between"])
            else:
                val = ""

            text = "{}{}{}".format(prefix, item, ":" + val if val else "")
            oled.text(text, 0, 10 + (i - start) * 10)

        oled.show()

        if not btn_up.value():
            index = (index - 1) % len(items)
            wait_release(btn_up)
            time.sleep_ms(120)

        elif not btn_down.value():
            index = (index + 1) % len(items)
            wait_release(btn_down)
            time.sleep_ms(120)

        elif not btn_sel.value():
            wait_release(btn_sel)
            time.sleep_ms(120)

            if items[index] == "SAVE & EXIT":
                debug_screen("Saving...")
                save_settings()
                time.sleep(0.5)
                return

            adjust_value(items[index])

        time.sleep_ms(50)
        
def wait_ms_with_stop(duration_ms, reset_mcp=False):
    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < duration_ms:
        feed_watchdog()
        if handle_stop(reset_mcp=reset_mcp):
            return False
        time.sleep_ms(10)
    return True

def tests_menu():
    items = [
        "Reset MCP",
        "I2C Scan",
        "Test Camera",
        "Quadrant 1",
        "Quadrant 2",
        "Quadrant 3",
        "Quadrant 4",
        "All Quadrants",
        "Back"
    ]
    index = 0

    while True:
        feed_watchdog()
        oled.fill(0)
        oled.text("TESTS", 0, 0)

        # show up to 5 items at once
        start = 0
        if index >= 4:
            start = index - 3
        end = min(start + 5, len(items))

        for i in range(start, end):
            prefix = ">" if i == index else " "
            oled.text(prefix + items[i], 0, 10 + (i - start) * 10)

        oled.show()

        if not btn_up.value():
            index = (index - 1) % len(items)
            wait_release(btn_up)
            time.sleep_ms(120)

        elif not btn_down.value():
            index = (index + 1) % len(items)
            wait_release(btn_down)
            time.sleep_ms(120)

        elif not btn_sel.value():
            wait_release(btn_sel)
            time.sleep_ms(120)

            if items[index] == "Reset MCP":
                testMCPReset()
            elif items[index] == "I2C Scan":
                scanI2C()
            elif items[index] == "Test Camera":
                test_camera()
            elif items[index] == "Quadrant 1":
                quadrant_test(0, 1)
            elif items[index] == "Quadrant 2":
                quadrant_test(2, 3)
            elif items[index] == "Quadrant 3":
                quadrant_test(4, 5)
            elif items[index] == "Quadrant 4":
                quadrant_test(6, 7)
            elif items[index] == "All Quadrants":
                all_quadrant_tests()
            elif items[index] == "Back":
                return

        time.sleep_ms(50)

def adjust_value(item):
    global settings

    while True:
        feed_watchdog()
        oled.fill(0)

        if item == "PRE LED":
            val = "{}ms".format(settings["pre_led"])
        elif item == "FOCUS":
            val = "{}ms".format(settings["focus"])
        elif item == "SHUTTER":
            val = "{}ms".format(settings["shutter"])
        elif item == "EXPOSURE":
            val = "{}ms".format(settings["exposure"])
        elif item == "BETWEEN":
            val = "{}ms".format(settings["between"])
        else:
            val = "?"

        oled.text("Adjust " + item, 0, 0)
        oled.text(val, 0, 20)
        oled.text("UP/DN change", 0, 40)
        oled.text("SEL exit", 0, 50)
        oled.show()

        if not btn_up.value():
            if item == "PRE LED":
                settings["pre_led"] += 10
            elif item == "FOCUS":
                settings["focus"] += 10
            elif item == "SHUTTER":
                settings["shutter"] += 10
            elif item == "EXPOSURE":
                settings["exposure"] += 10
            elif item == "BETWEEN":
                settings["between"] += 10
            wait_release(btn_up)

        elif not btn_down.value():
            if item == "PRE LED":
                settings["pre_led"] = max(0, settings["pre_led"] - 10)
            elif item == "FOCUS":
                settings["focus"] = max(0, settings["focus"] - 10)
            elif item == "SHUTTER":
                settings["shutter"] = max(0, settings["shutter"] - 10)
            elif item == "EXPOSURE":
                settings["exposure"] = max(0, settings["exposure"] - 10)
            elif item == "BETWEEN":
                settings["between"] = max(0, settings["between"] - 10)
            wait_release(btn_down)

        elif not btn_sel.value():
            wait_release(btn_sel)
            return

        time.sleep_ms(50)
        
#Take picture
def take_pic(step=None, total_steps=None, a=None, b=None, led_on=False, run_start_ms=None):
    cam_focus.value(1)
    cam_shutter.value(0)

    if step is not None and run_start_ms is not None:
        show_rti_status(step, total_steps, a, b, led_on, True, False, run_start_ms)

    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < settings["focus"]:
        feed_watchdog()
        if not btn_sel.value():
            cam_focus.value(0)
            cam_shutter.value(0)
            wait_release(btn_sel)
            return False
        time.sleep_ms(10)

    cam_shutter.value(1)

    if step is not None and run_start_ms is not None:
        show_rti_status(step, total_steps, a, b, led_on, True, True, run_start_ms)

    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < settings["shutter"]:
        feed_watchdog()
        if not btn_sel.value():
            cam_focus.value(0)
            cam_shutter.value(0)
            wait_release(btn_sel)
            return False
        time.sleep_ms(10)

    cam_shutter.value(0)
    cam_focus.value(0)

    if step is not None and run_start_ms is not None:
        show_rti_status(step, total_steps, a, b, led_on, False, False, run_start_ms)

    time.sleep_ms(50)
    feed_watchdog()
    return True

def test_camera():
    debug_screen("Testing camera...")
    if take_pic():
        debug_screen("Camera test", "done")
    else:
        debug_screen("Camera test", "stopped")
    time.sleep(1)

#Draw Menu
def draw_menu():
    oled.fill(0)
    for i, item in enumerate(menu_items):
        prefix = ">" if i == selected else " "
        oled.text(prefix + item, 0, i * 10)
    oled.show()
    
def wait_release(button):
    while not button.value():
        time.sleep_ms(10)

draw_menu()

#Debug text
def debug_screen(*lines):
    oled.fill(0)  # clear screen
    y = 0
    for line in lines:
        oled.text(str(line), 0, y)
        y += 10
    oled.show()

#Set mcp pins
def safe_set(port, pin, val):
    global mcp, i2c_exp

    if mcp is None:
        print("safe_set: MCP not initialized")
        debug_screen("MCP NOT READY")
        return False

    try:
        mcp.set_pin(port, pin, val)
        return True

    except OSError as e:
        addrs = i2c_exp.scan() if i2c_exp is not None else []
        msg1 = "{}{}={}".format(port, pin, val)
        debug_screen("EIO!", msg1, str([hex(a) for a in addrs])[:16])
        print("EIO on", msg1, "scan:", [hex(a) for a in addrs], "err:", e)
        return False

    except Exception as e:
        print("safe_set error:", e)
        debug_screen("MCP ERROR", str(e)[:16])
        return False


#Set MCP Expander I2C
try:
    i2c_exp = I2C(0, sda=Pin(0), scl=Pin(1))
    addresses = i2c_exp.scan()
    print("I2C scan:", [hex(a) for a in addresses])

    if not addresses:
        debug_screen("MCP Not Found", "I2C scan empty")
        raise RuntimeError("No I2C devices")

    addr = 0x20 if 0x20 in addresses else addresses[0]

    mcp = MCP23017(i2c_exp, addr=addr)
    print("Using MCP23017 at", hex(addr))
    debug_screen("MCP Found", hex(addr))

    # Set all pins as outputs
    mcp.set_port_dir('A', 0x00)
    mcp.set_port_dir('B', 0x00)
    debug_screen("MCP Ready", "A/B outputs")

except Exception as e:
    print("MCP init error:", e)
    debug_screen("MCP ERROR", str(e)[:16])

#Opening screen
load_settings()
ensure_settings_file()
oled.text('RTI Prototype', 12, 30)
oled.show()
time.sleep(2)
oled.fill(0)

# Scan MCP / expander bus
def scanI2C():

    # Scan expander bus (for MCP)
    try:
        addrs = i2c_exp.scan()
        mcp_addrs = [a for a in addrs if 0x20 <= a <= 0x27]
        mcp_hex = [hex(a) for a in mcp_addrs]

        print("MCP I2C scan:", mcp_hex)

    except Exception as e:
        mcp_addrs = []
        mcp_hex = []
        print("MCP I2C scan error:", e)

    # Scan OLED bus
    try:
        oled_addrs = i2c_oled.scan()
        oled_hex = [hex(a) for a in oled_addrs]

        print("OLED I2C scan:", oled_hex)

    except Exception as e:
        oled_addrs = []
        oled_hex = []
        print("OLED I2C scan error:", e)

    # Display on OLED
    line1 = "MCP:" + (" ".join(mcp_hex) if mcp_hex else "none")
    line2 = "OLED:" + (" ".join(oled_hex) if oled_hex else "none")

    debug_screen(
        "I2C SCAN",
        line1[:16],
        line2[:16],
    )

    time.sleep(2)

    return {
        "mcp_addrs": mcp_addrs,
        "oled_addrs": oled_addrs,
    }

#Connect to MCP
def connectMCP():
    global mcp, addr, i2c_exp

    i2c_bus_recover(1, 0)

    # Recreate I2C peripheral
    i2c_exp = I2C(0, sda=Pin(0), scl=Pin(1))

    addresses = i2c_exp.scan()
    print("I2C scan:", [hex(a) for a in addresses])

    if not addresses:
        print("No I2C devices found on i2c_exp")
        return False

    addr = 0x20 if 0x20 in addresses else addresses[0]
    mcp = MCP23017(i2c_exp, addr=addr)

    print("Using MCP23017 at", hex(addr))

    # Re-init expander after reset
    mcp.set_port_dir('A', 0x00)
    mcp.set_port_dir('B', 0x00)

    # Ensure cached state matches chip state
    mcp.porta = 0x00
    mcp.portb = 0x00
    mcp.write(mcp.GPIOA, 0x00)
    mcp.write(mcp.GPIOB, 0x00)

    return True
    
#I2C bus recover
def i2c_bus_recover(scl_pin=3, sda_pin=2):
    scl = Pin(scl_pin, Pin.OUT, value=1)
    sda = Pin(sda_pin, Pin.IN)

    for _ in range(9):
        if sda.value() == 1:
            break
        scl.value(0)
        time.sleep_us(10)
        scl.value(1)
        time.sleep_us(10)

    # STOP
    sda_out = Pin(sda_pin, Pin.OUT, value=0)
    time.sleep_us(10)
    scl.value(1)
    time.sleep_us(10)
    sda_out.value(1)
    time.sleep_us(10)

#MCP reset test
def testMCPReset():
    debug_screen("Test MCP Reset...")
    print("Reset low")
    mcp_reset.value(0)
    time.sleep(1)

    print("Reset high")
    mcp_reset.value(1)
    time.sleep(1)

    ok = connectMCP()
    print("Reconnect:", ok)
    debug_screen("MCP Reset: "+ str(ok))
    return ok

def all_leds_off():
    global mcp
    if mcp is None:
        print("all_leds_off: MCP not initialized")
        return False

    try:
        mcp.write(mcp.GPIOA, 0x00)
        mcp.write(mcp.GPIOB, 0x00)
        mcp.porta = 0x00
        mcp.portb = 0x00
        return True
    except Exception as e:
        print("all_leds_off error:", e)
        return False
        
def stop_requested():
    return not btn_sel.value()

def handle_stop(reset_mcp=False):
    if stop_requested():
        wait_release(btn_sel)
        emergency_stop(reset_mcp=reset_mcp)
        return True
    return False

def emergency_stop(reset_mcp=False):
    debug_screen("STOPPING...", "LEDs OFF")

    all_leds_off()
    cam_focus.value(0)
    cam_shutter.value(0)

    if reset_mcp:
        mcp_reset.value(0)
        time.sleep_ms(50)
        mcp_reset.value(1)
        time.sleep_ms(50)
        connectMCP()

    debug_screen("STOPPED")
    time.sleep_ms(500)
    
    
def quadrant_test(cha_1, cha_2, duration_led=None):
    global mcp

    if mcp is None:
        debug_screen("MCP NOT READY")
        time.sleep(2)
        return
    if duration_led is None:
        duration_led = settings["exposure"]

    total_steps = 16
    step = 0

    for a in (cha_1, cha_2):
        for b in range(8):
            step += 1

            debug_screen(
                "Quadrant test",
                "A{} B{}".format(a, b),
                "{}/{}".format(step, total_steps),
                "SEL=STOP"
            )

            safe_set('A', a, 1)
            safe_set('B', b, 1)

            start = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start) < int(duration_led):
                feed_watchdog()
                if handle_stop(reset_mcp=False):
                    return
                time.sleep_ms(20)

            safe_set('A', a, 0)
            safe_set('B', b, 0)

            if handle_stop(reset_mcp=False):
                return

    all_leds_off()
    debug_screen("OK", "Quadrant done")
    time.sleep(1)
    
def all_quadrant_tests(duration_led=None):
    global mcp

    if mcp is None:
        debug_screen("MCP NOT READY")
        time.sleep(2)
        return
    if duration_led is None:
        duration_led = settings["exposure"]

    total_steps = 64
    step = 0

    for pair in ((0, 1), (2, 3), (4, 5), (6, 7)):
        for a in pair:
            for b in range(8):
                step += 1

                debug_screen(
                    "All quadrants",
                    "A{} B{}".format(a, b),
                    "{}/{}".format(step, total_steps),
                    "SEL=STOP"
                )

                safe_set('A', a, 1)
                safe_set('B', b, 1)

                start = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), start) < int(duration_led):
                    feed_watchdog()
                    if handle_stop(reset_mcp=False):
                        return
                    time.sleep_ms(20)

                safe_set('A', a, 0)
                safe_set('B', b, 0)

                if handle_stop(reset_mcp=False):
                    return

    all_leds_off()
    debug_screen("OK", "All done")
    time.sleep(1)
    
def show_rti_status(step, total_steps, a, b, led_on, focus_on, shutter_on, run_start_ms):
    elapsed_ms = time.ticks_diff(time.ticks_ms(), run_start_ms)
    elapsed_s = elapsed_ms // 1000

    if step > 0:
        avg_step_ms = elapsed_ms / step
        remaining_ms = int((total_steps - step) * avg_step_ms)
    else:
        remaining_ms = 0

    remaining_s = remaining_ms // 1000

    oled.fill(0)

    # Title
    oled.text("RTI RUN", 0, 0)

    # Progress
    oled.text("{}/{}".format(step, total_steps), 0, 10)

    # Current LED position
    oled.text("A{} B{}".format(a, b), 0, 20)

    # States
    oled.text("L:{} F:{} S:{}".format(
        "1" if led_on else "0",
        "1" if focus_on else "0",
        "1" if shutter_on else "0"
    ), 0, 30)

    # Timing
    oled.text("EL:{}s".format(elapsed_s), 0, 40)
    oled.text("ETA:{}s".format(remaining_s), 0, 50)

    # STOP hint
    oled.text("SEL=STP", 64, 50)

    oled.show()

#Full Led simulation
def rti_simulation():
    global mcp
    if mcp is None:
        debug_screen("MCP NOT READY")
        time.sleep(2)
        return
    total_steps = 64
    step = 0
    run_start_ms = time.ticks_ms()

    pre_on_delay_ms = settings["pre_led"]
    focus_lag_ms = settings["focus"]
    shutter_actuation_ms = settings["shutter"]
    exposure_ms = settings["exposure"]
    between_shot_delay_ms = settings["between"]

    for a in range(8):
        for b in range(8):
            step += 1

            # LED ON
            safe_set('A', a, 1)
            safe_set('B', b, 1)
            show_rti_status(step, total_steps, a, b, True, False, False, run_start_ms)

            # LED warmup
            if not wait_ms_with_stop(pre_on_delay_ms):
                all_leds_off()
                return

            # Focus ON
            cam_focus.value(1)
            cam_shutter.value(0)
            show_rti_status(step, total_steps, a, b, True, True, False, run_start_ms)

            # Focus lag
            if not wait_ms_with_stop(focus_lag_ms):
                all_leds_off()
                cam_focus.value(0)
                cam_shutter.value(0)
                return

            # Shutter ON
            cam_shutter.value(1)
            show_rti_status(step, total_steps, a, b, True, True, True, run_start_ms)

            # Shutter pulse
            if not wait_ms_with_stop(shutter_actuation_ms):
                all_leds_off()
                cam_focus.value(0)
                cam_shutter.value(0)
                return

            # Shutter OFF, Focus OFF
            cam_shutter.value(0)
            cam_focus.value(0)
            show_rti_status(step, total_steps, a, b, True, False, False, run_start_ms)

            # Exposure while LED still ON
            if not wait_ms_with_stop(exposure_ms):
                all_leds_off()
                return

            # LED OFF
            safe_set('A', a, 0)
            safe_set('B', b, 0)
            show_rti_status(step, total_steps, a, b, False, False, False, run_start_ms)

            # Between shots
            if not wait_ms_with_stop(between_shot_delay_ms):
                all_leds_off()
                return

    all_leds_off()
    cam_focus.value(0)
    cam_shutter.value(0)
    debug_screen("OK", "RTI done")
    time.sleep(1)

#Menu Logic
if mcp is not None:
    all_leds_off()
draw_menu()
while True:
    feed_watchdog()

    if not btn_up.value():
        selected -= 1
        if selected < 0:
            selected = len(menu_items) - 1
        draw_menu()
        wait_release(btn_up)
        time.sleep_ms(120)

    elif not btn_down.value():
        selected += 1
        if selected >= len(menu_items):
            selected = 0
        draw_menu()
        wait_release(btn_down)
        time.sleep_ms(120)

    elif not btn_sel.value():
        wait_release(btn_sel)
        time.sleep_ms(120)

        if selected == 0:
            rti_simulation()
        elif selected == 1:
            tests_menu()
        elif selected == 2:
            settings_menu()

        draw_menu()

    time.sleep_ms(50)


