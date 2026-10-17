import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

url = os.getenv("DATABASE_URL")
engine = create_engine(url, pool_pre_ping=True)

try:
    with engine.connect() as conn:
        print("Connected successfully!")
        print("Database:", conn.execute(
            text("SELECT current_database()")
        ).scalar())
except Exception as e:
    print("Connection failed:", e)
finally:
    engine.dispose()