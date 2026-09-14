param([string]$RepoName = 'twins-growth-web')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
function CheckExit([string]$Step) { if ($LASTEXITCODE -ne 0) { throw "$Step failed; stopped without continuing." } }
if ($RepoName -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]*$') { throw 'Invalid repository name.' }
if (!(Get-Command gh -ErrorAction SilentlyContinue)) { throw 'GitHub CLI not installed. Let Codex install gh, then authenticate locally with gh auth login. Do not paste tokens into chat.' }
gh auth status; CheckExit 'GitHub authentication'
python tools/check_public.py; CheckExit 'Privacy guard'
# Create-only: never repoint, overwrite, force-push, or use an existing repository.
if (Test-Path .git) { throw 'This directory is already a git repository. Inspect it manually; this first-deploy script will not overwrite it.' }
$owner = (gh api user --jq .login).Trim(); CheckExit 'Read current GitHub user'
$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
gh repo view "$owner/$RepoName" 2>$null
$repoViewExit = $LASTEXITCODE
$ErrorActionPreference = $previousErrorAction
if ($repoViewExit -eq 0) { throw 'Repository already exists. Choose a new name; no existing project will be modified.' }
git init -b main; CheckExit 'git init'
git add web tools docs tests .github .gitignore README.md start_local.bat start_sync.bat configure_sync.bat one_click_sync.bat configure_github_backup.bat deploy_github.ps1; CheckExit 'git add explicit allowlist'
python tools/check_public.py; CheckExit 'Staged privacy guard'
git commit -m 'Add privacy-separated twins growth web app'; CheckExit 'git commit'
gh repo create "$owner/$RepoName" --public --source . --remote origin --push; CheckExit 'Create and push template repository'
gh api --method POST "repos/$owner/$RepoName/pages" -f build_type=workflow; CheckExit 'Enable Pages'
gh workflow run pages.yml; CheckExit 'Start Pages deployment'
Write-Host "Source repository created. Confirm Pages deployment outcome in GitHub Actions before sharing a website URL."
Write-Host "Only template code is public. private/ was NOT uploaded. Cloud family data needs separate setup."
