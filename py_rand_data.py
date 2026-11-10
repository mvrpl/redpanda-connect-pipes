from faker import Faker
from faker.providers import internet

import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

fake = Faker('pt_BR')
fake.add_provider(internet)

items = []

for _ in range(10):
    items.append({
        "nome": fake.unique.first_name(),
        "estado": fake.estado_nome(),
        "celular": fake.cellphone_number(),
        "ip": fake.ipv4_private(),
        "id": fake.iana_id()
    })

print(json.dumps(items))