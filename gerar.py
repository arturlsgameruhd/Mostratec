import os
from pathlib import Path

# Cria a pasta .streamlit caso ela não exista
os.makedirs(".streamlit", exist_ok=True)

# Cria o arquivo config.toml com o tema escuro
config_path = Path(".streamlit/config.toml")
config_content = '''[theme]
base = "dark"
primaryColor = "#6366f1"
backgroundColor = "#07080d"
secondaryBackgroundColor = "#0f1220"
textColor = "#e6e8ef"
'''
config_path.write_text(config_content, encoding="utf-8")

print("Sucesso! Pasta .streamlit e arquivo config.toml criados.")
