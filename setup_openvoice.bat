@echo off
call "%USERPROFILE%\Miniconda3\Scripts\activate.bat" openvoice
cd OpenVoice
echo Instalando dependencias do OpenVoice...
pip install -e .
echo Instalando MeloTTS...
pip install git+https://github.com/myshell-ai/MeloTTS.git
python -m unidic download
echo Instalacao concluida.
