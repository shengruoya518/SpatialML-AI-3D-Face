plugins {
    id("spatialml.sample-application")
    alias(libs.plugins.compose.compiler)
}

android {
    namespace = "com.pico.spatial.ml.sample.facelandmarker"
    defaultConfig { applicationId = "com.pico.spatial.ml.sample.facelandmarker" }
    buildFeatures { buildConfig = true }
    defaultConfig {
        // Enable the integrated experiment only in the explicitly selected validation build.
        buildConfigField(
            "boolean",
            "FACE_INLINE_GEOMETRY",
            providers
                .gradleProperty("faceInlineGeometry")
                .map { it.toBoolean().toString() }
                .getOrElse("false"),
        )
        buildConfigField(
            "boolean",
            "FACE_FUSED_GEOMETRY",
            providers
                .gradleProperty("faceFusedGeometry")
                .map { it.toBoolean().toString() }
                .getOrElse("false"),
        )
        buildConfigField(
            "boolean",
            "FACE_GPU_PREPROCESSING",
            providers
                .gradleProperty("faceGpuPreprocessing")
                .map { it.toBoolean().toString() }
                .getOrElse("false"),
        )
        buildConfigField(
            "boolean",
            "FACE_GPU_SAMPLE_BYTES",
            providers
                .gradleProperty("faceGpuSampleBytes")
                .map { it.toBoolean().toString() }
                .getOrElse("false"),
        )
        buildConfigField(
            "boolean",
            "FACE_RETAINED_VST_PIPELINE",
            providers
                .gradleProperty("faceRetainedVstPipeline")
                .map { it.toBoolean().toString() }
                .getOrElse("false"),
        )
        buildConfigField(
            "boolean",
            "FACE_COMPACT_VST_PIPELINE",
            providers
                .gradleProperty("faceCompactVstPipeline")
                .map { it.toBoolean().toString() }
                .getOrElse("false"),
        )
        buildConfigField(
            "boolean",
            "FACE_FUSED_CONTROL_MODELS",
            providers
                .gradleProperty("faceFusedControlModels")
                .map { it.toBoolean().toString() }
                .getOrElse("false"),
        )
    }
    ndkVersion = "27.0.12077973"
    externalNativeBuild { cmake { path = file("src/main/cpp/CMakeLists.txt") } }
}

// SpatialML's platform bindings are compileOnly in the SDK and live on the headset. Compile the
// public signatures locally because the foundation artifact is absent from the public Maven repo.
// These declarations are never packaged in the APK.
val compilePlatformBindings by
    tasks.registering(JavaCompile::class) {
        source(fileTree("platform-api") { include("**/*.java") })
        classpath = files(android.bootClasspath)
        destinationDirectory.set(layout.buildDirectory.dir("platform-api/classes"))
        sourceCompatibility = "1.8"
        targetCompatibility = "1.8"
    }
val platformBindingsJar by
    tasks.registering(Jar::class) {
        dependsOn(compilePlatformBindings)
        from(compilePlatformBindings.flatMap { it.destinationDirectory })
        archiveFileName.set("spatialml-platform-api.jar")
        destinationDirectory.set(layout.buildDirectory.dir("platform-api"))
    }

dependencies {
    compileOnly(files(platformBindingsJar))
    implementation(libs.spatial.core)
    implementation(libs.spatial.tracking)
    implementation(libs.spatial.ml.readback)
    implementation(libs.activity.compose)
    implementation(libs.lifecycle.runtime.compose)
}
