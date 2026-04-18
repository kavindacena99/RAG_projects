try:
    import pymysql
except ImportError as exc:
    raise ImportError(
        "PyMySQL is required because this backend is configured for MySQL only. "
        "Install backend dependencies from requirements.txt before starting Django."
    ) from exc

# Django's MySQL backend checks the MySQLdb driver version. PyMySQL exposes
# a legacy compatibility version tuple, so we align it with Django's minimum.
pymysql.version_info = (2, 2, 1, "final", 0)
pymysql.__version__ = "2.2.1"
pymysql.install_as_MySQLdb()
