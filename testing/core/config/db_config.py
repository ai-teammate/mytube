"""Database configuration loaded from environment variables."""
import os


class DBConfig:
    host: str
    port: int
    user: str
    password: str
    dbname: str
    sslmode: str

    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = int(os.getenv("DB_PORT", "5432"))
        self.user = os.getenv("DB_USER", "testuser")
        self.password = os.getenv("DB_PASSWORD", "testpass")
        self.dbname = os.getenv("DB_NAME", "mytube_test")
        self.sslmode = os.getenv("SSL_MODE", "disable")

    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} "
            f"user={self.user} password={self.password} "
            f"dbname={self.dbname} sslmode={self.sslmode}"
        )
