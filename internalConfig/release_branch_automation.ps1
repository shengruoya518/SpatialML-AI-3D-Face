# Exit on error
$ErrorActionPreference = "Stop"

# Check if required arguments are provided
if ($args.Count -ne 2) {
    Write-Host "Usage: .\internalConfig\release_branch_automation.ps1 <SDK_VERSION> <SPATIAL_TOOLS_VERSION>"
    Write-Host "Example: .\internalConfig\release_branch_automation.ps1 0.7.8 0.0.1-alpha.21"
    exit 1
}

$SDK_VERSION = $args[0]
$SPATIAL_TOOLS_VERSION = $args[1]
$MAVEN_URL = "https://artifact.bytedance.com/repository/Volcengine"  # Maven URL for publishing
$GRADLE_DISTRIBUTION_URL = "https\://services.gradle.org/distributions/gradle-8.10.2-bin.zip"

Write-Host "=========================================="
Write-Host "Release Script"
Write-Host "=========================================="
Write-Host "SDK_VERSION: $SDK_VERSION"
Write-Host "SPATIAL_TOOLS_VERSION: $SPATIAL_TOOLS_VERSION"
Write-Host "MAVEN_URL: $MAVEN_URL"
Write-Host "GRADLE_DISTRIBUTION_URL: $GRADLE_DISTRIBUTION_URL"
Write-Host "=========================================="
Write-Host ""

# 1. Create and checkout new release branch
Write-Host "Step 1: Creating and checking out release branch..."
git checkout -b "release/$SDK_VERSION"
Write-Host "[OK]" -ForegroundColor Green -NoNewline
Write-Host " Branch release/$SDK_VERSION created"
Write-Host ""

# 2. Update Spatial SDK version in libs.versions.toml
Write-Host "Step 2: Updating Spatial SDK version in libs.versions.toml..."
if (Test-Path "gradle/libs.versions.toml") {
    (Get-Content "gradle/libs.versions.toml") -replace 'spatialBom = "[^"]*"', "spatialBom = `"$SDK_VERSION`"" | Set-Content "gradle/libs.versions.toml"
    Write-Host "[OK]" -ForegroundColor Green -NoNewline
    Write-Host " Updated spatialBom version in libs.versions.toml"
}
elseif (Test-Path "libs.versions.toml") {
    (Get-Content "libs.versions.toml") -replace 'spatialBom = "[^"]*"', "spatialBom = `"$SDK_VERSION`"" | Set-Content "libs.versions.toml"
    Write-Host "[OK]" -ForegroundColor Green -NoNewline
    Write-Host " Updated spatialBom version in libs.versions.toml"
}
else {
    Write-Host "[!]" -ForegroundColor Yellow -NoNewline
    Write-Host " Warning: libs.versions.toml not found"
}
Write-Host ""

# 3. Update Spatial Tools version in editor-asset module's build.gradle
Write-Host "Step 3: Updating Spatial Tools version in editor-asset module's build.gradle..."
if (Test-Path "editor-asset/build.gradle") {
    (Get-Content "editor-asset/build.gradle") -replace "id 'com\.pico\.spatial\.tools' version '[^']*'", "id 'com.pico.spatial.tools' version '$SPATIAL_TOOLS_VERSION'" | Set-Content "editor-asset/build.gradle"
    Write-Host "[OK]" -ForegroundColor Green -NoNewline
    Write-Host " Updated plugin version in editor-asset/build.gradle"
}
elseif (Test-Path "editor-asset/build.gradle.kts") {
    (Get-Content "editor-asset/build.gradle.kts") -replace 'id\("com\.pico\.spatial\.tools"\) version "[^"]*"', "id(`"com.pico.spatial.tools`") version `"$SPATIAL_TOOLS_VERSION`"" | Set-Content "editor-asset/build.gradle.kts"
    Write-Host "[OK]" -ForegroundColor Green -NoNewline
    Write-Host " Updated plugin version in editor-asset/build.gradle.kts"
}
else {
    Write-Host "[!]" -ForegroundColor Yellow -NoNewline
    Write-Host " Warning: editor-asset module not found or no build.gradle file"
}
Write-Host ""

# 4. Update maven URL in settings.gradle.kts
Write-Host "Step 4: Updating maven URL in settings.gradle.kts..."
if (Test-Path "settings.gradle.kts") {
    (Get-Content "settings.gradle.kts") -replace 'url = uri\("[^"]+"\)', "url = uri(`"$MAVEN_URL`")" | Set-Content "settings.gradle.kts"
    Write-Host "[OK]" -ForegroundColor Green -NoNewline
    Write-Host " Updated Maven URLs in settings.gradle.kts"
}
else {
    Write-Host "[!]" -ForegroundColor Yellow -NoNewline
    Write-Host " Warning: settings.gradle.kts not found"
}
Write-Host ""

# 5. Update Gradle wrapper distribution URL
Write-Host "Step 5: Updating Gradle distribution URL..."
if (Test-Path "gradle/wrapper/gradle-wrapper.properties") {
    (Get-Content "gradle/wrapper/gradle-wrapper.properties") -replace 'distributionUrl=.*', "distributionUrl=$GRADLE_DISTRIBUTION_URL" | Set-Content "gradle/wrapper/gradle-wrapper.properties"
    Write-Host "[OK]" -ForegroundColor Green -NoNewline
    Write-Host " Updated distributionUrl in gradle-wrapper.properties"
}
else {
    Write-Host "[!]" -ForegroundColor Yellow -NoNewline
    Write-Host " Warning: gradle/wrapper/gradle-wrapper.properties not found"
}
Write-Host ""

# 6. Delete internalConfig folder and the script itself
Write-Host "Step 6: Deleting internalConfig folder for a clean release..."
if (Test-Path "internalConfig") {
    # Remove internal config block from root build.gradle.kts before deleting the folder
    if (Test-Path "build.gradle.kts") {
        $content = Get-Content "build.gradle.kts" -Raw
        $content = $content -replace '(?s)// >>> INTERNAL_CONFIG_BLOCK_START.*?// <<< INTERNAL_CONFIG_BLOCK_END\s*', ''
        Set-Content "build.gradle.kts" -Value $content
        Write-Host "[OK]" -ForegroundColor Green -NoNewline
        Write-Host " Removed internal configuration block from root build.gradle.kts"
    }

    # In PowerShell, we can use a small hack to delete the folder after the script finishes
    # but usually, just deleting the folder works if the script is running from it.
    # However, it's safer to use -Force.
    Remove-Item -Path "internalConfig" -Recurse -Force
    Write-Host "[OK]" -ForegroundColor Green -NoNewline
    Write-Host " Deleted internalConfig folder (Zero-Trace achieved)"
}
else {
    Write-Host "[!]" -ForegroundColor Yellow -NoNewline
    Write-Host " Warning: internalConfig folder not found"
}
Write-Host ""

Write-Host "=========================================="
Write-Host "[OK]" -ForegroundColor Green -NoNewline
Write-Host " All steps completed successfully!"
Write-Host "=========================================="
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Review the changes: git status"
Write-Host "2. Commit the changes: git add . && git commit -m 'Release $SDK_VERSION'"
Write-Host "3. Push the branch: git push origin release/$SDK_VERSION"
Write-Host ""
