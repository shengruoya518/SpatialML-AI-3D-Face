package com.pico.spatial.ml.sample.facelandmarker.platform

import android.app.Application
import com.pico.spatial.ml.sample.facelandmarker.FaceHelmetSample
import com.pico.spatial.ui.foundation.dsl.DefaultStage
import com.pico.spatial.ui.foundation.dsl.launch

class MainApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        launch { DefaultStage { FaceHelmetSample() } }
    }
}
