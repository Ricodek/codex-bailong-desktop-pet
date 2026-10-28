"""Analytic critically damped motion, preserving velocity when direction reverses."""
import math


class Spring:
    def __init__(self, value=0., frequency=22.):
        self.value=float(value);self.velocity=0.;self.target=float(value)
        self.frequency=frequency

    def advance(self, seconds):
        t=max(0.,min(float(seconds),.1))
        d=self.value-self.target;w=self.frequency;c=self.velocity+w*d
        decay=math.exp(-w*t)
        self.value=self.target+(d+c*t)*decay
        self.velocity=(self.velocity-w*c*t)*decay
        if abs(self.value-self.target)<.0007 and abs(self.velocity)<.01:
            self.value=self.target;self.velocity=0.
        return self.value

    @property
    def settled(self):
        return self.value==self.target and self.velocity==0.
