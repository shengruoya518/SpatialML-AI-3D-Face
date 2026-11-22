# Spatial ML

[English](README.md) | [简体中文](README_zh.md)

该项目是一款基于 PICO OS 6 的参考示例应用，使用 PICO Spatial SDK 演示 SpatialML 的能力。这些示例是面向开发者的实践指南，涵盖 CV 算法部署、多模态空间数据作为算法输入、本地机器学习推理的硬件加速、算法输出数据的异步回读（readback）、权限处理，以及 _SpatialML_ 隔离沙箱环境——在充分保护用户隐私的同时，释放应用的 MR 创意潜力。

![Screenshot](.github/screenshot.jpeg)

## 功能特性

项目提供九个可独立运行的 Android 应用目标，并且全部保持使用已发布的 Spatial SDK
`6.1.9` BOM：

- **超分辨率 — 编程式**：使用 Kotlin SpatialML API 构建处理图
- **超分辨率 — Pipeline**：从 schema-v2 pipeline 包加载同等处理图
- **风格化相机 — 编程式**：使用 Kotlin API 构建风格预测和转换流程
- **风格化相机 — Pipeline**：从 pipeline 包加载风格预测和转换流程
- **MediaPipe 人脸 — Pipeline**：加载人脸检测及 SpatialML 检测框显示 pipeline
- **Face Landmarker — Full Space**：通过零尺寸 SpatialML 容器执行推理，读回 478 点人脸网格并在 Stage 坐标中渲染，同时提供 52 个表情系数。参见 [示例指南](FaceLandmarkerApp/README.md)
- **Face Registration Lab**：通过 A/B/C 相机参数实验、同步相机与模型输入采集及棋盘格标定，测量人脸网格的偏移。参见 [实验步骤](FaceRegistrationLabApp/README.md)
- **Pose — Pipeline**：运行 schema-v2 姿态推理，并在 Automatic Stage 中以 13 个蓝色关节和 14 条白色肢体还原原始棍状人指示器。由于
  `6.1.9` BOM 未发布较新的 `SkeletonPoseComponent` 蒙皮网格 API，该目标使用独立标记实体
- **MNIST Wild — Pipeline**：从 VST 相机裁剪图像中识别手写数字，并在 Stage 中的三个显示器上显示裁剪图、分类及置信度

Pose 与 MNIST 包保留了 SpatialSDK 中的模型、脚本、绑定和图顺序。为兼容 `6.1.9` loader，pipeline
JSON 使用等价的 `XR_SECURE_MR_OPERATOR_TYPE_JAVASCRIPT_PICO` 名称，而非较新的
`XR_SECURE_MR_OPERATOR_TYPE_JS_SCRIPTING_PICO` 别名。

超分辨率示例具备以下能力：

- 部署基于神经网络的实时超分辨率模型，用于对透视相机画面进行放大显示
- 提供 Relax 与 SpatialML 两种模式。前者需要用户授予相机权限；后者采用 _SpatialML_ 沙箱，在保护用户隐私的同时实现图像放大
- 实现基于大语言模型的视觉问答（Visual Question Answer，VQA）交互（仅在 RelaxMR 模式下可用），允许用户对放大后的相机画面发起 VQA 查询，并可接入自选的 LLM 后端
- 展示如何使用 Kotlin 协程（Coroutine）异步调用 SpatialML API

## 环境要求

构建和运行本项目前，请参照 PICO Spatial SDK 官方文档完成开发环境配置：

- [PICO Spatial SDK 环境配置指南（中国大陆）](https://developer-cn.picoxr.com/document/spatial-sdk/set-up-development-environment/)
- [PICO Spatial SDK 环境配置指南（非中国大陆）](https://developer.picoxr.com/document/spatial-sdk/set-up-development-environment/)

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd SpatialML
```

### 2. 在 Android Studio 中打开项目

启动 Android Studio，选择 **Open an Existing Project**，然后选择 `SpatialML` 目录。

### **可选** 申请火山引擎 API Key

如上所述，超分辨率示例应用内置了基于大语言模型的视觉问答（VQA）接口，位于 [`SuperResolutionApp/src/main/java/com/pico/spatial/ml/sample/sr/vm/VQAWrapper.kt`](SuperResolutionApp/src/main/java/com/pico/spatial/ml/sample/sr/vm/VQAWrapper.kt)。该接口的内置实现以火山云引擎作为后端。如需开箱即用地体验 VQA 功能，请申请火山引擎 API Key。

申请完成后，连接 PICO 设备，确保已启用 USB 调试，然后执行：

```bash
adb shell setprop debug.spatialml.apikey <API-KEY>
```

若未配置 API Key，进入 _RelaxMR_ 模式后，"Ask AI" 按钮将处于不可点击状态。

### **可选** 替换为自选 VQA 后端

除了申请火山引擎 API Key 外，你也可以将 VQA 接口的默认实现替换为任意符合条件的 VQA 后端，唯一要求是该后端提供 RESTful API。

你可以参考 [`SuperResolutionApp/src/main/java/com/pico/spatial/ml/sample/sr/vm/VQAWrapper.kt`](SuperResolutionApp/src/main/java/com/pico/spatial/ml/sample/sr/vm/VQAWrapper.kt) 中的示例代码；默认实现定义如下：

```kt
val ark
    get() = create<FileUploadResponse, QueryResponse>(
        // ...
    )
```

### 3.运行项目

PICO 模拟器暂**不支持** SpatialML 功能，请使用搭载 PICO OS 6 的物理设备运行本示例。

1. 将 PICO 设备连接至开发机
2. 在设备上启用 **USB 调试（USB Debugging）**
3. 使用 Gradle 同步项目，使 Android Studio 发现九个应用模块
4. 在 Android Studio 的运行目标中选择一个应用模块并部署
5. 运行时可通过 `SpatialML::Server` 标签过滤 logcat 日志

## 项目结构

每个示例都是独立 Android 应用模块，具有自己的包名、Manifest、资源、APK 和 Android
Studio 运行目标：

```bash
SpatialML/
├── SuperResolutionApp/                 # 编程式超分辨率
├── SuperResolutionPipelineApp/         # Pipeline 超分辨率
├── StylizedApp/                        # 编程式风格化相机
├── StylizedPipelineApp/                # Pipeline 风格化相机
├── FaceMediaPipePipelineApp/           # MediaPipe 人脸 Pipeline
├── FaceLandmarkerApp/                  # Full Space 透视人脸网格与表情系数
├── FaceRegistrationLabApp/             # 相机与 Stage 注册测量实验
├── PosePipelineApp/                    # Pose Pipeline 与 Stage 标记渲染
├── MnistWildPipelineApp/               # MNIST Wild Pipeline 与 Stage 显示器
├── common/                             # 共享的非运行示例工具库
├── shared-assets/                      # 编程式与 Pipeline 示例共享资源
├── buildSrc/                           # 共享示例应用 Gradle 约定
├── gradle/                               # Gradle 依赖与构建脚本
├── build.gradle.kts                      # 根构建配置
└── settings.gradle.kts                   # 项目设置与 SDK 配置
```

使用以下命令构建九个 APK：

```bash
./gradlew assembleDebug
```

## 学习资源

深入了解空间应用开发，欢迎访问官方开发者网站获取完整资源：

- [PICO 开发者网站（中国大陆）](https://developer-cn.picoxr.com/)
- [PICO 开发者网站（非中国大陆）](https://developer.picoxr.com/)

## 许可证

© 2026 PICO。本项目的源代码依据 [Apache 2.0 License](LICENSE.txt) 协议开源。本项目的美术资产（包括但不限于纹理、3D 模型和音频）基于 [Creative Commons BY 4.0](https://creativecommons.org/licenses/by/4.0/) 授权。

## 支持

如有任何问题、疑惑或功能建议，欢迎通过 [PICO 开发者支持门户](https://picodevsupport.freshdesk.com/support/home) 提交工单与我们联系。

---

为空间应用开发者提供的官方参考示例
