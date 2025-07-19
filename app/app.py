from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from kafka import KafkaConsumer
import json
import threading
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'kandilli-deprem-dashboard-2024'
socketio = SocketIO(app, cors_allowed_origins="*")


# SQLite veritabanı oluştur
def init_db():
    if not os.path.exists('deprem.db'):
        conn = sqlite3.connect('deprem.db')
        c = conn.cursor()
        c.execute('''
            CREATE TABLE depremler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tarih TEXT,
                saat TEXT,
                enlem REAL,
                boylam REAL,
                derinlik_km REAL,
                buyukluk REAL,
                yer TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()


# Kafka Consumer'dan verileri al ve WebSocket'e gönder
def kafka_consumer_thread():
    try:
        consumer = KafkaConsumer(
            'deprem-verisi',
            bootstrap_servers=['localhost:9192'],
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            auto_offset_reset='latest'
        )

        print("🔗 Kafka Consumer başlatıldı...")

        for message in consumer:
            deprem_data = message.value

            # Veritabanına kaydet
            save_to_db(deprem_data)

            # WebSocket ile frontend'e gönder
            socketio.emit('yeni_deprem', deprem_data, broadcast=True)
            print(f"📡 WebSocket'e gönderildi: {deprem_data['yer']} - M{deprem_data['buyukluk']}")

    except Exception as e:
        print(f"❌ Kafka Consumer hatası: {e}")


def save_to_db(deprem_data):
    try:
        conn = sqlite3.connect('deprem.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO depremler (tarih, saat, enlem, boylam, derinlik_km, buyukluk, yer)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            deprem_data['tarih'],
            deprem_data['saat'],
            deprem_data['enlem'],
            deprem_data['boylam'],
            deprem_data['derinlik_km'],
            deprem_data['buyukluk'],
            deprem_data['yer']
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ Veritabanı kayıt hatası: {e}")


def get_recent_earthquakes(limit=50):
    """Son depremleri getir"""
    conn = sqlite3.connect('deprem.db')
    c = conn.cursor()
    c.execute('''
        SELECT tarih, saat, enlem, boylam, derinlik_km, buyukluk, yer, timestamp
        FROM depremler 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (limit,))

    columns = [description[0] for description in c.description]
    results = [dict(zip(columns, row)) for row in c.fetchall()]
    conn.close()
    return results


def get_statistics():
    """İstatistikler"""
    conn = sqlite3.connect('deprem.db')
    c = conn.cursor()

    # Toplam deprem sayısı
    c.execute('SELECT COUNT(*) FROM depremler')
    total_count = c.fetchone()[0]

    # En büyük deprem
    c.execute('SELECT MAX(buyukluk) FROM depremler WHERE buyukluk IS NOT NULL')
    max_magnitude = c.fetchone()[0] or 0

    # Ortalama büyüklük
    c.execute('SELECT AVG(buyukluk) FROM depremler WHERE buyukluk IS NOT NULL')
    avg_magnitude = c.fetchone()[0] or 0

    # Bugünkü deprem sayısı
    c.execute('''
        SELECT COUNT(*) FROM depremler 
        WHERE date(timestamp) = date('now')
    ''')
    today_count = c.fetchone()[0]

    # En aktif bölgeler
    c.execute('''
        SELECT yer, COUNT(*) as count 
        FROM depremler 
        GROUP BY yer 
        ORDER BY count DESC 
        LIMIT 5
    ''')
    top_locations = c.fetchall()

    conn.close()

    return {
        'total_count': total_count,
        'max_magnitude': round(max_magnitude, 1) if max_magnitude else 0,
        'avg_magnitude': round(avg_magnitude, 2) if avg_magnitude else 0,
        'today_count': today_count,
        'top_locations': top_locations
    }


@app.route('/')
def index():
    recent_earthquakes = get_recent_earthquakes(20)
    stats = get_statistics()
    return render_template('index.html', earthquakes=recent_earthquakes, stats=stats)


@app.route('/api/recent/<int:limit>')
def api_recent(limit=50):
    earthquakes = get_recent_earthquakes(limit)
    return json.dumps(earthquakes, ensure_ascii=False)


@app.route('/api/stats')
def api_stats():
    return json.dumps(get_statistics(), ensure_ascii=False)


@socketio.on('connect')
def handle_connect():
    print('👤 Kullanıcı bağlandı')
    emit('status', {'msg': 'Kandilli Deprem Dashboard\'a bağlandınız'})


@socketio.on('disconnect')
def handle_disconnect():
    print('👋 Kullanıcı ayrıldı')


if __name__ == '__main__':
    init_db()

    # Kafka Consumer'ı ayrı thread'de başlat
    consumer_thread = threading.Thread(target=kafka_consumer_thread, daemon=True)
    consumer_thread.start()

    print("🚀 Flask Dashboard başlatılıyor...")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)