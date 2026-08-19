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

Prefer a user-only secret file or secret manager command. If using a file:

```bash
install -d -m 700 "$HOME/.pi/agent/.secrets"
umask 077
read -r -s LITELLM_KEY
printf '%s' "$LITELLM_KEY" > "$HOME/.pi/agent/.secrets/litellm-api-key"
unset LITELLM_KEY
chmod 600 "$HOME/.pi/agent/.secrets/litellm-api-key"
```

Create a local reader command suitable for the platform and update only the local `models.json`. Do not commit platform-specific secret paths containing usernames.

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
