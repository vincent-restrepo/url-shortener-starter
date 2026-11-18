import os

# La app exige estos secretos al importarse; en los tests usamos valores de mentira
os.environ.setdefault("DB_PASSWORD", "test")
os.environ.setdefault("SHARED_SECRET", "test-secret")
