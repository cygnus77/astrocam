// camtest.cpp : This file contains the 'main' function. Program execution begins and ends there.
//

#include <iostream>
#include <string>
#include	"Maid3.h"
#include	"Maid3d1.h"
#include	"CtrlSample.h"

using namespace std;

LPMAIDEntryPointProc	g_pMAIDEntryPoint = NULL;
UCHAR	g_bFileRemoved = false;
ULONG	g_ulCameraType = 0;	// CameraType
HINSTANCE	g_hInstModule = NULL;
int g_fileNo = 0;
char g_destDir[MAX_PATH] = { 0, };

class CameraAPI
{
public:
	CameraAPI(int cameraModel) {
		char	ModulePath[MAX_PATH] = { 0 };
		ULONG	ulModID = 0;
		const char* mdFile = nullptr;

		if (cameraModel == 90) {
			mdFile = "\\Type0003.md3";
			this->BulbMode = 0;
			this->isShutterRelease = TRUE;

			this->m_hCommPort = ::CreateFile("COM5",
				GENERIC_WRITE | GENERIC_READ,  // access ( read and write)
				0,                           // (share) 0:cannot share the
											 // COM port
				0,                           // security  (None)
				OPEN_EXISTING,               // creation : open_existing
				0,        // we want overlapped operation
				0                            // no templates file for
											 // COM port...
			);

			DWORD err = GetLastError();
			if (err) {
				printf("Error: %d", err);
				throw new runtime_error("Unable to open COM 7\n");
			}

			COMMTIMEOUTS commTimeouts;
			commTimeouts.ReadIntervalTimeout = 0;
			commTimeouts.ReadTotalTimeoutConstant = 250;
			commTimeouts.ReadTotalTimeoutMultiplier = 250;
			commTimeouts.WriteTotalTimeoutConstant = 250;
			commTimeouts.WriteTotalTimeoutMultiplier = 50;
			SetCommTimeouts(this->m_hCommPort, &commTimeouts);

			DCB dcb = { 0 };
			dcb.DCBlength = sizeof(DCB);

			if (!::GetCommState(this->m_hCommPort, &dcb))
			{
				printf("CSerialCommHelper : Failed to Get Comm State Reason: %d",
					GetLastError());
			}

			dcb.BaudRate = 57600;
			dcb.fDtrControl = 1;
			dcb.fTXContinueOnXoff = 1;
			dcb.ByteSize = 8;

			if (!::SetCommState(this->m_hCommPort, &dcb))
			{
				printf("CSerialCommHelper : Failed to Set Comm State Reason: %d",
					GetLastError());
			}

			if (closeShutter() != 0) {
				throw new runtime_error("Arduino not responding!\n");
			}
		}
		else if (cameraModel == 5300) {
			mdFile = "\\Type0011.md3";
			this->BulbMode = 1;
		}
		else if (cameraModel == 750) {
			mdFile = "\\Type0015.md3";
			this->BulbMode = 2;
		}
		if (!Search_Module(ModulePath, mdFile)) throw runtime_error("Type0015 Module is not found.");
		if (!Load_Module(ModulePath)) throw runtime_error("Cant load Type0015");
		pRefMod = (LPRefObj)malloc(sizeof(RefObj));
		InitRefObj(pRefMod);
		pRefMod->pObject = (LPNkMAIDObject)malloc(sizeof(NkMAIDObject));
		pRefMod->pObject->refClient = (NKREF)pRefMod;

		if (!Command_Open(NULL, pRefMod->pObject, ulModID)) throw runtime_error("Module object can't be opened.");
		if (!EnumCapabilities(pRefMod->pObject, &(pRefMod->ulCapCount), &(pRefMod->pCapArray), NULL, NULL))  throw runtime_error("Failed in enumeration of capabilities.");

		if (!SetProc(pRefMod)) throw runtime_error("Failed in setting a call back function.");

		if (CheckCapabilityOperation(pRefMod, kNkMAIDCapability_ModuleMode, kNkMAIDCapOperation_Set)) {
			if (!Command_CapSet(pRefMod->pObject, kNkMAIDCapability_ModuleMode, kNkMAIDDataType_Unsigned,
				(NKPARAM)kNkMAIDModuleMode_Controller, NULL, NULL)) throw runtime_error("Failed in setting kNkMAIDCapability_ModuleMode.");
		}
	}

	void setDestDir(const char* destDir) {
		strncpy(g_destDir, destDir, MAX_PATH);
	}

	bool openSource(ULONG ulSrcID)
	{
		this->ulSrcID = ulSrcID;
		NkMAIDEnum	stEnum;
		LPNkMAIDCapInfo pCapInfo = GetCapInfo(pRefMod, kNkMAIDCapability_Children);
		if (pCapInfo == NULL) throw runtime_error("Failed to get kNkMAIDCapability_Children");

		// check data type of the capability
		if (pCapInfo->ulType != kNkMAIDCapType_Enum) return false;
		// check if this capability supports CapGet operation.
		if (!CheckCapabilityOperation(pRefMod, kNkMAIDCapability_Children, kNkMAIDCapOperation_Get)) throw runtime_error("Failed CheckCapabilityOperation on kNkMAIDCapability_Children");

		if (!Command_CapGet(pRefMod->pObject, kNkMAIDCapability_Children, kNkMAIDDataType_EnumPtr, (NKPARAM)&stEnum, NULL, NULL)) throw runtime_error("Failed Command_CapGet on kNkMAIDCapability_Children");

		pRefSrc = GetRefChildPtr_ID(pRefMod, ulSrcID);
		if (pRefSrc == NULL) {
			// Create Source object and RefSrc structure.
			if (AddChild(pRefMod, ulSrcID) == FALSE) {
				throw runtime_error("Source can't be opened");
			}
			pRefSrc = GetRefChildPtr_ID(pRefMod, ulSrcID);
		}
		return true;
	}

	bool inline setEnumProp(eNkMAIDCapabilityD1 prop, ULONG value) {
		NkMAIDEnum	stEnum;
		if (!Command_CapGet(pRefSrc->pObject, prop, kNkMAIDDataType_EnumPtr, (NKPARAM)&stEnum, NULL, NULL)) return false;
		stEnum.ulValue = value;
		if (!Command_CapSet(pRefSrc->pObject, prop, kNkMAIDDataType_EnumPtr, (NKPARAM)&stEnum, NULL, NULL)) return false;
		return true;
	}

	BOOL setISO(ULONG isoCode)
	{
		return setEnumProp(kNkMAIDCapability_Sensitivity, isoCode) &&
			Command_CapSet(pRefSrc->pObject, kNkMAIDCapability_IsoControl, kNkMAIDDataType_Boolean, (NKPARAM)FALSE, NULL, NULL);
	}

	BOOL setBulbMode()
	{
		return setEnumProp(kNkMAIDCapability_ShutterSpeed, this->BulbMode); // Bulb mode
	}

	BOOL setWhiteBalanceMode(ULONG wbCode) {
		return setEnumProp(kNkMAIDCapability_WBMode, wbCode);
	}

	bool turnOffNR() {
		return Command_CapSet(pRefSrc->pObject, kNkMAIDCapability_NoiseReductionHighISO, kNkMAIDDataType_Unsigned, (NKPARAM)kNkMAIDNoiseReductionHighISO_Off, NULL, NULL) &&
			Command_CapSet(pRefSrc->pObject, kNkMAIDCapability_NoiseReduction, kNkMAIDDataType_Boolean, (NKPARAM)FALSE, NULL, NULL);
	}

	bool turnOnExposureDelay() {
		throw runtime_error("not supported");
		//return Command_CapSet(pRefSrc->pObject, kNkMAIDCapability_ExposureDelayEx, kNkMAIDDataType_Unsigned, (NKPARAM)1, NULL, NULL);
	}

	bool setCommpressionLevel() {
		return setEnumProp(kNkMAIDCapability_CompressionLevel, 3); // 3 - RAW
	}

	bool setPictureControl() {
		return setEnumProp(kNkMAIDCapability_PictureControl, 1); // 0 - standard, 1- neutral
	}

	bool turnOffDLighting() {
		return Command_CapSet(pRefSrc->pObject, kNkMAIDCapability_Active_D_Lighting, kNkMAIDDataType_Unsigned, (NKPARAM)kNkMAIDActive_D_Lighting_Off, NULL, NULL);
		//return setEnumProp(kNkMAIDCapability_Active_D_Lighting, kNkMAIDActive_D_Lighting_Off);
	}

	int commCommand(const char* cmd_letter, const char* expect, int len_expect) {
		DWORD dwBytesWritten = 0;
		char buff[10] = { 0 };
		DWORD bytesRead = 0;
		int retries = 10;
		while (retries > 0) {
			printf(">");
			BOOL bRet = WriteFile(this->m_hCommPort, cmd_letter, 1, &dwBytesWritten, 0);
			if (!bRet || dwBytesWritten != 1) {
				printf("[Err1:%d, %x]", bRet, GetLastError());
				Sleep(250);
				retries--;
				continue;
			}

			printf("<");
			bRet = ReadFile(this->m_hCommPort, buff, len_expect, &bytesRead, NULL);
			if (!bRet || bytesRead != len_expect) {
				printf("[Err2:%d, %d, %x]", bRet, bytesRead, GetLastError());
				Sleep(250);
				retries--;
				continue;
			}
			if (strncmp(expect, buff, len_expect) == 0) {
				printf("\n");
				break; // success
			}
		}
		if (retries == 0) {
			return -1;
		}
		return 0;
	}

	int openShutter() {
		return commCommand("o", "open", 4);
	}

	int closeShutter() {
		return commCommand("c", "closed", 6);
	}

	int takeShutterReleasePicture(float seconds) {

		if (openShutter() != 0)
			return -1;

		// Sleep for exposure
		Sleep((DWORD)(seconds * 1000));

		if (closeShutter() != 0)
			return -1;

		LPNkMAIDObject pSourceObject = pRefSrc->pObject;
		BOOL bRet;
		ULONG ulItmID = 0;
		int retries = 10;
		// Poll for image availability
		while (retries) {
			NkMAIDEnum	stEnum;
			bRet = Command_CapGet(pSourceObject, kNkMAIDCapability_Children, kNkMAIDDataType_EnumPtr, (NKPARAM)&stEnum, NULL, NULL);
			if (bRet == false) {
				return -1;
			}

			if (stEnum.ulElements == 0) {
				retries--;
				Sleep(1000);
				continue;
			}

			// check the data of the capability.
			if (stEnum.wPhysicalBytes != 4) return -1;
			// allocate memory for array data
			stEnum.pData = malloc(stEnum.ulElements * stEnum.wPhysicalBytes);
			// get array data
			if (Command_CapGetArray(pSourceObject, kNkMAIDCapability_Children, kNkMAIDDataType_EnumPtr, (NKPARAM)&stEnum, NULL, NULL) == FALSE) {
				free(stEnum.pData);
				return -1;
			}

			if (stEnum.ulElements == 0) {
				retries--;
				free(stEnum.pData);
				Sleep(1000);
				continue;
			}
			ulItmID = ((ULONG*)stEnum.pData)[0];
			free(stEnum.pData);
			break;
		}

		if (retries == 0)
			return -1;

		LPRefObj pRefItm = GetRefChildPtr_ID(pRefSrc, ulItmID);
		if (pRefItm == NULL) {
			// Create Item object and RefSrc structure.
			if (AddChild(pRefSrc, ulItmID) == TRUE) {
				printf("Item object is opened.\n");
			}
			else {
				printf("Item object can't be opened.\n");
				return -1;
			}
			pRefItm = GetRefChildPtr_ID(pRefSrc, ulItmID);
		}

		LPNkMAIDCapInfo pCapInfo2 = GetCapInfo(pRefItm, kNkMAIDCapability_DataTypes);
		if (pCapInfo2 == NULL) {
			return -1;
		}

		if (!CheckCapabilityOperation(pRefItm, kNkMAIDCapability_DataTypes, kNkMAIDCapOperation_Get))
			return -1;

		ULONG	ulDataTypes=0;
		bRet = Command_CapGet(pRefItm->pObject, kNkMAIDCapability_DataTypes, kNkMAIDDataType_UnsignedPtr, (NKPARAM)&ulDataTypes, NULL, NULL);
		if (bRet == FALSE)
			return -1;

		ULONG	dataType;
		if ((ulDataTypes & kNkMAIDDataObjType_Image) == 0)
			return -1;

		// reset file removed flag
		g_bFileRemoved = false;

		LPRefObj pRefDat = GetRefChildPtr_ID(pRefItm, kNkMAIDDataObjType_Image);
		if (pRefDat == NULL) {
			// Create Image object and RefSrc structure.
			if (AddChild(pRefItm, kNkMAIDDataObjType_Image) == TRUE) {
				printf("Image object is opened.\n");
			}
			else {
				printf("Image object can't be opened.\n");
				return -1;
			}
			pRefDat = GetRefChildPtr_ID(pRefItm, kNkMAIDDataObjType_Image);
		}

		// set reference from DataProc
		LPRefDataProc pRefDeliver = (LPRefDataProc)malloc(sizeof(RefDataProc));// this block will be freed in CompletionProc.
		pRefDeliver->pBuffer = NULL;
		pRefDeliver->ulOffset = 0L;
		pRefDeliver->ulTotalLines = 0L;
		pRefDeliver->lID = pRefItm->lMyID;
		// set reference from CompletionProc
		ULONG ulCount = 0L;
		LPRefCompletionProc pRefCompletion = (LPRefCompletionProc)malloc(sizeof(RefCompletionProc));// this block will be freed in CompletionProc.
		pRefCompletion->pulCount = &ulCount;
		pRefCompletion->pRef = pRefDeliver;
		// set reference from DataProc
		NkMAIDCallback	stProc;
		stProc.pProc = (LPNKFUNC)DataProc;
		stProc.refProc = (NKREF)pRefDeliver;

		// set DataProc as data delivery callback function
		if (CheckCapabilityOperation(pRefDat, kNkMAIDCapability_DataProc, kNkMAIDCapOperation_Set) &&
			Command_CapSet(pRefDat->pObject, kNkMAIDCapability_DataProc, kNkMAIDDataType_CallbackPtr, (NKPARAM)&stProc, NULL, NULL) &&
			// start getting an image
			Command_CapStart(pRefDat->pObject, kNkMAIDCapability_Acquire, (LPNKFUNC)CompletionProc, (NKREF)pRefCompletion, NULL)) {

			IdleLoop(pRefDat->pObject, &ulCount, 1);
		}
		// reset DataProc
		if (!Command_CapSet(pRefDat->pObject, kNkMAIDCapability_DataProc, kNkMAIDDataType_Null, (NKPARAM)NULL, NULL, NULL)) return -1;

		if (pRefItm != NULL) {
			// If the item object remains, close it and remove from parent link.
			RemoveChild(pRefSrc, ulItmID);
		}

		return g_fileNo;
	}

	int takePicture(float seconds) {

		ULONG	ulCount = 0L;

		// Start capture
		LPNkMAIDObject pSourceObject = pRefSrc->pObject;
		if (!GetCapInfo(pRefSrc, kNkMAIDCapability_Capture)) return -1;

		LPRefCompletionProc pRefCompletion;
		pRefCompletion = (LPRefCompletionProc)malloc(sizeof(RefCompletionProc));
		pRefCompletion->pulCount = &ulCount;
		pRefCompletion->pRef = NULL;
		if (!Command_CapStart(pSourceObject, kNkMAIDCapability_Capture, (LPNKFUNC)CompletionProc, (NKREF)pRefCompletion, NULL)) return -1;
		IdleLoop(pSourceObject, &ulCount, 1);

		Command_Async(pRefSrc->pObject);

		// Sleep for exposure
		Sleep((DWORD)(seconds * 1000));

		// Terminate capture
		if (!GetCapInfo(pRefSrc, kNkMAIDCapability_TerminateCapture)) return -1;
		NkMAIDTerminateCapture Param;
		Param.ulParameter1 = 0;
		Param.ulParameter2 = 0;

		ulCount = 0;
		pRefCompletion = (LPRefCompletionProc)malloc(sizeof(RefCompletionProc));
		pRefCompletion->pulCount = &ulCount;
		pRefCompletion->pRef = NULL;
		if (!Command_CapStartGeneric(pSourceObject, kNkMAIDCapability_TerminateCapture, (NKPARAM)&Param, (LPNKFUNC)CompletionProc, (NKREF)pRefCompletion, NULL)) return -1;


		// Get item id
		Command_CapGet(pRefSrc->pObject, kNkMAIDCapability_CameraType, kNkMAIDDataType_UnsignedPtr, (NKPARAM)&g_ulCameraType, NULL, NULL);

		LPNkMAIDCapInfo pCapInfo = GetCapInfo(pRefSrc, kNkMAIDCapability_Children);
		if (!pCapInfo || pCapInfo->ulType != kNkMAIDCapType_Enum) return -1;
		if (!CheckCapabilityOperation(pRefSrc, kNkMAIDCapability_Children, kNkMAIDCapOperation_Get)) return -1;

		int retries = 5;
		NkMAIDEnum	stEnum;
		do {
			Sleep(1000);
			if (!Command_CapGet(pRefSrc->pObject, kNkMAIDCapability_Children, kNkMAIDDataType_EnumPtr, (NKPARAM)&stEnum, NULL, NULL)) return -1;
			cout << ".";
			retries--;
		} while (retries > 0 && stEnum.ulElements == 0);
		if (stEnum.ulElements == 0) {
			cout << "No images found" << endl;
			return -1;
		}
		cout << endl;

		if (stEnum.wPhysicalBytes != 4) return -1;
		stEnum.pData = malloc(stEnum.ulElements * stEnum.wPhysicalBytes);
		if (!Command_CapGetArray(pRefSrc->pObject, kNkMAIDCapability_Children, kNkMAIDDataType_EnumPtr, (NKPARAM)&stEnum, NULL, NULL)) {
			free(stEnum.pData);
			return -1;
		}
		ULONG ulItmID = ((ULONG*)stEnum.pData)[0];

		// Acquire item
		LPRefObj pRefItm = GetRefChildPtr_ID(pRefSrc, ulItmID);
		if (pRefItm == NULL) {
			// Create Item object and RefSrc structure.
			if (AddChild(pRefSrc, ulItmID) == TRUE) {
				printf("Item object is opened.\n");
			}
			else {
				printf("Item object can't be opened.\n");
				return -1;
			}
			pRefItm = GetRefChildPtr_ID(pRefSrc, ulItmID);
		}

		LPNkMAIDCapInfo pCapInfo2 = GetCapInfo(pRefItm, kNkMAIDCapability_DataTypes);
		if (pCapInfo2 == NULL) return -1;

		if (!CheckCapabilityOperation(pRefItm, kNkMAIDCapability_DataTypes, kNkMAIDCapOperation_Get)) return -1;

		ULONG	ulDataTypes;
		if (!Command_CapGet(pRefItm->pObject, kNkMAIDCapability_DataTypes, kNkMAIDDataType_UnsignedPtr, (NKPARAM)&ulDataTypes, NULL, NULL)) return -1;
		ULONG	dataType;
		if ((ulDataTypes & kNkMAIDDataObjType_Image) == 0) return -1;

		// reset file removed flag
		g_bFileRemoved = false;

		LPRefObj pRefDat = GetRefChildPtr_ID(pRefItm, kNkMAIDDataObjType_Image);
		if (pRefDat == NULL) {
			// Create Image object and RefSrc structure.
			if (AddChild(pRefItm, kNkMAIDDataObjType_Image) == TRUE) {
				printf("Image object is opened.\n");
			}
			else {
				printf("Image object can't be opened.\n");
				return -1;
			}
			pRefDat = GetRefChildPtr_ID(pRefItm, kNkMAIDDataObjType_Image);
		}

		// set reference from DataProc
		LPRefDataProc pRefDeliver = (LPRefDataProc)malloc(sizeof(RefDataProc));// this block will be freed in CompletionProc.
		pRefDeliver->pBuffer = NULL;
		pRefDeliver->ulOffset = 0L;
		pRefDeliver->ulTotalLines = 0L;
		pRefDeliver->lID = pRefItm->lMyID;
		// set reference from CompletionProc
		ulCount = 0L;
		pRefCompletion = (LPRefCompletionProc)malloc(sizeof(RefCompletionProc));// this block will be freed in CompletionProc.
		pRefCompletion->pulCount = &ulCount;
		pRefCompletion->pRef = pRefDeliver;
		// set reference from DataProc
		NkMAIDCallback	stProc;
		stProc.pProc = (LPNKFUNC)DataProc;
		stProc.refProc = (NKREF)pRefDeliver;

		// set DataProc as data delivery callback function
		if (CheckCapabilityOperation(pRefDat, kNkMAIDCapability_DataProc, kNkMAIDCapOperation_Set) &&
			Command_CapSet(pRefDat->pObject, kNkMAIDCapability_DataProc, kNkMAIDDataType_CallbackPtr, (NKPARAM)&stProc, NULL, NULL) &&
			// start getting an image
			Command_CapStart(pRefDat->pObject, kNkMAIDCapability_Acquire, (LPNKFUNC)CompletionProc, (NKREF)pRefCompletion, NULL)) {

			IdleLoop(pRefDat->pObject, &ulCount, 1);
		}
		// reset DataProc
		if( !Command_CapSet(pRefDat->pObject, kNkMAIDCapability_DataProc, kNkMAIDDataType_Null, (NKPARAM)NULL, NULL, NULL)) return -1;

		if (pRefItm != NULL) {
			// If the item object remains, close it and remove from parent link.
			RemoveChild(pRefSrc, ulItmID);
		}

		return g_fileNo;
	}

	void close() {
		if (pRefMod) {
			// Close Source_Object
			RemoveChild(pRefMod, ulSrcID);

			// Close Module_Object
			Close_Module(pRefMod);
		}
		FreeLibrary(g_hInstModule);
		g_hInstModule = NULL;
		// Free memory blocks allocated in this function.
		if (pRefMod->pObject != NULL) {
			free(pRefMod->pObject);
			pRefMod->pObject = NULL;
		}
		if (pRefMod != NULL) {
			free(pRefMod);
			pRefMod = NULL;
		}
		if (m_hCommPort != 0) {
			::CloseHandle(m_hCommPort);
			m_hCommPort = 0;
		}
	}

	virtual ~CameraAPI() {
		close();
	}

	BOOL isShutterRelease = FALSE;
private:
	LPRefObj pRefMod;
	LPRefObj pRefSrc;
	ULONG ulSrcID;
	int BulbMode = 2;
	HANDLE m_hCommPort = 0;
};

extern "C" {
	__declspec(dllexport) CameraAPI* __stdcall getCameraAPI(int cameraModel) {
		return new CameraAPI(cameraModel);
	}

	__declspec(dllexport) bool open(CameraAPI* cd, int camera, const char* dstDir) {
		cd->setDestDir(dstDir?dstDir:".");
		return cd->openSource(camera) &&
			cd->setBulbMode() &&
			cd->setWhiteBalanceMode(3) &&
			cd->turnOffNR() &&
			cd->setPictureControl() &&
			cd->setCommpressionLevel() &&
			cd->turnOffDLighting();
	}

	__declspec(dllexport) bool setISO(CameraAPI* cd, int iso) {
		return cd->setISO(iso);
	}

	__declspec(dllexport) int takePicture(CameraAPI* cd, float seconds) {
		if (cd->isShutterRelease) {
			return cd->takeShutterReleasePicture(seconds);
		}
		else {
			return cd->takePicture(seconds);
		}
	}

	__declspec(dllexport) bool close(CameraAPI* cd) {
		cd->close();
		delete cd;
		return true;
	}
}

int main()
{
	CameraAPI* cam = getCameraAPI(90);

	if (!open(cam, 1, "C:\\src\\pics")) {
		cout << "Cam setup failed" << endl;
		return -1;
	}

	setISO(cam, 12);

	for (int i = 0; i < 2; i++) {

		cout << "Image: " << takePicture(cam, 5) << endl;

		cout << "Happy Birthday ADITYA !" << endl;
	}
	
	return 0;
}
 