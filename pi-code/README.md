# Medicijnkluis

Dit is de software die op de fysieke medicijnkluis draait.

## installatie

```bash
# maak een virtuele pythonomgeving aan
python -m venv .venv

# activeer het
.venv\scripts\activate

# installeer dependencies
pip install -r requirements.txt
```

## configuratie

maak een `.env` bestand in de hoofdmap van het project en vul daar de juiste gegevens in, bijvoorbeeld:

```env
secretkey=geheime-sleutel
db_host=localhost
db_user=root
db_password=wachtwoord
db_name=database-naam
db_port=3306
admin_username=admin
admin_password=admin-wachtwoord
```

## voorwaarde

je hebt een draaiende mysql-server nodig met een database.

## starten

```bash
python app.py
```

de applicatie draait op [http://localhost:5000](http://localhost:5000).