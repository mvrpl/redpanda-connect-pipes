# Redpanda Connect: Estudos

Pipelines de exemplo feitos para estudar o [Redpanda Connect](https://docs.redpanda.com/redpanda-connect/), com variáveis de ambiente gerenciadas pelo [dotenvx](https://dotenvx.com/).

## Pré-requisitos

[Windows Apps](https://github.com/mvrpl/windows-apps) | [Mac/Linux Apps](https://github.com/mvrpl/unix-apps)

- Redpanda Connect
- Dotenvx
- Python 3 (usado pelo exemplo `py_rand_data`)

## Exemplos

| Pipeline | Arquivo | O que faz |
| --- | --- | --- |
| Dados aleatórios | `py_rand_data.yaml` | A cada 10 s executa um script Python que gera um registro aleatório |
| Tags do Spark → Kafka | `github_tags_spark.yaml` | Lê as tags do `apache/spark` na API do GitHub e envia ao Kafka |
| Reviews da Steam → Kafka | `steam_reviews.yaml` | Lê reviews da Steam e gera um evento Kafka por review |

### py_rand_data

O input `generate` dispara a cada 10 segundos e o processor `command` executa o `py_rand_data.py`. O script imprime um objeto JSON por execução, com os campos `celular`, `estado`, `id`, `ip` e `nome`.

**Execução**

```powershell
dotenvx run -- redpanda-connect -c .\py_rand_data.yaml
```

No Linux ou macOS, troque o caminho por `./py_rand_data.yaml`.

**Exemplo de formato do registro**

```json
{
  "celular": "(21) 99999-0000",
  "estado": "RJ",
  "id": 1,
  "ip": "192.168.0.10",
  "nome": "Fulano de Tal"
}
```

### github_tags

Consulta `https://api.github.com/repos/apache/spark/tags` a cada 1 minuto, separa o array em um evento por tag e envia ao Kafka com `kafka_franz`, usando o nome da tag como key.

```powershell
dotenvx run -- redpanda-connect -c .\github_tags.yaml
```

### steam_reviews

Lê `https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1?appId=227300`, pega todos os itens de `response.reviews` e gera um evento Kafka para cada um.

```powershell
dotenvx run -- redpanda-connect -c .\steam_reviews.yaml
```

## Variáveis de ambiente

O `dotenvx run --` carrega o `.env` e injeta as variáveis no processo. No YAML, elas são lidas com `${VAR}`:

```yaml
sasl:
  - mechanism: SCRAM-SHA-256
    username: ${KAFKA_USER}
    password: ${KAFKA_PASSWORD}
```

Exemplo de `.env` (ajuste os nomes para a sua config):

```dotenv
KAFKA_BROKER=meu-broker:12345
KAFKA_USER=usuario
KAFKA_PASSWORD=segredo
```

Para criptografar os valores antes de versionar:

```bash
dotenvx encrypt
```

Isso criptografa o `.env` (que pode ir para o Git) e cria o `.env.keys` com a chave privada. **Nunca commite o `.env.keys`**: adicione-o ao `.gitignore`.

```gitignore
.env.keys
```