#include <windows.h>
#include <SimConnect.h>
#include <iostream>

int main() {
    std::cout << "CrewBridge backend starting...\n";

    HANDLE hSimConnect = nullptr;
    if (SUCCEEDED(SimConnect_Open(&hSimConnect, "CrewBridge Client", nullptr, 0, 0, 0))) {
        std::cout << "Connected to SimConnect!\n";
    } else {
        std::cerr << "Failed to connect to SimConnect\n";
        return 1;
    }

    while (true) {
        SimConnect_CallDispatch(hSimConnect,
            [](SIMCONNECT_RECV* pData, DWORD cbData, void* pContext) {

                


            }, nullptr);

        Sleep(6);
    }
    SimConnect_Close(hSimConnect);
    return 0;
}
