import os

if os.getenv("MYSQL_DATABASE"):
    try:
        import pymysql

        pymysql.install_as_MySQLdb()
    except ImportError:
        pass
