// Copyright 2026 PICO. All rights reserved.
#include <jni.h>
#include <dlfcn.h>
#include <array>
#include <cmath>

namespace {
void fail(JNIEnv* env, const char* message) {
    env->ThrowNew(env->FindClass("java/lang/IllegalStateException"), message);
}
}

extern "C" JNIEXPORT jfloatArray JNICALL
Java_com_pico_spatial_ml_sample_facelandmarker_CameraCalibration_queryLeftCameraToHead(JNIEnv* env, jobject) {
    // Same public PXRCapture C ABI used by OpenMR's PXRCaptureAPIWrapper. Only metadata is queried;
    // this client never opens/configures a stream. Release still affects the shared device
    // camera, so Kotlin must finish this query before constructing the SpatialML session.
    void* library = dlopen("libpxrcapturendk.so", RTLD_NOW | RTLD_LOCAL);
    if (!library) { fail(env, "Cannot load PICO optical-camera calibration library"); return nullptr; }
    using GetInstance = void* (*)();
    using GetExtrinsics = int (*)(void*, double*, int*, double*, int*);
    using Release = int (*)(void*);
    auto instance = reinterpret_cast<GetInstance>(dlsym(library, "PXRCaptureGetInstance"));
    auto extrinsics = reinterpret_cast<GetExtrinsics>(dlsym(library, "PXRCaptureGetCameraExtrinsics"));
    auto release = reinterpret_cast<Release>(dlsym(library, "PXRCaptureRelease"));
    if (!instance || !extrinsics || !release) {
        dlclose(library); fail(env, "PICO camera calibration API is unavailable"); return nullptr;
    }
    std::array<double, 16> left{}, right{};
    int leftSize = 0, rightSize = 0;
    void* client = instance();
    const int status = client ? extrinsics(client, left.data(), &leftSize, right.data(), &rightSize) : -1;
    const int releaseStatus = client ? release(client) : -1;
    dlclose(library);
    if (status != 0 || releaseStatus != 0 || leftSize != 16 || rightSize != 16) {
        fail(env, "PICO camera calibration did not return two 4x4 matrices"); return nullptr;
    }
    // Match the IMU->OpenXR view conversion in the deployed OpenMR VSTSession. The metadata is
    // row-major, so E(left optical -> head) = imuToHead * leftOpticalToImu, with no Unity Z flip.
    constexpr std::array<double, 16> imuToHead{
        0, -1, 0, .05057, -1, 0, 0, .01874, 0, 0, -1, -.05194, 0, 0, 0, 1
    };
    std::array<float, 16> result{};
    for (int r = 0; r < 4; ++r) for (int c = 0; c < 4; ++c) {
        double value = 0;
        for (int k = 0; k < 4; ++k) value += imuToHead[r * 4 + k] * left[k * 4 + c];
        if (!std::isfinite(value)) { fail(env, "Non-finite optical-camera calibration"); return nullptr; }
        result[r * 4 + c] = static_cast<float>(value);
    }
    jfloatArray array = env->NewFloatArray(16);
    if (array) env->SetFloatArrayRegion(array, 0, 16, result.data());
    return array;
}
