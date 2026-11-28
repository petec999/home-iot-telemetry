#!/usr/bin/env python3
"""Replace only the Xiaomi cloud utility module with its public ARC4 API version.
No global packages or HA entries are changed.
"""
import ast
from pathlib import Path
import shutil
import time
import os

SOURCE = "import base64\nimport hashlib\nimport hmac\nimport json\nimport os\nimport random\nfrom typing import Any\n\nfrom Crypto.Cipher import ARC4\n\n\ndef generate_nonce(millis: int):\n    nonce_bytes = os.urandom(8) + (int(millis / 60000)).to_bytes(4, byteorder=\"big\")\n    return base64.b64encode(nonce_bytes).decode()\n\n\ndef generate_agent() -> str:\n    agent_id = random_text(65, 69, 13)\n    prefix = random_text(97, 122, 18)\n    return f\"{prefix}-{agent_id} APP/com.xiaomi.mihome APPV/10.5.201\"\n\n\ndef generate_device_id() -> str:\n    return random_text(97, 122, 6)\n\n\ndef generate_signature(\n    url, signed_nonce: str, nonce: str, params: dict[str, str]\n) -> str:\n    signature_params = [url.split(\"com\")[1], signed_nonce, nonce]\n    for k, v in params.items():\n        signature_params.append(f\"{k}={v}\")\n    signature_string = \"&\".join(signature_params)\n    signature = hmac.new(\n        base64.b64decode(signed_nonce),\n        msg=signature_string.encode(),\n        digestmod=hashlib.sha256,\n    )\n    return base64.b64encode(signature.digest()).decode()\n\n\ndef generate_enc_signature(\n    url, method: str, signed_nonce: str, params: dict[str, str]\n) -> str:\n    signature_params = [str(method).upper(), url.split(\"com\")[1].replace(\"/app/\", \"/\")]\n    for k, v in params.items():\n        signature_params.append(f\"{k}={v}\")\n    signature_params.append(signed_nonce)\n    signature_string = \"&\".join(signature_params)\n    return base64.b64encode(\n        hashlib.sha1(signature_string.encode(\"utf-8\")).digest()\n    ).decode()\n\n\ndef generate_enc_params(\n    url: str,\n    method: str,\n    signed_nonce: str,\n    nonce: str,\n    params: dict[str, str],\n    ssecurity: str,\n) -> dict[str, str]:\n    params[\"rc4_hash__\"] = generate_enc_signature(url, method, signed_nonce, params)\n    for k, v in params.items():\n        params[k] = encrypt_rc4(signed_nonce, v)\n    params.update(\n        {\n            \"signature\": generate_enc_signature(url, method, signed_nonce, params),\n            \"ssecurity\": ssecurity,\n            \"_nonce\": nonce,\n        }\n    )\n    return params\n\n\ndef to_json(response_text: str) -> any:\n    return json.loads(response_text.replace(\"&&&START&&&\", \"\"))\n\n\n# The keys whose values in Xiaomi's login requests and responses give the\n# session away: its secrets, the signatures a login is built on, and the URLs\n# that carry either in their query.\n_SECRET_KEYS = frozenset(\n    {\n        \"_sign\",\n        \"clientSign\",\n        \"context\",\n        \"ick\",\n        \"location\",\n        \"loginUrl\",\n        \"lp\",\n        \"nonce\",\n        \"notificationUrl\",\n        \"passToken\",\n        \"psecurity\",\n        \"qr\",\n        \"serviceToken\",\n        \"ssecurity\",\n        \"ticket\",\n    }\n)\nREDACTED = \"**REDACTED**\"\n\n\ndef redacted(value: Any) -> Any:\n    \"\"\"A login request or response, as it may be logged.\n\n    JSON text and dictionaries keep their shape, with the secret values\n    masked. Any other text is logged only by its length, since a page can\n    carry the same secrets.\n    \"\"\"\n    if isinstance(value, str):\n        try:\n            value = to_json(value)\n        except ValueError:\n            return f\"<{len(value)} characters>\"\n    return _masked(value)\n\n\ndef _masked(value: Any) -> Any:\n    if isinstance(value, dict):\n        return {\n            key: REDACTED if key in _SECRET_KEYS else _masked(item)\n            for key, item in value.items()\n        }\n    if isinstance(value, list):\n        return [_masked(item) for item in value]\n    return value\n\n\ndef without_query(url: Any) -> Any:\n    \"\"\"A URL as it may be logged: its query carries signatures and tokens.\"\"\"\n    return str(url).split(\"?\", 1)[0] if url else url\n\n\ndef encrypt_rc4(password: str, payload: str) -> str:\n    r = ARC4.new(base64.b64decode(password))\n    r.encrypt(bytes(1024))\n    return base64.b64encode(r.encrypt(payload.encode())).decode()\n\n\ndef decrypt_rc4(password: str, payload: str) -> bytes:\n    r = ARC4.new(base64.b64decode(password))\n    r.encrypt(bytes(1024))\n    return r.encrypt(base64.b64decode(payload))\n\n\ndef random_text(chr_from: int, chr_to: int, length: int) -> str:\n    return \"\".join([chr(random.randint(chr_from, chr_to)) for _ in range(length)])\n"
root=Path("/config/custom_components/robot_vacuum_map")
p=root/"connector/xiaomi_cloud/utils.py"
connector=p.with_name("connector.py")
old=p.read_text()
new=SOURCE
if "Crypto.Util._raw_api" not in old:
    if old==new:
        print("Already patched")
        raise SystemExit(0)
    raise SystemExit("Unexpected source: no private Crypto import; no changes")
tree=ast.parse(new)
defined={n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
defined.update(t.id for n in tree.body if isinstance(n,ast.Assign) for t in n.targets if isinstance(t,ast.Name))
for node in ast.walk(ast.parse(connector.read_text())):
    if isinstance(node,ast.ImportFrom) and node.level==1 and node.module=="utils":
        missing={a.name for a in node.names}-defined
        if missing:
            raise SystemExit("Incompatible connector imports: "+str(missing))
compile(new,str(p),"exec")
backup=Path("/config")/("robot-vacuum-map-utils-backup-"+str(time.time_ns())+".py")
shutil.copy2(p,backup)
tmp=p.with_suffix(".py.tmp")
tmp.write_text(new)
os.replace(tmp,p)
shutil.rmtree(p.parent/"__pycache__",ignore_errors=True)
print("PATCH OK; backup:",backup)
print("Restart HA Core before retrying configuration.")
