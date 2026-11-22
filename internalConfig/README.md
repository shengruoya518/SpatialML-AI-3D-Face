# Internal Configuration

## APK Naming Configuration

By default, APK files are named as `${appName}-${versionName}-${buildType}.apk`.
You can override this by setting `forceApkName` property. For example:

```shell
./gradlew assembleRelease -PforceApkName=my-app-release.apk
```

## Signing Configuration

By default, release APKs are signed with `release-keystore.jks` in ./internalConfig.
You can override this by setting `signingConfigs.release.storeFile` property. For example:

```shell
./gradlew assembleRelease -PsigningConfigs.release.storeFile=my-keystore.jks
```

## License Configuration

This setup adds official license headers to source files. License templates are stored in ./license.
To apply headers as well as format code, run:

```shell
./gradlew spotlessApply -PenableLicense
```

If you just want to format code, run:

```shell
./gradlew spotlessApply
```
