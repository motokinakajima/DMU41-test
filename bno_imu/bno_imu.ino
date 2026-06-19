#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BNO055.h>
#include <utility/imumaths.h>

Adafruit_BNO055 bno = Adafruit_BNO055(55, 0x28, &Wire);

uint16_t packet_counter = 0;
unsigned long interval = 10000; 
unsigned long next_time = 0;

void setup() {
  Serial.begin(921600);
  Wire.begin(); 
  
  if (!bno.begin()) {
    while (1);
  }
  
  bno.setExtCrystalUse(true);
}

void loop() {
  unsigned long now = micros();
  
  if (now >= next_time) {
    next_time += interval;

    imu::Vector<3> gyro = bno.getVector(Adafruit_BNO055::VECTOR_GYROSCOPE);
    imu::Vector<3> accel = bno.getVector(Adafruit_BNO055::VECTOR_ACCELEROMETER);
    int8_t temp = bno.getTemp();

    Serial.print(now);
    Serial.print(",");
    Serial.print(packet_counter);
    Serial.print(",");
    Serial.print(gyro.x(), 5);
    Serial.print(",");
    Serial.print(gyro.y(), 5);
    Serial.print(",");
    Serial.print(gyro.z(), 5);
    Serial.print(",");
    Serial.print(accel.x(), 5);
    Serial.print(",");
    Serial.print(accel.y(), 5);
    Serial.print(",");
    Serial.print(accel.z(), 5);
    Serial.print(",");
    Serial.println(temp);

    packet_counter++;
  }
}