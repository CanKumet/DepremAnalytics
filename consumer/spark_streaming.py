from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, avg, to_date
from pyspark.sql.types import StructType, StringType, DoubleType

# Kafka’dan gelen JSON yapısına uygun şema
schema = StructType() \
    .add("tarih", StringType()) \
    .add("saat", StringType()) \
    .add("enlem", DoubleType()) \
    .add("boylam", DoubleType()) \
    .add("derinlik_km", DoubleType()) \
    .add("buyukluk", DoubleType()) \
    .add("yer", StringType())

# Spark Session
spark = SparkSession.builder \
    .appName("KandilliDepremAnalizi") \
    .config("spark.sql.streaming.schemaInference", "true") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.0") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# Kafka’dan veriyi oku
df_kafka = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9192") \
    .option("subscribe", "deprem-verisi") \
    .load()

# JSON parse
df_json = df_kafka.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), schema).alias("data")) \
    .select("data.*")

# 🔹 Ortalama büyüklük
ortalama_b = df_json.select(avg("buyukluk").alias("ortalama_boyut"))

# 🔹 En yoğun bölge (lokasyon bazlı sayım)
en_yogun_yer = df_json.groupBy("yer").count().orderBy(col("count").desc())

# 🔹 Tarih bazlı büyüklük ortalaması
zaman_bazli = df_json \
    .withColumn("gun", to_date(col("tarih"), "yyyy.MM.dd")) \
    .groupBy("gun").avg("buyukluk") \
    .orderBy("gun")

# 🔔 Canlı uyarı sistemi – M >= 4.0
alert_stream = df_json.filter(col("buyukluk") >= 4.0)

# 🔎 DEBUG: df_json çıktısını terminale yaz
debug_query = df_json.writeStream \
    .format("console") \
    .outputMode("append") \
    .option("truncate", False) \
    .start()

# ✅ En yoğun bölgeler terminale
query_yogun = en_yogun_yer.writeStream \
    .outputMode("complete") \
    .format("console") \
    .option("truncate", False) \
    .start()

# ✅ Canlı alert terminale
alert_query = alert_stream.writeStream \
    .outputMode("append") \
    .format("console") \
    .option("truncate", False) \
    .start()

# ✅ Ortalama büyüklük terminale
ortalama_query = ortalama_b.writeStream \
    .outputMode("complete") \
    .format("console") \
    .option("truncate", False) \
    .start()

# ✅ Zaman bazlı ortalama terminale
zaman_query = zaman_bazli.writeStream \
    .outputMode("complete") \
    .format("console") \
    .option("truncate", False) \
    .start()

# Stream’lerin sürekli çalışmasını sağla
debug_query.awaitTermination()
query_yogun.awaitTermination()
alert_query.awaitTermination()
ortalama_query.awaitTermination()
zaman_query.awaitTermination()
