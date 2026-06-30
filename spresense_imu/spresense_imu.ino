#include <Arduino.h>
#include <nuttx/config.h>
#include <sys/ioctl.h>
#include <fcntl.h>
#include <nuttx/sensors/cxd5602pwbimu.h>
#include <arch/board/board.h>

int imu_fd;
uint16_t packet_counter = 0;

void setup() {
  Serial.begin(921600);
  
  int init_ret = board_cxd5602pwbimu_initialize(5);
  if (init_ret < 0) {
    while(1);
  }

  imu_fd = open("/dev/imu0", O_RDONLY);
  if (imu_fd < 0) {
    while(1); 
  }
  
  ioctl(imu_fd, SNIOC_SSAMPRATE, 960);
  
  cxd5602pwbimu_range_t range;
  range.accel = 2;    
  range.gyro  = 125;  
  ioctl(imu_fd, SNIOC_SDRANGE, (unsigned long)&range);
  
  ioctl(imu_fd, SNIOC_SFIFOTHRESH, 1); 
  ioctl(imu_fd, SNIOC_ENABLE, 1);      
}

void loop() {
  cxd5602pwbimu_data_t imu_data;
  
  int ret = read(imu_fd, &imu_data, sizeof(imu_data));
  
  if (ret == sizeof(imu_data)) {
    unsigned long timestamp = micros();

    if (Serial && Serial.availableForWrite() > 80) {
      Serial.print(timestamp);
      Serial.print(",");
      Serial.print(packet_counter);
      Serial.print(",");
      Serial.print(imu_data.gx, 5);
      Serial.print(",");
      Serial.print(imu_data.gy, 5);
      Serial.print(",");
      Serial.print(imu_data.gz, 5);
      Serial.print(",");
      Serial.print(imu_data.ax, 5);
      Serial.print(",");
      Serial.print(imu_data.ay, 5);
      Serial.print(",");
      Serial.print(imu_data.az, 5);
      Serial.print(",");
      Serial.println(imu_data.temp, 2);
    }

    packet_counter++;
  }
}