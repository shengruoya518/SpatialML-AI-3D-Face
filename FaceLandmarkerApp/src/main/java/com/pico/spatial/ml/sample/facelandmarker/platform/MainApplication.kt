package com.pico.spatial.ml.sample.facelandmarker.platform

import android.app.Application
import com.pico.spatial.ml.sample.facelandmarker.FaceLandmarkerSample
import com.pico.spatial.ui.foundation.dsl.DefaultStage
import com.pico.spatial.ui.foundation.dsl.launch

class MainApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        // FaceHelmetSample needs occlusion/face-occlusion.bundle, still a Git LFS stub here.
        launch { DefaultStage { FaceLandmarkerSample() } }
    }
}
