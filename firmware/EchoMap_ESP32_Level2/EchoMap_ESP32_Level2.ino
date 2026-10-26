/*
  EchoMap ESP32 firmware — Level 2
  Board: ESP32 Dev Module
  HC-SR04: TRIG GPIO 5, ECHO GPIO 18 via divider
  GY-521 / MPU6050: SDA GPIO 21, SCL GPIO 22, VCC 3.3V

  Serial protocol: one JSON record per line at 115200 baud.
  Install libraries via Arduino Library Manager:
    - Adafruit MPU6050
    - Adafruit Unified Sensor
*/

#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

#define TRIG_PIN 5
#define ECHO_PIN 18
#define SDA_PIN 21
#define SCL_PIN 22

Adafruit_MPU6050 mpu;
bool mpuReady = false;
unsigned long lastSample = 0;
const unsigned long SAMPLE_INTERVAL_MS = 250;

void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  Wire.begin(SDA_PIN, SCL_PIN);
  mpuReady = mpu.begin(0x68, &Wire);
  if (mpuReady) {
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
  }

  // Keep startup diagnostics out of the JSON stream; the web parser expects JSON lines.
}

void loop() {
  const unsigned long now = millis();
  if (now - lastSample < SAMPLE_INTERVAL_MS) return;
  lastSample = now;

  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(3);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  const unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000UL);
  const bool echoValid = duration > 0;
  const float distanceCm = echoValid ? (duration * 0.0343f / 2.0f) : -1.0f;

  float ax = 0, ay = 0, az = 0, gx = 0, gy = 0, gz = 0;
  if (mpuReady) {
    sensors_event_t accel, gyro, temp;
    mpu.getEvent(&accel, &gyro, &temp);
    ax = accel.acceleration.x; ay = accel.acceleration.y; az = accel.acceleration.z;
    gx = gyro.gyro.x; gy = gyro.gyro.y; gz = gyro.gyro.z;
  }

  Serial.print("{\"v\":1,\"type\":\"sample\",\"ts_ms\":");
  Serial.print(now);
  Serial.print(",\"distance_cm\":");
  if (echoValid && distanceCm > 0 && distanceCm <= 450) Serial.print(distanceCm, 2);
  else Serial.print("null");
  Serial.print(",\"echo_valid\":");
  Serial.print((echoValid && distanceCm > 0 && distanceCm <= 450) ? "true" : "false");

  if (mpuReady) {
    Serial.print(",\"accel_m_s2\":{\"x\":"); Serial.print(ax, 3);
    Serial.print(",\"y\":"); Serial.print(ay, 3);
    Serial.print(",\"z\":"); Serial.print(az, 3);
    Serial.print("},\"gyro_rad_s\":{\"x\":"); Serial.print(gx, 4);
    Serial.print(",\"y\":"); Serial.print(gy, 4);
    Serial.print(",\"z\":"); Serial.print(gz, 4);
    Serial.print("}");
  }
  Serial.println("}");
}
