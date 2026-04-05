// Load the signing configuration from the .env file
val keystoreProperties = Properties().apply {
    load(file("../../leobookapp/.env"))
}

android {
    signingConfigs {
        create("release") {
            storeFile = file(keystoreProperties.getProperty("KEYSTORE_PATH"))
            storePassword = keystoreProperties.getProperty("LEOBOOK_STORE_PASSWORD")
            keyAlias = keystoreProperties.getProperty("LEOBOOK_KEY_ALIAS")
            keyPassword = keystoreProperties.getProperty("LEOBOOK_KEY_PASSWORD")
        }
    }
}