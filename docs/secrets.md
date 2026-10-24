# Local Secret Provisioning

This repository never stores credential values. The following instructions create local files or references only.

## Pi on Windows: file-backed credential

### Target path

```text
%USERPROFILE%\.pi\agent\.secrets\litellm-api-key
```

### Create the directory and file

Run PowerShell interactively. The command prompts securely and does not place the value in command history:

```powershell
$secretDir = Join-Path $env:USERPROFILE ".pi\agent\.secrets"
$secretPath = Join-Path $secretDir "litellm-api-key"
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null
$secure = Read-Host "LiteLLM API key" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    [IO.File]::WriteAllText($secretPath, $plain, [Text.UTF8Encoding]::new($false))
}
finally {
    if ($plain) { $plain = $null }
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}
```

### Restrict the ACL

```powershell
$acl = New-Object System.Security.AccessControl.FileSecurity
$acl.SetAccessRuleProtection($true, $false)
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    $user,
    "FullControl",
    "Allow"
)
$acl.AddAccessRule($rule)
Set-Acl -LiteralPath $secretPath -AclObject $acl
```

Do not print the file, hash it into reports, or pass it through commands that capture stdout.

Copy the tracked helper script to:

```text
%USERPROFILE%\.pi\agent\scripts\read-litellm-api-key.ps1
```

The Pi template resolves the credential with:

```text
!powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$USERPROFILE/.pi/agent/scripts/read-litellm-api-key.ps1"
```

Pi executes this through Git Bash on Windows, so `$USERPROFILE` is intentional in the outer command.

## Pi on Linux/macOS

The shared POSIX reader at `clients/pi/scripts/read-litellm-api-key.sh` is suitable for Linux and macOS. Install it locally under `~/.pi/agent/scripts/` and reference it from the local `models.json` using Pi's `!command` resolver:

```json
"apiKey": "!sh \"$HOME/.pi/agent/scripts/read-litellm-api-key.sh\""
```

Provision the secret without putting it in shell history or command arguments. The directory and file are user-only (`700` and `600`):

```bash
install -d -m 700 "$HOME/.pi/agent/.secrets"
umask 077
read -r -s LITELLM_KEY
printf '%s' "$LITELLM_KEY" > "$HOME/.pi/agent/.secrets/litellm-api-key"
unset LITELLM_KEY
chmod 600 "$HOME/.pi/agent/.secrets/litellm-api-key"
```

The reader writes only the file contents to stdout for Pi; missing and empty files exit nonzero and report a non-secret error to stderr. Do not run it manually in logs or diagnostics that capture stdout. Keep the script and secret local to the Pi user configuration; update only local `models.json`, and do not commit user-specific paths or credentials.

### Validation evidence

`tests/test_pi_secret_reader.py` uses a synthetic `HOME` and temporary files only. GitHub Actions run `40060512462` passed the full validation jobs on hosted `ubuntu-latest` (Linux) and `macos-latest` (macOS), including the synthetic reader fixtures and OS-specific suite checks. This validates the shared POSIX script and fixtures on those hosted runner OSes; it does not establish owner-managed host configuration, eeepc/Linux host validation, or equivalence beyond the shared script contract. No real credential file or secret-reader stdout is used for tests.

## OpenCode

The template contains:

```text
{env:LITELLM_EDGE_API_KEY}
```

Supply the variable through a local secret manager or launcher. Recommended approaches include:

- password-manager CLI injection;
- an OS credential-store wrapper;
- a local launcher script outside Git;
- a private environment file read by the launcher, with user-only permissions.

Do not persist the value in the tracked template. Avoid user-level registry/environment persistence when a file-backed or secret-manager workflow is available.

## Validation

Credential existence:

```powershell
pi auth check --provider litellm-edge
```

This confirms credential resolution, not upstream acceptance. Follow it with one minimal representative completion.
