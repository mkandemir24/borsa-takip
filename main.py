import yfinance as yf
import requests
import firebase_admin
from firebase_admin import credentials, firestore

# --- AYARLAR ---
# Pushcut uygulamasından aldığın Webhook URL'sini buraya yapıştır
PUSHCUT_URL = "https://api.pushcut.io/sm78-WPw1gBiPwMsry-Xg/notifications/MyNotification" 

# --- FIREBASE BAĞLANTISI ---
if not firebase_admin._apps:
    # GitHub Secrets'a eklediğimiz anahtar buraya otomatik gelecek
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def borsa_robotu():
    hisseler_ref = db.collection("hisseler").order_by("sira").stream()
    bildirim_metni = ""
    
    for doc in hisseler_ref:
        hisse_data = doc.to_dict()
        hisse_kod = hisse_data.get('kod')
        
        try:
            # Yahoo Finance'den son 2 günlük veriyi çek
            hisse = yf.Ticker(hisse_kod)
            hist = hisse.history(period="2d")
            
            if len(hist) >= 2:
                guncel_fiyat = round(hist['Close'].iloc[-1], 2)
                onceki_kapanis = hist['Close'].iloc[-2]
                degisim = round(((guncel_fiyat - onceki_kapanis) / onceki_kapanis) * 100, 2)
                
                # Veritabanını (Paneli) güncelle
                db.collection("hisseler").document(doc.id).update({
                    "fiyat": guncel_fiyat,
                    "degisim": degisim
                })
                
                # Bildirim metnine ekle
                emoji = "🟢" if degisim > 0 else "🔴" if degisim < 0 else "⚪"
                bildirim_metni += f"{emoji} {hisse_kod.replace('.IS','')}: {guncel_fiyat} TL (%{degisim:+})\n"
                
        except Exception as e:
            print(f"Hata ({hisse_kod}): {e}")

    # --- PUSHCUT BİLDİRİMİ ---
    if bildirim_metni:
        try:
            payload = {
                "text": bildirim_metni,
                "title": "🏹 BİST Avcısı Raporu"
            }
            requests.post(PUSHCUT_URL, json=payload)
            print("Bildirim gönderildi!")
        except Exception as e:
            print(f"Pushcut Hatası: {e}")

if __name__ == "__main__":
    borsa_robotu()
