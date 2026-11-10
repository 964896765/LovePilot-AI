package com.lovepilot.ai

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.Mac
import javax.crypto.spec.GCMParameterSpec

/** Android Keystore owns the non-exportable AES key. */
class SecurePrefs(context: Context) {
    private val prefs = context.getSharedPreferences("secure_connection", Context.MODE_PRIVATE)

    @Synchronized
    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val alias = "lovepilot.aes.v1"
        if (!store.containsAlias(alias)) {
            KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore").apply {
                init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256).build())
            }.generateKey()
        }
        return store.getKey(alias, null) as SecretKey
    }

    fun seal(value: String): String {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val data = byteArrayOf(1) + cipher.iv + cipher.doFinal(value.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(data, Base64.NO_WRAP)
    }

    fun unseal(value: String): String {
        val data = Base64.decode(value, Base64.NO_WRAP)
        require(data.size >= 30 && data[0] == 1.toByte()) { "本地配置需要重新输入" }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, data.copyOfRange(1, 13)))
        return String(cipher.doFinal(data.copyOfRange(13, data.size)), Charsets.UTF_8)
    }

    fun read(name: String, fallback: String = ""): String =
        prefs.getString(name, null)?.let { unseal(it) } ?: fallback

    fun saveConnection(url: String, token: String) {
        require(prefs.edit().putString("url", seal(url)).putString("token", seal(token)).commit()) {
            "本地连接配置保存失败"
        }
    }

    fun clear() { prefs.edit().clear().apply() }

    @Synchronized
    fun fingerprint(value: String): String {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        val alias = "lovepilot.hmac.v1"
        if (!store.containsAlias(alias)) {
            KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_HMAC_SHA256, "AndroidKeyStore").apply {
                init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY)
                    .setDigests(KeyProperties.DIGEST_SHA256).setKeySize(256).build())
            }.generateKey()
        }
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(store.getKey(alias, null))
        return Base64.encodeToString(mac.doFinal(value.toByteArray(Charsets.UTF_8)), Base64.NO_WRAP)
    }
}
