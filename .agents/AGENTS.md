# Regras do Workspace

<RULE[git_push_auth]>
Sempre que precisar executar operações que exijam autenticação no GitHub (como `git push` ou `git pull`) e você encontrar falhas de senha/token do tipo `Authentication failed` ou `Invalid username or token`, o ambiente possivelmente está com conflito de variáveis.

Para contornar o problema e forçar o uso da chave local pré-aprovada pelo usuário no GitHub CLI, execute o comando com a seguinte sequência obrigatória **dentro da mesma sessão PowerShell**:

```powershell
Remove-Item Env:\GITHUB_TOKEN -ErrorAction SilentlyContinue
gh auth switch -u robsonvit
gh auth setup-git
git push
```
Esta sequência desabilita tokens temporários inválidos do ambiente local e usa o `gh auth setup-git` para delegar a autenticação de forma silenciosa e bem-sucedida.
</RULE[git_push_auth]>
