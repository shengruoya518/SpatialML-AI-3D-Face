#!/bin/bash

set -e  # Exit on error

# Check if required arguments are provided
if [ "$#" -ne 2 ]; then
    echo "Usage: bash internalConfig/release_branch_automation.sh <SDK_VERSION> <SPATIAL_TOOLS_VERSION>"
    echo "Example: bash internalConfig/release_branch_automation.sh 0.7.8 0.0.1-alpha.21"
    exit 1
fi

SDK_VERSION=$1
SPATIAL_TOOLS_VERSION=$2
MAVEN_URL="https://artifact.bytedance.com/repository/Volcengine"  # Maven URL for publishing
GRADLE_DISTRIBUTION_URL="https\://services.gradle.org/distributions/gradle-8.10.2-bin.zip"

echo "=========================================="
echo "Release Script"
echo "=========================================="
echo "SDK_VERSION: ${SDK_VERSION}"
echo "SPATIAL_TOOLS_VERSION: ${SPATIAL_TOOLS_VERSION}"
echo "MAVEN_URL: ${MAVEN_URL}"
echo "GRADLE_DISTRIBUTION_URL: ${GRADLE_DISTRIBUTION_URL}"
echo "=========================================="
echo ""

# 1. Create and checkout new release branch
echo "Step 1: Creating and checking out release branch..."
git checkout -b "release/${SDK_VERSION}"
echo "✅ Branch release/${SDK_VERSION} created"
echo ""

# 2. Update Spatial SDK version in libs.versions.toml
echo "Step 2: Updating Spatial SDK version in libs.versions.toml..."
if [ -f "gradle/libs.versions.toml" ]; then
    sed -i.bak "s/spatialBom = \".*\"/spatialBom = \"${SDK_VERSION}\"/" gradle/libs.versions.toml
    rm gradle/libs.versions.toml.bak
    echo "✅ Updated spatialBom version in libs.versions.toml"
elif [ -f "libs.versions.toml" ]; then
    sed -i.bak "s/spatialBom = \".*\"/spatialBom = \"${SDK_VERSION}\"/" libs.versions.toml
    rm libs.versions.toml.bak
    echo "✅ Updated spatialBom version in libs.versions.toml"
else
    echo "⚠️ Warning: libs.versions.toml not found"
fi
echo ""

# 3. Update Spatial Tools version in editor-asset module's build.gradle
echo "Step 3: Updating Spatial Tools version in editor-asset module's build.gradle..."
if [ -f "editor-asset/build.gradle" ]; then
    sed -i.bak "s/id 'com\.pico\.spatial\.tools' version '[^']*'/id 'com.pico.spatial.tools' version '${SPATIAL_TOOLS_VERSION}'/" editor-asset/build.gradle
    rm editor-asset/build.gradle.bak
    echo "✅ Updated plugin version in editor-asset/build.gradle"
elif [ -f "editor-asset/build.gradle.kts" ]; then
    sed -i.bak "s/id(\"com\.pico\.spatial\.tools\") version \"[^\"]*\"/id(\"com.pico.spatial.tools\") version \"${SPATIAL_TOOLS_VERSION}\"/" editor-asset/build.gradle.kts
    rm editor-asset/build.gradle.kts.bak
    echo "✅ Updated plugin version in editor-asset/build.gradle.kts"
else
    echo "⚠️ Warning: editor-asset module not found or no build.gradle file"
fi
echo ""

# 4. Update maven URL in settings.gradle.kts
echo "Step 4: Updating maven URL in settings.gradle.kts..."
if [ -f "settings.gradle.kts" ]; then
    # Replace all maven url occurrences
    sed -i.bak -E "s|url = uri\(\"[^\"]+\"\)|url = uri(\"${MAVEN_URL}\")|g" settings.gradle.kts
    rm settings.gradle.kts.bak
    echo "✅ Updated Maven URLs in settings.gradle.kts"
else
    echo "⚠️ Warning: settings.gradle.kts not found"
fi
echo ""

# 5. Update Gradle wrapper distribution URL
echo "Step 5: Updating Gradle distribution URL..."
if [ -f "gradle/wrapper/gradle-wrapper.properties" ]; then
    sed -i.bak "s|distributionUrl=.*|distributionUrl=${GRADLE_DISTRIBUTION_URL}|" gradle/wrapper/gradle-wrapper.properties
    rm gradle/wrapper/gradle-wrapper.properties.bak
    echo "✅ Updated distributionUrl in gradle-wrapper.properties"
else
    echo "⚠️ Warning: gradle/wrapper/gradle-wrapper.properties not found"
fi
echo ""

# 6. Delete internalConfig folder and the script itself
echo "Step 6: Deleting internalConfig folder for a clean release..."
if [ -d "internalConfig" ]; then
    # Remove internal config block from root build.gradle.kts before deleting the folder
    if [ -f "build.gradle.kts" ]; then
        perl -i.bak -0pe 's/\/\/ >>> INTERNAL_CONFIG_BLOCK_START.*?\/\/ <<< INTERNAL_CONFIG_BLOCK_END\n//gs' build.gradle.kts
        rm build.gradle.kts.bak
        echo "✅ Removed internal configuration block from root build.gradle.kts"
    fi

    # We use a subshell to delete the folder after the script finishes or during its last breath
    # In bash, once the script is loaded, it can usually finish even if deleted
    rm -rf internalConfig
    echo "✅ Deleted internalConfig folder (Zero-Trace achieved)"
else
    echo "⚠️ Warning: internalConfig folder not found"
fi
echo ""

echo "=========================================="
echo "✅ All steps completed successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Review the changes: git status"
echo "2. Commit the changes: git add . && git commit -m 'Release ${SDK_VERSION}'"
echo "3. Push the branch: git push origin release/${SDK_VERSION}"
echo ""
