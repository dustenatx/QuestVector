# Vault format 1 fixtures

Synthetic vault files in format 1 (PBKDF2-HMAC-SHA256 at 390,000
iterations, no associated data), used to test that vaults written by
QuestVector 1.1.0 still open and are upgraded to format 2 on save
([ADR-0015](../../../docs/decisions/0015-pbkdf2-1m-iterations-vault-v2.md)).
They contain no real keys.

| File | Passphrase | Contents |
|---|---|---|
| `v1-vault.json` | `qv-fixture-v1-passphrase` | provider `anthropic`, key `QVFIXTURE-v1-not-a-real-key`, `session_cache {"a": 1}` |
| `v1-vault-empty-passphrase.json` | empty | provider `ollama`, model `llama3.1` |

Both were written on 28 Oct 2026 by `save_vault` from the released 1.1.0
code, not by a reimplementation:

```bash
git show v1.1.0:questvector/core/vault.py > /tmp/vault_v1_1_0.py
```

```python
import importlib.util, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("vault_v1_1_0", "/tmp/vault_v1_1_0.py")
old = importlib.util.module_from_spec(spec)
sys.modules["vault_v1_1_0"] = old
spec.loader.exec_module(old)

out = Path("tests/fixtures/vault")
old.save_vault(out / "v1-vault.json", "qv-fixture-v1-passphrase", old.VaultData(
    llm_provider="anthropic",
    llm_api_keys={"anthropic": "QVFIXTURE-v1-not-a-real-key"},
    session_cache={"a": 1},
))
old.save_vault(out / "v1-vault-empty-passphrase.json", "",
               old.VaultData(llm_provider="ollama", llm_model="llama3.1"))
```

Don't regenerate them with the current code: that writes format 2.
