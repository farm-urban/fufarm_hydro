import RPi.GPIO as GPIO
import time


P_SERVO = 22 # GPIO port
P_SERVO = 0 # GPIO port
fPWM = 50 # Hz (soft PWM方式，limit the freques)
a = 10
b = 2

def setup():
    global pwm
    #GPIO.setmode(GPIO.BOARD)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(P_SERVO, GPIO.OUT)
    pwm = GPIO.PWM(P_SERVO, fPWM)
    pwm.start(0)

def setDirection(direction):
    duty = a / 180 * direction + b
    pwm.ChangeDutyCycle(duty)
    print("direction =", direction, "-> duty =", duty)
    time.sleep(3)

print("starting")
setup()

#for i in range(0,110,10):
#  print(i)
#  pwm.ChangeDutyCycle(i)
#  time.sleep(2)
#  pwm.ChangeDutyCycle(0)
#
#pwm.stop()

#for direction in range(0, 181, 10):
#for direction in range(0, 361, 20):
for direction in [0, 90, 180]:
    print("Direction: ",direction)
    setDirection(direction)
    #direction = 0
    #setDirection(0)

#GPIO.cleanup()

print("done")
