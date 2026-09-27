import os
import urllib.request
import zipfile

url = "https://myshell-public-repo-host.s3.amazonaws.com/openvoice/checkpoints_v2_0417.zip"
file_name = "checkpoints_v2_0417.zip"
target_dir = "OpenVoice/checkpoints_v2"

if not os.path.exists(target_dir):
    os.makedirs(target_dir)

if not os.path.exists(file_name):
    print(f"Baixando checkpoints pesados de {url} (isso pode demorar muito)...")
    urllib.request.urlretrieve(url, file_name)
    print("Download concluído!")
else:
    print(f"O arquivo {file_name} já existe. Pulando o download.")

print("Extraindo os arquivos...")
with zipfile.ZipFile(file_name, 'r') as zip_ref:
    zip_ref.extractall("OpenVoice")
    # O arquivo zip contém uma pasta checkpoints_v2, então extraímos na raiz do OpenVoice
    
print("Checkpoints configurados com sucesso!")
