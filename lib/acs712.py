from machine import Pin, ADC
import sys
import time
import math

class ACS712:
    def __init__(self):
        self._zero = 512
        self.sensitivity = 0.117
        self.ADC_SCALE = 4095
        self.VREF = 3.3
        self.DEFAULT_FREQUENCY = 50
        self._adc = ADC(Pin(34))

    def calibrate(self):
        acc = 0
        num_samples = 1000
        self._adc.atten(ADC.ATTN_11DB)
        self._adc.width(ADC.WIDTH_12BIT)
        for _ in range(num_samples):
            acc += self._adc.read()
            time.sleep(0.001)
        self._zero = acc / num_samples
        return self._zero

    @property
    def zeroPoint(self):
        return self._zero

    @zeroPoint.setter
    def zeroPoint(self, _zero):
        self._zero = _zero

    @property
    def sensitivity(self):
        return self._sensitivity

    @sensitivity.setter
    def sensitivity(self, value):
        self._sensitivity = value


    def getCurrentAC(self, freq=50):
        period = 100 / freq
        t_start = int(time.ticks_ms() / 100)
        Isum = 0
        msr_cnt = 0
        Inow = None;

        while ((time.ticks_ms() / 100) - t_start < period):
            Inow = self._adc.read() - self.zeroPoint
            Isum += Inow * Inow
            msr_cnt += 1
        pass  

        Irms = math.sqrt(Isum / msr_cnt) / self.ADC_SCALE * self.VREF / self.sensitivity
        if Irms < 0.5:
            return 0
        return round(Irms, 2)