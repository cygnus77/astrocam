#include "indigo_names.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <indigo/indigo_bus.h>
#include <indigo/indigo_client.h>

enum CAMERA_STATE  {
	IDLE = 0,
    EXPOSING = 1,
    DOWNLOADING = 2,
    ERROR = -1,
};

#define MAX_STR 128

typedef struct {
	char name[MAX_STR];
	char model[MAX_STR];
	bool connected;
	int state;
	double exposure_progress;
	bool cooler_avbl;
	double cooler_temperature;
	double cooler_power; //0-100
	bool cooler_on;
	double gain, offset;
	double width, height, pixel_size, pixel_width, pixel_height;
	void *image;
	unsigned long image_len;
} CameraT;

static CameraT camera = {
	.model="",
	.connected = false,
	.exposure_progress = 0,
	.state = IDLE,
	.cooler_avbl=false,
	.cooler_temperature=1e5,
	.cooler_power=0,
	.cooler_on=false,
	.gain=0,
	.offset=0,
	.image=NULL,
	.image_len=0,
};

typedef struct {
	char name[MAX_STR];
	char model[MAX_STR];
	bool connected;
	bool tracking;
	bool parked;
	bool athome;
	double ra, dec;
} MountT;

static MountT mount = {
	.model="",
	.connected = false,
	.tracking = false,
	.parked = false,
	.athome=false,
	.ra = 0,
	.dec = 0,
};

typedef struct {
	char name[MAX_STR];
	char model[MAX_STR];
	bool connected;
	double position;
} FocuserT;

static FocuserT focuser = {
	.model="",
	.connected = false,
	.position = -1
};

indigo_driver_entry *ccd_driver, *mount_driver, *focuser_driver;

static indigo_result client_attach(indigo_client *client) {
	indigo_log("attached to INDIGO bus...");
	indigo_enumerate_properties(client, &INDIGO_ALL_PROPERTIES);
	return INDIGO_OK;
}

void* connect_device(void* devname);

void set_file_format(indigo_device *device, indigo_client *client, indigo_property *property) {
	static const char * items[] = { CCD_IMAGE_FORMAT_RAW_ITEM_NAME };
	static bool values[] = { true };
	indigo_change_switch_property(client, device->name, property->name, 1, items, values);
}

void enable_blob_v2(indigo_device *device, indigo_client *client, indigo_property *property) {
	indigo_enable_blob(client, property, INDIGO_ENABLE_BLOB_URL);
}
void enable_blob_old(indigo_device *device, indigo_client *client, indigo_property *property) {
	indigo_enable_blob(client, property, INDIGO_ENABLE_BLOB_ALSO);
}
void setModel(char* field, indigo_property* property) {
	indigo_item* item = indigo_get_item(property, INFO_DEVICE_MODEL_ITEM_NAME);
	if(item) {
		char *model = indigo_get_text_item_value(item);
		if(model)
			strncpy(field, model, MAX_STR);
	}
}

static indigo_result client_define_property(
	indigo_client *client,
	indigo_device *device,
	indigo_property *property,
	const char *message
) {
	printf("DEFN: device: %s, name: %s\n", property->device, property->name);
	if (strcmp(property->device, camera.name) == 0) {

		if (!strcmp(property->name, CONNECTION_PROPERTY_NAME)) {
			if (indigo_get_switch(property, CONNECTION_CONNECTED_ITEM_NAME)) {
				camera.connected = true;
				indigo_log("Camera already connected...");
			} else {
				indigo_async(connect_device, (void*)camera.name);
				return INDIGO_OK;
			}
		}
		else if (!strcmp(property->name, CCD_INFO_PROPERTY_NAME)) {
			camera.width = indigo_get_item(property, CCD_INFO_WIDTH_ITEM_NAME)->number.value;
			camera.height = indigo_get_item(property, CCD_INFO_HEIGHT_ITEM_NAME)->number.value;
			camera.pixel_size = indigo_get_item(property, CCD_INFO_PIXEL_SIZE_ITEM_NAME)->number.value;
			camera.pixel_width = indigo_get_item(property, CCD_INFO_PIXEL_WIDTH_ITEM_NAME)->number.value;
			camera.pixel_height = indigo_get_item(property, CCD_INFO_PIXEL_HEIGHT_ITEM_NAME)->number.value;
		}
		else if (!strcmp(property->name, INFO_PROPERTY_NAME)) {
			setModel(camera.model, property);
		}
		else if (!strcmp(property->name, CCD_IMAGE_PROPERTY_NAME)) {
			if (device->version >= INDIGO_VERSION_2_0)
				indigo_handle_property_async(enable_blob_v2, device, client, property);
			else
				indigo_handle_property_async(enable_blob_old, device, client, property);
		}
		else if (!strcmp(property->name, CCD_IMAGE_FORMAT_PROPERTY_NAME)) {
			indigo_handle_property_async(set_file_format, device, client, property);
		}
		else if (!strcmp(property->name, CCD_TEMPERATURE_PROPERTY_NAME)) {
			camera.cooler_temperature = indigo_get_item(property, CCD_TEMPERATURE_ITEM_NAME)->number.value;
		}
		else if (!strcmp(property->name, CCD_COOLER_PROPERTY_NAME)) {
			camera.cooler_avbl = true;
			camera.cooler_on = indigo_get_switch(property, CCD_COOLER_ON_ITEM_NAME);
		}
		else if (!strcmp(property->name, CCD_COOLER_POWER_PROPERTY_NAME)) {
			camera.cooler_power = indigo_get_item(property, CCD_COOLER_POWER_ITEM_NAME)->number.value;
		}
		else if (!strcmp(property->name, CCD_OFFSET_PROPERTY_NAME)) {
			camera.offset = indigo_get_item(property, CCD_OFFSET_ITEM_NAME)->number.value;
		}
	}

	else if (strcmp(property->device, mount.name) == 0) {
		if (!strcmp(property->name, CONNECTION_PROPERTY_NAME)) {
			if (indigo_get_switch(property, CONNECTION_CONNECTED_ITEM_NAME)) {
				mount.connected = true;
				indigo_log("Mount already connected...");
			} else {
				indigo_async(connect_device, (void*)mount.name);
				return INDIGO_OK;
			}
		}
		else if (!strcmp(property->name, INFO_PROPERTY_NAME)) {
			setModel(mount.model, property);
		}
		else if (!strcmp(property->name, MOUNT_TRACKING_PROPERTY_NAME)) {
			mount.tracking = indigo_get_switch(property, MOUNT_TRACKING_ON_ITEM_NAME);
			indigo_log("Tracking: %d", mount.tracking);
		}
		else if (!strcmp(property->name, MOUNT_PARK_PROPERTY_NAME)) {
			mount.parked = indigo_get_switch(property, MOUNT_PARK_PARKED_ITEM_NAME);
			indigo_log("Parked: %d", mount.parked);
		}
		else if (!strcmp(property->name, MOUNT_HOME_PROPERTY_NAME)) {
			mount.athome = indigo_get_switch(property, MOUNT_HOME_ITEM_NAME);
			indigo_log("Athome: %d", mount.athome);
		}
		else if (!strcmp(property->name, MOUNT_EQUATORIAL_COORDINATES_PROPERTY_NAME)) {
			mount.ra = indigo_get_item(property, MOUNT_EQUATORIAL_COORDINATES_RA_ITEM_NAME)->number.value;
			mount.dec = indigo_get_item(property, MOUNT_EQUATORIAL_COORDINATES_DEC_ITEM_NAME)->number.value;
			indigo_log("Position: %f, %f", mount.ra, mount.dec);
		}
		return INDIGO_OK;
	}

	else if (strcmp(property->device, focuser.name) == 0) {
		if (!strcmp(property->name, CONNECTION_PROPERTY_NAME)) {
			if (indigo_get_switch(property, CONNECTION_CONNECTED_ITEM_NAME)) {
				focuser.connected = true;
				indigo_log("Focuser already connected...");
			} else {
				indigo_async(connect_device, (void*)focuser.name);
				return INDIGO_OK;
			}
		}
		else if (!strcmp(property->name, INFO_PROPERTY_NAME)) {
			setModel(focuser.model, property);
		}
		else if (!strcmp(property->name, FOCUSER_POSITION_PROPERTY_NAME)) {
			focuser.position = indigo_get_item(property, FOCUSER_POSITION_ITEM_NAME)->number.value;
			indigo_log("Focuser: %f", focuser.position);
		}
		return INDIGO_OK;
	}

	return INDIGO_OK;
}

static indigo_result client_update_property(
	indigo_client *client,
	indigo_device *device,
	indigo_property *property,
	const char *message
) {
	printf("UPD: device: %s, name: %s\n", property->device, property->name);
	if (strcmp(property->device, camera.name) == 0) {

		static const char * items[] = { CCD_EXPOSURE_ITEM_NAME };
		static double values[] = { 3.0 };
		if (!strcmp(property->name, CONNECTION_PROPERTY_NAME) && property->state == INDIGO_OK_STATE) {
			if (indigo_get_switch(property, CONNECTION_CONNECTED_ITEM_NAME)) {
				if (!camera.connected) {
					camera.connected = true;
					indigo_log("Camera connected...");
				}
			} else {
				if (camera.connected) {
					indigo_log("Camera disconnected...");
					camera.connected = false;
				}
			}
			return INDIGO_OK;
		}
		if (!strcmp(property->name, CCD_IMAGE_PROPERTY_NAME) && property->state == INDIGO_OK_STATE) {
			/* URL blob transfer is available only in client - server setup.
			This will never be called in case of a client loading a driver. */
			camera.state = DOWNLOADING;
			if (*property->items[0].blob.url && indigo_populate_http_blob_item(&property->items[0]))
				indigo_log("image URL received (%s, %d bytes)...", property->items[0].blob.url, property->items[0].blob.size);

			if (property->items[0].blob.value) {

				if (camera.image) {
					free(camera.image);
				}
				camera.image_len = property->items[0].blob.size;
				camera.image = malloc(camera.image_len);
				memcpy(camera.image, property->items[0].blob.value, camera.image_len);

				/* In case we have URL BLOB transfer we need to release the blob ourselves */
				if (*property->items[0].blob.url) {
					free(property->items[0].blob.value);
					property->items[0].blob.value = NULL;
				}
			}
		}
		if (!strcmp(property->name, CCD_EXPOSURE_PROPERTY_NAME)) {
			if (property->state == INDIGO_BUSY_STATE) {
				indigo_log("exposure %gs...", property->items[0].number.value);
				camera.exposure_progress = property->items[0].number.value;
			} else if (property->state == INDIGO_OK_STATE) {
				indigo_log("exposure done...");
				camera.state = IDLE;
			}
			return INDIGO_OK;
		}
		else if (!strcmp(property->name, CCD_TEMPERATURE_PROPERTY_NAME)) {
			camera.cooler_temperature = indigo_get_item(property, CCD_TEMPERATURE_ITEM_NAME)->number.value;
			indigo_log("Cooler temp: %f", camera.cooler_temperature);
		}
		else if (!strcmp(property->name, CCD_COOLER_PROPERTY_NAME)) {
			camera.cooler_avbl = true;
			camera.cooler_on = indigo_get_switch(property, CCD_COOLER_ON_ITEM_NAME);
		}
		else if (!strcmp(property->name, CCD_COOLER_POWER_PROPERTY_NAME)) {
			camera.cooler_power = indigo_get_item(property, CCD_COOLER_POWER_ITEM_NAME)->number.value;
			indigo_log("Cooler power: %f", camera.cooler_power);
		}
		else if (!strcmp(property->name, CCD_GAIN_PROPERTY_NAME)) {
			camera.gain = indigo_get_item(property, CCD_GAIN_ITEM_NAME)->number.value;
			indigo_log("Gain: %f", camera.gain);
		}
		else if (!strcmp(property->name, CCD_OFFSET_PROPERTY_NAME)) {
			camera.offset = indigo_get_item(property, CCD_OFFSET_ITEM_NAME)->number.value;
			indigo_log("Offset: %f", camera.offset);
		}
	}

	else if (strcmp(property->device, mount.name) == 0) {

		if (!strcmp(property->name, CONNECTION_PROPERTY_NAME) && property->state == INDIGO_OK_STATE) {
			if (indigo_get_switch(property, CONNECTION_CONNECTED_ITEM_NAME)) {
				if (!mount.connected) {
					mount.connected = true;
					indigo_log("Mount connected...");
				}
			} else {
				if (mount.connected) {
					indigo_log("Mount disconnected...");
					mount.connected = false;
				}
			}
			return INDIGO_OK;
		}
		else if (!strcmp(property->name, MOUNT_TRACKING_PROPERTY_NAME)) {
			mount.tracking = indigo_get_switch(property, MOUNT_TRACKING_ON_ITEM_NAME);
			indigo_log("Tracking: %d", mount.tracking);
		}
		else if (!strcmp(property->name, MOUNT_PARK_PROPERTY_NAME)) {
			mount.parked = indigo_get_switch(property, MOUNT_PARK_PARKED_ITEM_NAME);
			indigo_log("Parked: %d", mount.parked);
		}
		else if (!strcmp(property->name, MOUNT_HOME_PROPERTY_NAME)) {
			mount.athome = indigo_get_switch(property, MOUNT_HOME_ITEM_NAME);
			indigo_log("Athome: %d", mount.athome);
		}
		else if (!strcmp(property->name, MOUNT_EQUATORIAL_COORDINATES_PROPERTY_NAME)) {
			mount.ra = indigo_get_item(property, MOUNT_EQUATORIAL_COORDINATES_RA_ITEM_NAME)->number.value;
			mount.dec = indigo_get_item(property, MOUNT_EQUATORIAL_COORDINATES_DEC_ITEM_NAME)->number.value;
			indigo_log("Position: %f, %f", mount.ra, mount.dec);
		}
	}

	else if (strcmp(property->device, focuser.name) == 0) {

		if (!strcmp(property->name, CONNECTION_PROPERTY_NAME) && property->state == INDIGO_OK_STATE) {
			if (indigo_get_switch(property, CONNECTION_CONNECTED_ITEM_NAME)) {
				if (!focuser.connected) {
					focuser.connected = true;
					indigo_log("Focuser connected...");
				}
			} else {
				if (focuser.connected) {
					indigo_log("Focuser disconnected...");
					focuser.connected = false;
				}
			}
			return INDIGO_OK;
		}
		else if (!strcmp(property->name, FOCUSER_POSITION_PROPERTY_NAME)) {
			focuser.position = indigo_get_item(property, FOCUSER_POSITION_ITEM_NAME)->number.value;
			indigo_log("Focuser: %f", focuser.position);
		}
	}

	return INDIGO_OK;
}

static indigo_result client_detach(indigo_client *client) {
	indigo_log("detached from INDIGO bus...");
	return INDIGO_OK;
}

static indigo_client client = {
	"Remote server client", false, NULL, INDIGO_OK, INDIGO_VERSION_CURRENT, NULL,
	client_attach,
	client_define_property,
	client_update_property,
	NULL,
	NULL,
	client_detach
};

void* connect_device(void* devname) {
	indigo_device_connect(&client, (char*)devname);
	return NULL;
}


/***********************
	Camera API
 ***********************/
const char* getCameraModel() {
	return camera.model;
}
int getCameraState() {
	return camera.state;
}
bool getCameraConnected() {
	return camera.connected;
}

double getCameraWidth() 		{ return camera.width; }
double getCameraHeight() 		{ return camera.height; }
double getCameraPixelSize() 	{ return camera.pixel_size; }
double getCameraPixelWidth()	{ return camera.pixel_width; }
double getCameraPixelHeight()	{ return camera.pixel_height; }

void setCameraFrameType(bool light) {
	static const char * items[] = { CCD_FRAME_TYPE_LIGHT_ITEM_NAME, CCD_FRAME_TYPE_DARK_ITEM_NAME };
	static bool values[2];
	values[0] = light;
	values[1] = !light;
	indigo_change_switch_property(&client, camera.name, CCD_FRAME_TYPE_PROPERTY_NAME, 1, items, values);
}

void cameraStartExposure(double seconds) {
	static const char * items[] = { CCD_EXPOSURE_ITEM_NAME };
	static double values[1];
	values[0] = seconds;
	camera.state = EXPOSING;
	indigo_change_number_property(&client, camera.name, CCD_EXPOSURE_PROPERTY_NAME, 1, items, values);
}

void getCameraImage(void **ptr, unsigned long* len) {
	*ptr = camera.image;
	*len = camera.image_len;
}

/* Cooler APIs */

void setCameraCoolerOn(bool on) {
	static const char * items[] = { CCD_COOLER_ON_ITEM_NAME };
	static bool values[1];
	values[0] = on;
	indigo_change_switch_property(&client, camera.name, CCD_COOLER_PROPERTY_NAME, 1, items, values);
}
bool getCameraCoolerOn() {
	return camera.cooler_on;
}
void setCameraCoolerTemperature(double target) {
	static const char * items[] = { CCD_TEMPERATURE_ITEM_NAME };
	static double values[1];
	values[0] = target;
	indigo_change_number_property(&client, camera.name, CCD_TEMPERATURE_PROPERTY_NAME, 1, items, values);
}
double getCameraCoolerTemperature() {
	return camera.cooler_temperature;
}
double getCameraCoolerPower() {
	return camera.cooler_power;
}

/* Gain & Offset */

void setCameraGain(double gain) {
	static const char * items[] = { CCD_GAIN_ITEM_NAME };
	static double values[1];
	values[0] = gain;
	indigo_change_number_property(&client, camera.name, CCD_GAIN_PROPERTY_NAME, 1, items, values);
}
double getCameraGain() {
	return camera.gain;
}
void setCameraOffset(double offset) {
	static const char * items[] = { CCD_OFFSET_ITEM_NAME };
	static double values[1];
	values[0] = offset;
	indigo_change_number_property(&client, camera.name, CCD_OFFSET_PROPERTY_NAME, 1, items, values);
}
double getCameraOffset() {
	return camera.offset;
}

/***********************
	Focuser API
 ***********************/

void setFocuserPosition(double position) {
	static const char * items[] = { FOCUSER_POSITION_ITEM_NAME };
	static double values[1];
	values[0] = position;
	indigo_change_number_property(&client, focuser.name, FOCUSER_POSITION_PROPERTY_NAME, 1, items, values);
}

double getFocuserPosition() {
	return focuser.position;
}

/***********************
	Mount API
 ***********************/
void _mountSetCoorinates(double ra, double dec) {
	static const char * coord_items[] = { MOUNT_EQUATORIAL_COORDINATES_RA_ITEM_NAME, MOUNT_EQUATORIAL_COORDINATES_DEC_ITEM_NAME };
	static double coord_values[2];
	coord_values[0] = ra;
	coord_values[1] = dec;
	indigo_change_number_property(&client, mount.name, MOUNT_EQUATORIAL_COORDINATES_PROPERTY_NAME, 2, coord_items, coord_values);
}

void MountMoveTo(double ra, double dec) {
	static const char * items[] = { MOUNT_ON_COORDINATES_SET_TRACK_ITEM_NAME };
	static bool values[1] = {true};
	indigo_change_switch_property(&client, mount.name, MOUNT_ON_COORDINATES_SET_PROPERTY_NAME, 1, items, values);

	_mountSetCoorinates(ra, dec);
}

void MountSyncTo(double ra, double dec) {
	static const char * items[] = { MOUNT_ON_COORDINATES_SET_SYNC_ITEM_NAME };
	static bool values[1] = {true};
	indigo_change_switch_property(&client, mount.name, MOUNT_ON_COORDINATES_SET_PROPERTY_NAME, 1, items, values);

	_mountSetCoorinates(ra, dec);
}

void MountPark(bool on) {
	static const char * items[1] = { MOUNT_PARK_PARKED_ITEM_NAME };
	static bool values[1];
	values[0] = on;
	indigo_change_switch_property(&client, mount.name, MOUNT_PARK_PROPERTY_NAME, 1, items, values);
}

void MountGotoHome() {
	static const char * items[] = { MOUNT_HOME_ITEM_NAME };
	static bool values[1] = {true};
	indigo_change_switch_property(&client, mount.name, MOUNT_HOME_PROPERTY_NAME, 1, items, values);
}

void getMountCoordinates(double *ra, double *dec) {
	*ra = mount.ra;
	*dec = mount.dec;
}

bool getMountTracking() { return mount.tracking; }
bool getMountParked() { return mount.parked; }
bool getMountSlewing() { return false; }
bool getMountAtHome() { return mount.athome; }

bool Initialize() {
	indigo_set_log_level(INDIGO_LOG_INFO);
	indigo_start();
	if (indigo_load_driver("indigo_ccd_simulator", true, &ccd_driver) == INDIGO_OK &&
		// indigo_load_driver("indigo_ccd_simulator", true, &focuser_driver) == INDIGO_OK &&
		indigo_load_driver("indigo_mount_simulator", true, &mount_driver) == INDIGO_OK ) {

		strncpy(camera.name, "CCD Imager Simulator", MAX_STR);
		strncpy(mount.name, "Mount Simulator", MAX_STR);
		strncpy(focuser.name, "CCD Imager Simulator (focuser)", MAX_STR);

		indigo_attach_client(&client);

		while(!(camera.connected && focuser.connected && mount.connected)) {
			indigo_usleep(ONE_SECOND_DELAY);
		}
		return true;
	}
	return false;
}

void Close() {
	indigo_device_disconnect(&client, camera.name);
	indigo_device_disconnect(&client, mount.name);
	indigo_device_disconnect(&client, focuser.name);

	while(camera.connected || focuser.connected || mount.connected) {
		indigo_usleep(ONE_SECOND_DELAY);
	}
	
	indigo_detach_client(&client);
	indigo_remove_driver(mount_driver);
	indigo_remove_driver(ccd_driver);
	// indigo_remove_driver(focuser_driver);
	indigo_stop();
}

void Sleep1Sec() {
	indigo_usleep(ONE_SECOND_DELAY);
}

int main(int argc, const char * argv[]) {
	indigo_main_argc = argc;
	indigo_main_argv = argv;
	
#if defined(INDIGO_WINDOWS)
	freopen("indigo.log", "w", stderr);
#endif

	Initialize();
	
	setCameraCoolerOn(true);
	setCameraCoolerTemperature(22);
	while(getCameraCoolerTemperature() > 22) {
		indigo_usleep(ONE_SECOND_DELAY);
	}

	setCameraGain(120);
	setFocuserPosition(1000);
	cameraStartExposure(3);
	while(getCameraState() != IDLE) {
		indigo_usleep(ONE_SECOND_DELAY);
	}
	Close();
		
	return 0;
}
