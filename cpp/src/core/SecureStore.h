#pragma once
#include <QString>

// Penyandian rahasia at-rest (padanan src/secure_store.py).
// Skema: keystream CTR berbasis SHA-256(key || counter) di-XOR dengan plaintext,
// hasilnya base64 dengan prefix "v1:". Kunci 32-byte disimpan di berkas .secret_key.
//
// CATATAN: ini obfuscation kuat-ringan (bukan AES bersertifikat). Cukup untuk
// menyamarkan API key/password lokal. Upgrade ke AES/OpenSSL bisa di tahap lanjut.
namespace SecureStore {

// Path berkas kunci (default ".secret_key" di CWD). Bisa diubah untuk test.
void setKeyFilePath(const QString &path);
QString keyFilePath();

// Enkripsi -> token "v1:<base64>". String kosong -> "".
QString encrypt(const QString &plain);

// Dekripsi token. Mendukung format lama (base64 polos tanpa prefix) demi
// kompatibilitas mundur. Gagal -> kembalikan input apa adanya.
QString decrypt(const QString &token);

} // namespace SecureStore
