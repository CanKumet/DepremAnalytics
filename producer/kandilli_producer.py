# producer/kandilli_producer.py

import requests
import json
import time
from kafka import KafkaProducer
from bs4 import BeautifulSoup

# Kafka ayarları
producer = KafkaProducer(
    bootstrap_servers='localhost:9192',
    value_serializer=lambda x: json.dumps(x, ensure_ascii=False).encode('utf-8')  # Türkçe karakterler için
)

# Kandilli sayfası
KANDILLI_URL = "http://www.koeri.boun.edu.tr/scripts/lst0.asp"


def fetch_kandilli_data(limit=20):
    try:
        response = requests.get(KANDILLI_URL, timeout=10)
        response.encoding = 'windows-1254'

        soup = BeautifulSoup(response.text, "html.parser")
        pre = soup.find("pre")
        if not pre:
            print("❌ <pre> etiketi bulunamadı.")
            return []

        lines = pre.text.strip().split("\n")[6:]  # Veri satırları 7. satırdan itibaren
        depremler = []

        for satir in lines[:limit]:
            try:
                tarih = satir[0:10].strip()
                saat = satir[11:19].strip()
                enlem = float(satir[20:28].strip())
                boylam = float(satir[29:37].strip())
                derinlik_raw = satir[38:45].strip()
                derinlik = float(derinlik_raw) if derinlik_raw.replace('.', '', 1).isdigit() else None
                ml_raw = satir[60:64].strip()
                ml = float(ml_raw) if ml_raw.replace('.', '', 1).isdigit() else None
                yer = satir[71:110].strip()

                deprem = {
                    "tarih": tarih,
                    "saat": saat,
                    "enlem": enlem,
                    "boylam": boylam,
                    "derinlik_km": derinlik,
                    "buyukluk": ml,
                    "yer": yer
                }

                depremler.append(deprem)

            except Exception as e:
                print(f"⚠️ Satır parse hatası: {e} → {satir}")

        return depremler

    except Exception as e:
        print(f"❌ Veri çekme hatası: {e}")
        return []


def main():
    print("✅ Kandilli Producer başlatıldı. Her 60 saniyede veri çekilecek...\n")
    while True:
        veriler = fetch_kandilli_data()
        for deprem in veriler:
            producer.send("deprem-verisi", value=deprem)
            print(f"📤 Gönderildi: {deprem['yer']} - M{deprem['buyukluk']} - {deprem['tarih']} {deprem['saat']}")
        print("⏱ Bekleniyor...\n")
        time.sleep(60)


if __name__ == "__main__":
    main()
