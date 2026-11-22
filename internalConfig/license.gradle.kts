import java.time.Year

// Year handling
val startYear = 2026
val currentYear = Year.now().value
val yearRange = if (startYear == currentYear) "$currentYear" else "$startYear - $currentYear"

// Templates: template file path -> Spotless target & optional delimiter
data class LicenseTemplate(val template: String, val target: String, val delimiter: String? = null)

val licenseTemplates =
    listOf(
        LicenseTemplate("$rootDir/internalConfig/license/license.kt", "**/*.kt"),
        LicenseTemplate("$rootDir/internalConfig/license/license.xml", "**/*.xml", "<[^!?]")
    )
// Task to generate processed license headers
val generateLicense by
    tasks.registering {
        val outputDir = layout.buildDirectory.dir("generated/license")
        outputs.dir(outputDir)

        doLast {
            licenseTemplates.forEach { tpl ->
                val content = file(tpl.template).readText().replace("\$YEARS", yearRange)
                val outFile = outputDir.get().file(file(tpl.template).name).asFile
                outFile.writeText(content)
            }
        }
    }

tasks.matching { it.name.startsWith("spotless") }.configureEach { dependsOn("generateLicense") }
