/**
 * ────────────────────────────────────────────────────────────────────────
 * SCRIPT PARA GOOGLE APPS SCRIPT
 * ────────────────────────────────────────────────────────────────────────
 * Copie e cole este código no https://script.google.com/
 * 
 * Como usar:
 * 1. Cole este código no editor do Google Apps Script.
 * 2. Preencha o `GITHUB_TOKEN` com o seu token do GitHub (Personal Access Token).
 * 3. Execute a função `configurarInstaladorDiario` UMA ÚNICA VEZ clicando em "Executar".
 *    (Ele pedirá permissões do Google, basta aceitar).
 * 4. Pronto! O Google vai agendar automaticamente as postagens todos os dias nos horários de pico.
 */

var GITHUB_TOKEN = 'SEU_TOKEN_DO_GITHUB_AQUI'; 
var REPO_OWNER   = 'robsonvit';
var REPO_NAME    = 'canal-cortes';
var WORKFLOW_ID  = 'main.yml';
var BRANCH       = 'master';

/**
 * Função principal que aciona o GitHub Actions
 */
function acionarRoboDeCortes() {
  var url = 'https://api.github.com/repos/' + REPO_OWNER + '/' + REPO_NAME + '/actions/workflows/' + WORKFLOW_ID + '/dispatches';
  
  var payload = {
    "ref": BRANCH
  };
  
  var options = {
    "method": "post",
    "headers": {
      "Authorization": "Bearer " + GITHUB_TOKEN,
      "Accept": "application/vnd.github.v3+json"
    },
    "contentType": "application/json",
    "payload": JSON.stringify(payload),
    "muteHttpExceptions": true
  };
  
  try {
    var response = UrlFetchApp.fetch(url, options);
    var code = response.getResponseCode();
    if (code === 204) {
      Logger.log("✅ Pipeline acionado com sucesso no GitHub!");
    } else {
      Logger.log("❌ Erro ao acionar o pipeline. Código: " + code + " | Resposta: " + response.getContentText());
    }
  } catch (e) {
    Logger.log("⚠️ Falha crítica ao conectar com o GitHub: " + e.toString());
  }
}

/**
 * RODE ESTA FUNÇÃO UMA ÚNICA VEZ PARA INSTALAR O SISTEMA
 * Ela cria os 3 acionadores diários (Manhã, Tarde e Noite).
 * O Google executará os gatilhos dentro de uma janela de 1 hora a partir do horário definido.
 */
function configurarInstaladorDiario() {
  // 1. Limpa qualquer gatilho anterior para evitar duplicatas
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    ScriptApp.deleteTrigger(triggers[i]);
  }
  
  // 2. Cria o gatilho da Manhã (entre 11h e 12h)
  ScriptApp.newTrigger("acionarRoboDeCortes")
           .timeBased()
           .everyDays(1)
           .inTimezone("America/Sao_Paulo")
           .atHour(11)
           .create();
           
  // 3. Cria o gatilho da Tarde (entre 17h e 18h)
  ScriptApp.newTrigger("acionarRoboDeCortes")
           .timeBased()
           .everyDays(1)
           .inTimezone("America/Sao_Paulo")
           .atHour(17)
           .create();
           
  // 4. Cria o gatilho da Noite (entre 20h e 21h)
  ScriptApp.newTrigger("acionarRoboDeCortes")
           .timeBased()
           .everyDays(1)
           .inTimezone("America/Sao_Paulo")
           .atHour(20)
           .create();
           
  Logger.log("✅ SISTEMA INSTALADO COM SUCESSO!");
  Logger.log("O robô de cortes postará automaticamente 3x por dia todos os dias (Manhã, Tarde e Noite).");
  Logger.log("Você não precisa mais clicar em Executar!");
}
