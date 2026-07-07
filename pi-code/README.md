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
SECRET_KEY=geheime-sleutel
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=wachtwoord
DB_NAME=database-naam
DB_PORT=3306
ADMIN_PINCODE=123456
```

## voorwaarde

je hebt een draaiende mysql-server nodig met een database.

## starten

```bash
python app.py
```

de applicatie draait op [http://localhost:5000](http://localhost:5000).