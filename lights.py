#!/usr/bin/env python3
# NeoPixel library strandtest example
# Author: Tony DiCola (tony@tonydicola.com)
#
# Direct port of the Arduino NeoPixel library strandtest example.  Showcases
# various animations on a strip of NeoPixels.

import time
import random
from rpi_ws281x import Adafruit_NeoPixel, Color, RGBW
from serial import Serial
from zlib import crc32
import argparse

# LED strip configuration:
LED_COUNT      = 432     # Number of LED pixels.
LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
#LED_PIN        = 10      # GPIO pin connected to the pixels (10 uses SPI /dev/spidev0.0).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 10      # DMA channel to use for generating a signal (try 10)
LED_BRIGHTNESS = 90      # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

class Ring:
    global_offset:int = 0

    def __init__(self, strip: Adafruit_NeoPixel, pixel_count: int, reverse=False):
        self.strip = strip
        self.pixel_count = pixel_count
        self.offset = Ring.global_offset
        self.reverse = reverse
        Ring.global_offset += pixel_count

    def render(self, color: RGBW):
        for i in range(self.pixel_count):
            self.strip.setPixelColor(self.offset + i, color)

    def setPixelColor(self, i: int, color: RGBW):
        i = self.getOffset(i)
        self.strip.setPixelColor(i, color)

    def getOffset(self, i: int) -> int:
        if self.reverse:
            return self.offset + self.pixel_count - i - 1
        else:
            return self.offset + i

    def numPixels(self):
        return self.pixel_count
    
    def show(self):
        return self.strip.show()
    
    def darken(self, factor=.9):
        for i in range(self.pixel_count):
            i = self.getOffset(i)
            color = RGBW(self.strip.getPixelColor(i))
            self.strip.setPixelColor(i, Color(int(color.r * factor), int(color.g * factor), int(color.b * factor), int(color.w * factor)))

# Define functions which animate LEDs in various ways.
def colorWipe(strip, color, wait_ms=1):
    """Wipe color across display a pixel at a time."""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms/1000.0)

def theaterChase(strip, color, wait_ms=50, iterations=10):
    """Movie theater light style chaser animation."""
    for j in range(iterations):
        for q in range(3):
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, color)
            strip.show()
            time.sleep(wait_ms/1000.0)
            for i in range(0, strip.numPixels(), 3):
                strip.setPixelColor(i+q, 0)

def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    pos %= 256
    if pos < 85:
        return Color(pos * 3, 255 - pos * 3, 0)
    elif pos < 170:
        pos -= 85
        return Color(255 - pos * 3, 0, pos * 3)
    else:
        pos -= 170
        return Color(0, pos * 3, 255 - pos * 3)


def firefly_strips(strips, show, iterations=4):
    for j in range(256*iterations):
        for i, strip in enumerate(strips):
            strip.darken(factor=.8)
            for n in range(int(strip.numPixels() / 10) + 1):
                idx = random.randrange(0, strip.numPixels())
                strip.setPixelColor(idx, wheel(j + 10 * i + n * 2))
        show()

def darken_circle_strips(strips, show, iterations=4):
    for j in range(256*iterations):
        for i, strip in enumerate(strips):
            strip.darken()
            strip.setPixelColor(j % strip.numPixels(), wheel(j + 10 * i))
        show()

def rainbow_strips(strips, show, wait_ms=0, iterations=4):
    for j in range(256*iterations):
        for s, strip in enumerate(strips):
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, wheel((i+j+10*s) & 255))
        show()
        time.sleep(wait_ms/1000.0)


def rainbow_cycle_strips(strips, show, wait_ms=0, iterations=4):
    """Draw rainbow that uniformly distributes itself across all pixels."""
    for j in range(256*iterations):
        for strip in strips:
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, wheel((int(i * 256 / strip.numPixels()) + j) & 255))
        show()
        time.sleep(wait_ms/1000.0)




def fade_to_black(strips, showfunc):
    for i in range(40):
        for strip in strips:
            strip.darken()
        showfunc()


colors = (Color(255, 0, 0), Color(0, 255, 0), Color(0, 0, 255))

def clear(strip: Adafruit_NeoPixel):
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))

    strip.show()

def clear_all(strips, show):
    for strip in strips:
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 0, 0))
    show()
        

class PixelExpander:
    def __init__(self, ser: Serial):
        self.ser = ser

    def make_frame_header(channel: int, record_type: int) -> bytes:
        return b'UPXL' + channel.to_bytes(1) + record_type.to_bytes(1)

    def make_channel_header(pixel_count: int) -> bytes:
        num_elements = 4 # RGBW
        red_index = 1
        green_index = 0
        blue_index = 2
        white_index = 3
        color_index = red_index | green_index << 2 | blue_index << 4 | white_index << 6
        return num_elements.to_bytes(1) + color_index.to_bytes(1) + pixel_count.to_bytes(2, 'little')

    def writeMessage(self, data: bytes):
        crc = crc32(data)
        msg = data+crc.to_bytes(4, 'little')
        #print(crc)
        ser.write(msg)
        #print(len(msg), msg)

    def write_pixels(self, channel, pixeldata):
        header = PixelExpander.make_frame_header(channel, 1)
        chan_header = PixelExpander.make_channel_header(int(len(pixeldata) / 4))
        self.writeMessage(header+chan_header+pixeldata)

    def draw(self):
        self.writeMessage(PixelExpander.make_frame_header(0xff, 2))

class ExpanderStrip:
    def __init__(self, expander: PixelExpander, channel: int, num_pixels: int):
        self.expander = expander
        self.channel = channel
        self.pixels = [Color(0, 0, 0, 0)] * num_pixels

    def numPixels(self):
        return len(self.pixels)
    
    def setPixelColor(self, n, color):
        """Set LED at position n to the provided 24-bit color value (in RGB order).
        """
        self.pixels[n] = color

    def darken(self, factor=0.9):
        for i in range(len(self.pixels)):
            color = self.pixels[i]
            self.pixels[i] = Color(int(color.r * factor), int(color.g * factor), int(color.b * factor), int(color.w * factor))

    def write_pixels(self):
        pixeldata = bytearray()
        for pixel in self.pixels:
            pixeldata.extend((pixel.r, pixel.g, pixel.b, pixel.w))
        self.expander.write_pixels(self.channel, pixeldata)

# Main program logic follows:
if __name__ == '__main__':
    # Process arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
    args = parser.parse_args()

    ser = Serial('/dev/ttyS0', baudrate=2000000)
    print(ser.name)

    pex = PixelExpander(ser)
    hoops = [ExpanderStrip(pex, chan, 150) for chan in range(16)]

    # for i in range(3):
    #     hoops[i].setPixelColor(i, wheel(i))
    #     hoops[i].write_pixels()
    # pex.draw()
    # print(len(hoops))
    #rainbow_cycle_strips([strip1, strip2])

    # while True: 
    #     for strip in hoops:
    #         strip.darken()
    #         strip.write_pixels()
    #     pex.draw()
    #     time.sleep(3.6 / 1000.0)

    def show():
        rings[0].show()
        for strip in hoops:
            strip.write_pixels()
        pex.draw()



    # Create NeoPixel object with appropriate configuration.
    strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
    # Intialize the library (must be called once before other functions).
    strip.begin()

    rings = [
        Ring(strip, 16, ),
        Ring(strip, 35, reverse=True),
        Ring(strip, 8), Ring(strip, 16, reverse=True), Ring(strip, 24),
        Ring(strip, 35),
        Ring(strip, 8), Ring(strip, 16, reverse=True),
        Ring(strip, 45),
        Ring(strip, 24, reverse=True),
        Ring(strip, 8), Ring(strip, 16, reverse=True),
        Ring(strip, 24),
        Ring(strip, 24, reverse=True), Ring(strip, 16), Ring(strip, 8, reverse=True),
        Ring(strip, 45),
        Ring(strip, 8, reverse=True), Ring(strip, 16),
        Ring(strip, 16, reverse=True),
        Ring(strip, 16), Ring(strip, 8, reverse=True),
    ]
    try:
        # for i, ring in enumerate(rings):
        #     ring.render(colors[i % len(colors)])
        # strip.show()
        # clear(strip)
        #time.sleep(20)

        print ('Press Ctrl-C to quit.')
        if not args.clear:
            print('Use "-c" argument to clear LEDs on exit')

        allstrips = rings+hoops

        clear_all(allstrips, show)
        while True:
            print('Fireflies')
            firefly_strips(allstrips, show)
            print('fade')
            fade_to_black(allstrips, show)
            clear_all(allstrips, show)

            print('Rainbow (rings)')
            rainbow_strips(allstrips, show)
            print('fade')
            fade_to_black(allstrips, show)
            clear_all(allstrips, show)

            print('Darken')
            darken_circle_strips(allstrips, show)
            print('fade')
            fade_to_black(allstrips, show)
            clear_all(allstrips, show)

            print('Rainbow cycle (rings)')
            rainbow_cycle_strips(allstrips, show)
            print('fade')
            fade_to_black(allstrips, show)
            clear_all(allstrips, show)

    except KeyboardInterrupt:
        clear_all(rings+hoops, show)
