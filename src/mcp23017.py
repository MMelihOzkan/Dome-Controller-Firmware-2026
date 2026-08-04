class MCP23017:
    IODIRA = 0x00
    IODIRB = 0x01
    GPIOA  = 0x12
    GPIOB  = 0x13
    GPPUA  = 0x0C
    GPPUB  = 0x0D

    def __init__(self, i2c, addr):
        self.i2c = i2c
        self.addr = addr
        self.porta = 0x00
        self.portb = 0x00

    def write(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    def read(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def set_port_dir(self, port, mask):
        if port == 'A':
            self.write(self.IODIRA, mask)
        else:
            self.write(self.IODIRB, mask)

    def set_pin(self, port, pin, value):
        if not (0 <= pin <= 7):
            raise ValueError("pin must be 0–7")

        if port == 'A':
            if value:
                self.porta |= (1 << pin)
            else:
                self.porta &= ~(1 << pin)
            self.write(self.GPIOA, self.porta)

        elif port == 'B':
            if value:
                self.portb |= (1 << pin)
            else:
                self.portb &= ~(1 << pin)
            self.write(self.GPIOB, self.portb)

        else:
            raise ValueError("port must be 'A' or 'B'")
