# Bazani tozalash (sinov ma'lumotlarini o'chirish)

`reset_data.py` hamma ishchi ma'lumotni o'chiradi: tovarlar, qoldiq, kirim, savdo, qarz, pul amallari,
mijozlar, omborlar, yetkazib beruvchilar, tarix. **Xodimlar va direktor kirish huquqi qoladi.**
Qaytarib bo'lmaydi, lekin skript o'chirishdan oldin tekshirilgan zaxira nusxa oladi.

## Serverda

1. Avval reja (hech narsa o'chmaydi):
   ```
   sudo -u topshinalar /opt/topshinalar/.venv/bin/python /opt/topshinalar/reset_data.py
   ```
2. Xizmatlarni to'xtating:
   ```
   sudo systemctl stop topshinalar topshinalar-miniapp
   ```
3. O'chirish (zaxira avtomatik `/var/lib/topshinalar/backups` ga tushadi):
   ```
   sudo -u topshinalar /opt/topshinalar/.venv/bin/python /opt/topshinalar/reset_data.py --confirm
   ```
4. Xizmatlarni yoqing va tekshiring:
   ```
   sudo systemctl start topshinalar topshinalar-miniapp
   systemctl is-active topshinalar topshinalar-miniapp
   ```

## Eslatmalar

- Xato bo'lsa hech narsa o'zgarmaydi (bitta tranzaksiya, orqaga qaytariladi).
- Xabar guruhi (`NOTIFY_*`) kursori ham tozalanadi, eski amallar guruhga yuborilmaydi.
- Sayt katalogiga (`catalog_sync`) oldin chiqarilgan tovarlar saytda qolishi mumkin. Sayt tomonini alohida tekshiring.
- Zaxirani qaytarish: `RESTORE-DATA.bat` / `deploy/VPS-UZ.md` dagi tiklash qadamlari.
