import os
from datetime import datetime

MODULE_PATH = "modules/generated_backend_demo.py"

code = f""""""
Automatisch generiertes Backend-Modul
Erstellt am {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

def hello():
    return "Hello from the PEAR Backend-Agent!"

if __name__ == "__main__":
    print(hello())
"""

os.makedirs(os.path.dirname(MODULE_PATH), exist_ok=True)
with open(MODULE_PATH, "w", encoding="utf-8") as f:
    f.write(code)
print(f"Backend-Modul generiert: {MODULE_PATH}")
