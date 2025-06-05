import json
import os

print("=== ТЕСТ ЗАПИСИ JSON ===")
print(f"Рабочая директория: {os.getcwd()}")

# Тест 1: Простая запись
data = {"test": "успех", "число": 123}
with open("test.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print("✅ Файл test.json создан")

# Тест 2: Чтение
with open("test.json", "r", encoding="utf-8") as f:
    loaded = json.load(f)
    print(f"✅ Прочитано: {loaded}")

# Тест 3: Проверка пути
print(f"✅ Абсолютный путь: {os.path.abspath('test.json')}")

# Тест 4: Список файлов
print("📁 Файлы в директории:")
for f in os.listdir('.'):
    if f.endswith('.json'):
        print(f"  {f} - размер: {os.path.getsize(f)} байт")
