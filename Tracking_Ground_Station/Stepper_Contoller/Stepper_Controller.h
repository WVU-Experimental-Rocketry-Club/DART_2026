#ifndef Stepper_Controller_H
#define Stepper_Controller_H
#include <MultiStepper.h>
#include <AccelStepper.h>
#include <Wire.h> //Needed for I2C to GNSS

#include <SparkFun_u-blox_GNSS_Arduino_Library.h>
#include <Wire.h>

#define NUM_STEPPERS 2
#define PPR 400
#define MAX_verticle_angle 89
#define MAX_AZIMUTH 180
#define EARTH_RADIUS 6378
SFE_UBLOX_GNSS myGNSS;


/*
 *Holds gps coordnates, Latitude, Longitude, Altitude
*/
typedef struct gps_location{
  double lat;
  double lon;
  double alt;
}gps_location;



/*@Brief Initilizes and connects to the u-blox gps
* @parm none
* @return Returns 1 if error otherwise retuens 0
*/
int connect_gps();

/*@Brief Uses GPS to retrive ground station GPS coordniates and places them in
         a gps struct
* @parm none
* @return
*/
gps_location ground_station_gps();

/*
 * Responseable for give rocket loaction from radios, contians dummy values
*/
gps_location rocket_gps();

/*
 *@Brief Calculates the azimuth between two lat,long points starting from 0 degress
 *@parm none
 *@returns returns the degree angle as a double
*/
double get_azimuth();

/*
 *@Brief Calculates the angle the ground station will need to turn upward to point at the rocket. 
          To do this, it calues the distance between the rocket and groundstation using the haversine formulae for distance
 *@parm none
 *@return Returns angle in degrees as a double
*/
double get_verticle_angle();


/*
 *@Brief Uses the two angles to calcute the number of steps each motor needs to take to point at the rocket
 *@parm Verticle_angle & azimuth
 *@return none
*/
void step_to_rocket(double verticle_angle, double azimuth);

#endif