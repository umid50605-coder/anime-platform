from getpass import getpass

from sqlalchemy import URL, create_engine, text

password = getpass("MySQL parolini kiriting: ")

url = URL.create(
    drivername="mysql+pymysql",
    username="anime_app",
    password=password,
    host="127.0.0.1",
    port=3306,
    database="anime_metadata",
)

engine = create_engine(url)

try:
    with engine.begin() as connection:

        # INSERT
        result = connection.execute(
            text("""
                INSERT INTO connection_test (massage)
                VALUES (:massage)
            """),
            {"massage": "Python orqali INSERT ishladi"},
        )

        row_id = result.lastrowid
        print("INSERT:", row_id)

        # SELECT
        row = connection.execute(
            text("""
                SELECT id, massage
                FROM connection_test
                WHERE id = :id
            """),
            {"id": row_id},
        ).mappings().one()

        print("SELECT:", dict(row))

        # UPDATE
        connection.execute(
            text("""
                UPDATE connection_test
                SET massage = :massage
                WHERE id = :id
            """),
            {
                "massage": "Python orqali UPDATE ishladi",
                "id": row_id,
            },
        )

        print("UPDATE: muvaffaqiyatli")

        # DELETE
        connection.execute(
            text("""
                DELETE FROM connection_test
                WHERE id = :id
            """),
            {"id": row_id},
        )

        print("DELETE: muvaffaqiyatli")

    print("\nBarcha CRUD amallari bajarildi.")

except Exception as error:
    print("XATOLIK:", type(error).__name__, error)

finally:
    engine.dispose()
