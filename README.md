## Setup para análise de dados ##

Configuração de exemplo para uso das ferramentas:
- Apache Spark
- Apache NiFi
- Kafka
- Jupyter Notebook
- PostgreSQL

### Definir .env dos caminhos dos arquivos ###

```
SCRIPTS_PATH=/path_to_project/scripts
NIFI_DATA_PATH=/path_to_project/data/nifi
JUPYTER_DATA_PATH=/path_to_project/data/jupyter
POSTGRES_DATA_PATH=/path_to_project/data/postgres
```

No linux carregar o .env 
```
source .env
```

Na raiz do projeto rodar o docker-compose

```
docker-compose up -d
```

Visualizar cada container:
```
docker logs -f container
```

Finalizar os containers
```
docker-compose down
```
