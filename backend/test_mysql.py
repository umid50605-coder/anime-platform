from sqlalchemy import create_engine, text
from getpass import getpass

password = getpass("anime_app parolini kiriting: ")

DATABASE_URL = (
    f"mysql+pymysql://anime_app:{password}"
    "@127.0.0.1:3306/anime_metadata"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

try:
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT DATABASE(), USER(), VERSION()")
        )

        database, user, version = result.fetchone()

        print("\nMySQL connection successful!")
        print("Database:", database)
        print("User:", user)
        print("Version:", version)

except Exception as error:
    print("Connection failed:", type(error).__name__)
    print(error)

finally:
    engine.dispose()
