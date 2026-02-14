import yfinance as yf
import requests
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import pytz

# --- AYARLAR ---
PUSHCUT_URL = "https://api.pushcut.io/v1/notifications/HisseRaporu" 

# --- FIREBASE BAĞLANTISI ---
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def borsa_acik_mi():
    # Türkiye saat dilimini ayarla
    tz = pytz.timezone('Europe/Istanbul')
    simdi = datetime.now(tz)
    
    # Hafta sonu mu? (5 = Cumartesi, 6 = Pazar)
    if simdi.weekday() >= 5:
        return False
    
    # Saat 10:00 ile 18:15 arası mı?
    saat_dakika = simdi.hour * 100 + simdi.minute
    if 1000 <= saat_dakika <= 1815:
        return True
    
    return False

def borsa_robotu():
    hisseler_ref = db.collection("hisseler").order_by("sira").stream()
    bildirim_metni = ""
    
    for doc in hisseler_ref:
        hisse_data = doc.to_dict()
        hisse_kod = hisse_data.get('kod')
        
        try:
            hisse = yf.Ticker(hisse_kod)
            data = hisse.history(period="1d", interval="1m")
            
            if not data.empty:
                guncel_fiyat = round(data['Close'].iloc[-1], 2)
                try:
                    onceki_kapanis = hisse.fast_info['previousClose']
                except:
                    onceki_kapanis = data['Open'].iloc[0]
                
                degisim = round(((guncel_fiyat - onceki_kapanis) / onceki_kapanis) * 100, 2)
                
                # Veritabanını her zaman güncelle (Panel güncel kalsın)
                db.collection("hisseler").document(doc.id).update({
                    "fiyat": guncel_fiyat,
                    "degisim": degisim
                })
                
                # Rapor metnini hazırla
                emoji = "🟢" if degisim > 0 else "🔴" if degisim < 0 else "⚪"
                bildirim_metni += f"{emoji} {hisse_kod.replace('.IS','')}: {guncel_fiyat} TL (%{degisim:+})\n"
                
        except Exception as e:
            print(f"Hata ({hisse_kod}): {e}")

    # --- BİLDİRİM GÖNDERME KONTROLÜ ---
    if bildirim_metni:
        if borsa_acik_mi():
            try:
                payload = {"text": bildirim_metni, "title": "🏹 BİST Avcısı Canlı"}
                requests.post(PUSHCUT_URL, json=payload)
                print("Borsa açık: Bildirim gönderildi.")
            except Exception as e:
                print(f"Pushcut Hatası: {e}")
        else:
            print("Borsa kapalı: Veriler güncellendi ama bildirim gönderilmedi.")

if __name__ == "__main__":
    borsa_robotu()
