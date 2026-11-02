#include <stdio.h>
#include "hbird_sdk_hal.h"

#define I2C_PRESCALER 0x1F
#define I2C_ID        I2C1

void gpio_config();
int puf_on();
int puf_off();
int i2c_puf_wr_test();

int main(void)
{

    printf("I2C Test\r\n");

    gpio_config();

    i2c_setup(I2C_ID, I2C_PRESCALER, I2C_CTR_EN);
    printf("I2C setup\r\n");
    i2c_puf_wr_test();
    return 0;
}

void gpio_config()
{
    gpio_iof_config(GPIOB, IOF_I2C_MASK);
}

int puf_on()
{
	i2c_send_data(I2C_ID, 0xc8);
	i2c_send_command(I2C_ID, I2C_READ);
    if(!i2c_get_ack(I2C_ID)) {
      printf("No ack received from puf, Device Control, Write data\n");
      return 0;
    }
	i2c_send_data(I2C_ID, 0x00);
	i2c_send_command(I2C_ID, I2C_READ);
    if(!i2c_get_ack(I2C_ID)) {
      printf("No ack received from puf, Device Control, Write data\n");
      return 0;
    }
	i2c_send_data(I2C_ID, 0x20);
	i2c_send_command(I2C_ID, I2C_READ);
    if(!i2c_get_ack(I2C_ID)) {
      printf("No ack received from puf, Device Control, Write data\n");
      return 0;
    }
    return 0;
}

int puf_off()
{
	i2c_send_data(I2C_ID, 0xc8);
	i2c_send_command(I2C_ID, I2C_READ);
    if(!i2c_get_ack(I2C_ID)) {
      printf("No ack received from puf, Device Control, Write data\n");
      return 0;
    }
	i2c_send_data(I2C_ID, 0x00);
	i2c_send_command(I2C_ID, I2C_READ);
    if(!i2c_get_ack(I2C_ID)) {
      printf("No ack received from puf, Device Control, Write data\n");
      return 0;
    }
	i2c_send_data(I2C_ID, 0x10);
	i2c_send_command(I2C_ID, I2C_READ);
    if(!i2c_get_ack(I2C_ID)) {
      printf("No ack received from puf, Device Control, Write data\n");
      return 0;
    }
    return 0;
}

int i2c_puf_wr_test(){
	uint8_t data[32] = {
			0xBD,0x1B,0x01,0x9F,0xEC,0xA9,0x86,0x04,
			    0xAE,0xC5,0xFF,0xCC,0xBB,0xCA,0x2F,0xC2,
			    0x7D,0x70,0xEB,0x4F,0x7E,0xAF,0x7C,0xD8,
			    0xBC,0xCF,0x2B,0x1B,0xAF,0xA0,0x0A,0xF8
	    };
    i2c_send_data(I2C_ID, 0xc8);
    i2c_send_command(I2C_ID, I2C_START_WRITE);
     if(!i2c_get_ack(I2C_ID)) {
       printf("No ack received from puf, Device Control, Write data\n");
       return 0;
     }

      i2c_send_data(I2C_ID, 0x00);
      i2c_send_command(I2C_ID, I2C_WRITE);
      if(!i2c_get_ack(I2C_ID)) {
        printf("No ack received from puf, Device Control, Write data\n");
        return 0;
      }
      i2c_send_data(I2C_ID, 0x50);
      i2c_send_command(I2C_ID, I2C_WRITE);
      if(!i2c_get_ack(I2C_ID)) {
        printf("No ack received from puf, Device Control, Write data\n");
        return 0;
      }
      for (int i = 0; i < 32; i++) {
        i2c_send_data(I2C_ID, data[i]);
        i2c_send_command(I2C_ID, I2C_WRITE);
      }
      i2c_send_command(I2C_ID, I2C_STOP);
      while(i2c_busy(I2C_ID));
      printf("I2C Write data done \n");

      do {
        i2c_send_data(I2C_ID, 0xc9);
        i2c_send_command(I2C_ID, I2C_START_WRITE);
      } while (!i2c_get_ack(I2C_ID));


   	uint8_t respone[32];
       // Read Data
       for (int i = 0; i < 32; i++) {
         if (i == 31)
           i2c_send_command(I2C_ID, I2C_STOP_READ);
         else
           i2c_send_command(I2C_ID, I2C_READ);

         if (!i2c_get_ack(I2C_ID)) {
           printf("No ack received from puf for byte %d\n", i);
           return 0;
         }

         respone[i] = i2c_get_data(I2C_ID);
         printf("Received %02x \n", respone[i]);
       }

       printf("I2C Test Pass!!!\n");

}














