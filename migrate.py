import os
import re

files = [
    'scripts/ajustar_corte_semantico.py',
    'scripts/baixar_musica.py',
    'scripts/inserir_contexto.py',
    'scripts/upload_youtube.py',
    'scripts/transcrever.py'
]

for f in files:
    if not os.path.exists(f): continue
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # 1. Groq imports -> OpenAI
    content = content.replace('from groq import Groq', 'from openai import OpenAI')
    
    # 2. cliente = Groq(...) -> OpenAI(base_url, api_key)
    content = re.sub(
        r'cliente\s*=\s*Groq\(api_key=groq_key\)',
        'cliente = OpenAI(base_url=\"https://openrouter.ai/api/v1\", api_key=os.environ.get(\"OPENROUTER_API_KEY\"))',
        content
    )
    content = re.sub(
        r'cliente\s*=\s*Groq\(api_key=os\.environ\.get\([\'\"]GROQ_API_KEY[\'\"]\)\)',
        'cliente = OpenAI(base_url=\"https://openrouter.ai/api/v1\", api_key=os.environ.get(\"OPENROUTER_API_KEY\"))',
        content
    )
    
    # 3. Model replacements (llama-3.1-70b-versatile -> meta-llama/llama-3.3-70b-instruct:free)
    content = content.replace('llama-3.1-70b-versatile', 'meta-llama/llama-3.3-70b-instruct:free')
    
    # 4. ENV variable checks
    content = content.replace('GROQ_API_KEY', 'OPENROUTER_API_KEY')
    content = content.replace('groq_key', 'openrouter_key')
    
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)
    print(f'Migrated {f}')
