#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kandilli Deprem Dashboard - Ana Orchestrator
Tüm sistem bileşenlerini koordineli şekilde başlatır ve yönetir.
"""

import subprocess
import time
import os
import signal
import sys
import platform
import psutil
from pathlib import Path


class KandilliOrchestrator:
    def __init__(self):
        self.processes = {}
        self.python_path = self._get_python_path()
        self.project_root = Path(__file__).parent

    def _get_python_path(self):
        """Sistem için uygun Python yolunu belirle"""
        if platform.system() == "Windows":
            # Windows için .venv kontrol
            venv_python = Path(".venv/Scripts/python.exe")
            if venv_python.exists():
                return str(venv_python.absolute())
        else:
            # Linux/Mac için .venv kontrol
            venv_python = Path(".venv/bin/python")
            if venv_python.exists():
                return str(venv_python.absolute())

        # Sistem Python'unu kullan
        return sys.executable

    def check_dependencies(self):
        """Gerekli dosyaların varlığını kontrol et"""
        required_files = [
            "producer/kandilli_producer.py",
            "consumer/spark_streaming.py",
            "app/app.py",
            "app/templates/index.html"
        ]

        missing_files = []
        for file in required_files:
            if not (self.project_root / file).exists():
                missing_files.append(file)

        if missing_files:
            print(f"❌ Eksik dosyalar: {', '.join(missing_files)}")
            print("Lütfen eksik dosyaları oluşturun ve tekrar deneyin.")
            return False

        return True

    def check_kafka_connection(self):
        """Kafka sunucusunun çalışıp çalışmadığını kontrol et"""
        try:
            from kafka import KafkaProducer
            producer = KafkaProducer(
                bootstrap_servers=['localhost:9192'],
                request_timeout_ms=5000
            )
            producer.close()
            print("✅ Kafka bağlantısı başarılı")
            return True
        except Exception as e:
            print(f"❌ Kafka bağlantı hatası: {e}")
            print("Lütfen Kafka sunucusunu başlatın (localhost:9192)")
            return False

    def start_process(self, name, script_path, wait_time=2):
        """Bir süreç başlat ve takip et"""
        try:
            print(f"[{len(self.processes) + 1}] {name} başlatılıyor...")

            full_path = self.project_root / script_path
            if not full_path.exists():
                print(f"❌ Dosya bulunamadı: {full_path}")
                return False

            process = subprocess.Popen(
                [self.python_path, str(full_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )

            self.processes[name] = process
            print(f"✅ {name} başlatıldı (PID: {process.pid})")

            # Sürecin başlatılmasını bekle
            time.sleep(wait_time)

            # Sürecin çalışıp çalışmadığını kontrol et
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                print(f"❌ {name} beklenmedik şekilde kapandı!")
                print(f"STDOUT: {stdout}")
                print(f"STDERR: {stderr}")
                return False

            return True

        except Exception as e:
            print(f"❌ {name} başlatılırken hata: {e}")
            return False

    def monitor_processes(self):
        """Süreçlerin durumunu izle"""
        while True:
            try:
                time.sleep(5)  # 5 saniyede bir kontrol

                dead_processes = []
                for name, process in self.processes.items():
                    if process.poll() is not None:
                        dead_processes.append(name)

                if dead_processes:
                    print(f"⚠️ Ölen süreçler tespit edildi: {', '.join(dead_processes)}")
                    for name in dead_processes:
                        process = self.processes[name]
                        stdout, stderr = process.communicate()
                        print(f"💀 {name} çıktısı:")
                        print(f"STDOUT: {stdout}")
                        print(f"STDERR: {stderr}")
                        del self.processes[name]

                    print("🔄 Sistem yeniden başlatılıyor...")
                    self.shutdown_all()
                    time.sleep(2)
                    self.start_all()

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"⚠️ İzleme sırasında hata: {e}")

    def shutdown_all(self):
        """Tüm süreçleri güvenli şekilde sonlandır"""
        print("\n🛑 Sistem kapatılıyor...")

        for name, process in self.processes.items():
            try:
                if process.poll() is None:  # Süreç hala çalışıyor
                    print(f"⏹️ {name} kapatılıyor...")

                    if platform.system() == "Windows":
                        process.terminate()
                    else:
                        process.send_signal(signal.SIGTERM)

                    # 5 saniye bekle, hala çalışıyorsa zorla kapat
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        print(f"🔨 {name} zorla kapatılıyor...")
                        process.kill()
                        process.wait()

                    print(f"✅ {name} kapatıldı")
            except Exception as e:
                print(f"❌ {name} kapatılırken hata: {e}")

        self.processes.clear()
        print("🎯 Tüm süreçler başarıyla kapatıldı")

    def start_all(self):
        """Tüm sistem bileşenlerini başlat"""
        print("🚀 Kandilli Deprem Dashboard Sistemi başlatılıyor...\n")

        # Ön kontroller
        if not self.check_dependencies():
            return False

        if not self.check_kafka_connection():
            return False

        # 1. Kandilli Producer (Veri kaynağı)
        if not self.start_process("Kandilli Producer", "producer/kandilli_producer.py", 3):
            return False

        # 2. Spark Streaming (Veri işleme - opsiyonel)
        print("⚠️ Spark Streaming başlatılıyor (bu biraz zaman alabilir)...")
        if not self.start_process("Spark Streaming", "consumer/spark_streaming.py", 15):
            print("⚠️ Spark başlatılamadı, ancak sistem çalışmaya devam edebilir")

        # 3. Flask Web Dashboard
        if not self.start_process("Flask Dashboard", "app/app.py", 3):
            return False

        print("\n" + "=" * 60)
        print("🎉 SİSTEM BAŞARIYLA BAŞLATILDI!")
        print("=" * 60)
        print("📊 Dashboard: http://localhost:5000")
        print("📈 API Stats: http://localhost:5000/api/stats")
        print("📋 Son Depremler: http://localhost:5000/api/recent/50")
        print("\n💡 Çıkmak için Ctrl+C tuşlayın")
        print("=" * 60 + "\n")

        return True

    def show_status(self):
        """Çalışan süreçlerin durumunu göster"""
        print("\n📊 SİSTEM DURUM RAPORU")
        print("-" * 40)

        if not self.processes:
            print("❌ Çalışan süreç yok")
            return

        for name, process in self.processes.items():
            status = "🟢 ÇALIŞIYOR" if process.poll() is None else "🔴 DURDURULDU"
            try:
                cpu_percent = psutil.Process(process.pid).cpu_percent()
                memory_mb = psutil.Process(process.pid).memory_info().rss / 1024 / 1024
                print(
                    f"{name:20} | {status} | PID: {process.pid:6} | CPU: {cpu_percent:5.1f}% | RAM: {memory_mb:6.1f}MB")
            except:
                print(f"{name:20} | {status} | PID: {process.pid:6}")

        print("-" * 40 + "\n")

    def run(self):
        """Ana çalışma döngüsü"""
        try:
            if not self.start_all():
                print("❌ Sistem başlatılamadı!")
                return

            # Periyodik durum raporu
            last_status_time = time.time()

            while True:
                time.sleep(1)

                # Her 30 saniyede durum raporu göster
                if time.time() - last_status_time > 30:
                    self.show_status()
                    last_status_time = time.time()

        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown_all()


def main():
    """Ana fonksiyon"""
    print("🌍 Kandilli Deprem Dashboard - Sistem Orchestrator")
    print("=" * 50)

    orchestrator = KandilliOrchestrator()

    try:
        orchestrator.run()
    except Exception as e:
        print(f"💥 Beklenmedik hata: {e}")
        orchestrator.shutdown_all()


if __name__ == "__main__":
    main()