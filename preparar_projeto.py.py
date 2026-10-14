import os
from pathlib import Path

def executar_automacao():
    print("Iniciando a preparação automática do projeto...")
    base_dir = Path(".")
    
    # 1. Criar requirements.txt
    req_path = base_dir / "requirements.txt"
    req_content = (
        "streamlit>=1.37.0\n"
        "plotly>=5.0.0\n"
        "numpy>=1.20.0\n"
        "pandas>=1.3.0\n"
        "google-genai>=0.1.0\n"
    )
    req_path.write_text(req_content, encoding="utf-8")
    print("[OK] Arquivo requirements.txt criado com sucesso.")

    # 2. Criar .streamlit/config.toml
    streamlit_dir = base_dir / ".streamlit"
    streamlit_dir.mkdir(exist_ok=True)
    config_path = streamlit_dir / "config.toml"
    config_content = (
        "[theme]\n"
        "base = 'dark'\n"
        "primaryColor = '#6366f1'\n"
        "backgroundColor = '#07080d'\n"
        "secondaryBackgroundColor = '#0f1220'\n"
        "textColor = '#e6e8ef'\n"
    )
    config_path.write_text(config_content, encoding="utf-8")
    print("[OK] Pasta .streamlit e arquivo config.toml criados com sucesso.")

    # 3. Criar .gitignore
    gitignore_path = base_dir / ".gitignore"
    gitignore_content = (
        "astra_users.json\n"
        "__pycache__/\n"
        ".ipynb_checkpoints/\n"
        ".DS_Store\n"
    )
    gitignore_path.write_text(gitignore_content, encoding="utf-8")
    print("[OK] Arquivo .gitignore criado com sucesso.")

    print("\n----------------------------------------------------")
    print("TUDO PRONTO PELA PARTE DOS ARQUIVOS!")
    print("----------------------------------------------------")
    print("Para subir para o seu GitHub privado de forma rápida, abra o terminal na pasta e digite:")
    print("  1. git init")
    print("  2. git add .")
    print("  3. git commit -m 'Setup automatizado Mostratec'")
    print("  4. git branch -M main")
    print("  5. git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git")
    print("  6. git push -u origin main")

if __name__ == "__main__":
    executar_automacao()
