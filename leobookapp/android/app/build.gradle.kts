import java.util.Properties
import java.io.FileInputStream
import org.gradle.api.GradleException

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// ── Load release signing key ────────────────────────────────────────
val keystoreProperties = Properties()
val keystoreFile = rootProject.file("key.properties")
if (keystoreFile.exists()) {
    keystoreProperties.load(FileInputStream(keystoreFile))
}

val keystoreKeys = listOf("keyAlias", "keyPassword", "storeFile", "storePassword")
val hasCompleteSigningConfig = keystoreKeys.all {
    !keystoreProperties.getProperty(it).isNullOrBlank()
}
val releaseStoreFile = if (hasCompleteSigningConfig) {
    rootProject.file(keystoreProperties.getProperty("storeFile"))
} else {
    null
}
val hasReleaseSigning = keystoreFile.exists() &&
    hasCompleteSigningConfig &&
    releaseStoreFile?.exists() == true
val isReleaseTaskRequested = gradle.startParameter.taskNames.any { taskName ->
    taskName.contains("release", ignoreCase = true) ||
        taskName.contains("bundle", ignoreCase = true)
}

if (isReleaseTaskRequested && !hasReleaseSigning) {
    throw GradleException(
        "Release signing is required for LeoBook builds. " +
            "Ensure android/key.properties exists and points to a valid release keystore.",
    )
}

android {
    namespace = "com.materialless.leobookapp"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_11.toString()
    }

    defaultConfig {
        applicationId = "com.materialless.leobookapp"
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        ndkVersion = "27.0.12077973"
    }

    signingConfigs {
        if (hasReleaseSigning) {
            create("release") {
                keyAlias = keystoreProperties.getProperty("keyAlias")
                keyPassword = keystoreProperties.getProperty("keyPassword")
                storeFile = releaseStoreFile
                storePassword = keystoreProperties.getProperty("storePassword")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (hasReleaseSigning) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
        debug {
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

flutter {
    source = "../.."
}
