## DualSensePilot v1.0.0

PS5 DualSense kolu için özelleştirme ve emülasyon aracı: adaptif tetikler, ışık çubuğu/LED, titreşim, Xbox 360 / DualShock 4 emülasyonu, profiller.

### Kurulum
`DualSensePilot_Setup.exe` dosyasını indir ve çalıştır. Sihirbaz kurulum klasörünü seçtirir. Sürücüler (ViGEmBus, HidHide) bilgisayarında yoksa kurulur; bu yüzden yönetici izni ister.

Dosya dijital olarak imzalı değildir, Windows SmartScreen uyarı verebilir ("Yine de çalıştır"). Neyin kurulduğunu, internet kullanmadığını ve nasıl doğrulayacağını [README](https://github.com/N0CR-Y/DualSensePilot#kurmadan-önce-incele) anlatıyor.

### SHA-256
```
CB7277AA7914F2E46A7F4F1B6938216E63411CA942A6FF33959F8CF02B26467F  DualSensePilot_Setup.exe
```
PowerShell: `Get-FileHash .\DualSensePilot_Setup.exe -Algorithm SHA256`

### Test durumu
Bluetooth ile gerçek bir DualSense üzerinde denendi (giriş raporları, çıkış raporları, tetik efektleri, X360 eşlemesi, titreşim geri bildirimi). USB bağlantısı kod tarafında destekleniyor ama donanımda ayrıca denenmedi.
