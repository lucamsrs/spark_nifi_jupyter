import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum as spark_sum
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType
import psycopg2

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurações
kafka_bootstrap_servers = "kafka:9092"
kafka_topic = "sales_topic"
postgres_host = "postgres"
postgres_db = "nifi_db"
postgres_user = "nifi_user"
postgres_password = "nifi_password"
postgres_table_analysis = "sales_analysis"

# Configurar sessão do Spark
spark = SparkSession.builder \
    .appName("KafkaSparkETL") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,org.apache.kafka:kafka-clients:3.5.1,org.postgresql:postgresql:42.2.19") \
    .config("spark.sql.streaming.forceDeleteTempCheckpointLocation", "true") \
    .getOrCreate()

logger.info("Spark session initialized.")

# Definir esquema do CSV
schema = StructType([
    StructField("IdPedido", StringType(), True),
    StructField("Data", StringType(), True),
    StructField("IdCliente", StringType(), True),
    StructField("NomeCliente", StringType(), True),
    StructField("SexoCliente", StringType(), True),
    StructField("IdadeCliente", IntegerType(), True),
    StructField("IdProduto", StringType(), True),
    StructField("Produto", StringType(), True),
    StructField("PrecoAtual", FloatType(), True),
    StructField("QuantidadeComprada", IntegerType(), True),
    StructField("PrecoPagoPorUnidade", FloatType(), True),
    StructField("TotalCompra", FloatType(), True),
    StructField("Status", StringType(), True)
])

# Ler dados do Kafka e tratar como CSV
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", kafka_bootstrap_servers) \
    .option("subscribe", kafka_topic) \
    .load()

logger.info("Kafka stream initialized.")

# Converter os dados CSV para colunas usando o esquema ajustado
sales_df = df.selectExpr("CAST(value AS STRING) as csv_string") \
    .selectExpr(f"from_csv(csv_string, '{schema.simpleString()}', map('sep', ',')) as data") \
    .select("data.*")

# Usar writeStream para mostrar os dados no console para depuração
console_query = sales_df.writeStream \
    .outputMode("append") \
    .format("console") \
    .option("truncate", "false") \
    .start()

# Função para inserir o sumário no PostgreSQL
def foreach_batch_function(batch_df, epoch_id):
    logger.info(f"Processing batch with epoch_id: {epoch_id}")

    # Cálculo do sumário
    summary_df = batch_df.groupBy("Produto").agg(
        spark_sum(col("QuantidadeComprada") * col("PrecoPagoPorUnidade")).alias("total_revenue")
    )

    # Logar o conteúdo de summary_df
    summary_df.show(truncate=False)
    logger.info("Summary data frame calculated.")

    # Conexão com o PostgreSQL
    try:
        conn = psycopg2.connect(
            host=postgres_host,
            database=postgres_db,
            user=postgres_user,
            password=postgres_password
        )
        cursor = conn.cursor()
        logger.info("Connected to PostgreSQL.")

        # Inserir sumário na tabela `sales_analysis`
        for row in summary_df.collect():
            logger.info(f"Inserting into sales_analysis - Product: {row['Produto']}, Total Revenue: {row['total_revenue']}")
            cursor.execute(
                f"""
                INSERT INTO {postgres_table_analysis} (product, total_revenue)
                VALUES (%s, %s)
                ON CONFLICT (product) DO UPDATE SET total_revenue = sales_analysis.total_revenue + EXCLUDED.total_revenue
                """,
                (row['Produto'], row['total_revenue'])
            )

        # Commit e fechamento da conexão
        conn.commit()
        logger.info("Data committed to PostgreSQL.")
    except Exception as e:
        logger.error("Error while inserting into PostgreSQL", exc_info=e)
    finally:
        cursor.close()
        conn.close()
        logger.info("PostgreSQL connection closed.")

# Gravar sumário no PostgreSQL
query = sales_df.writeStream \
    .foreachBatch(foreach_batch_function) \
    .outputMode("update") \
    .start()

logger.info("Streaming query started.")
query.awaitTermination()
console_query.awaitTermination()
