import json
import os
import sys
from pathlib import Path
from urllib import error, request

from ssl_utils import create_ssl_context, get_ca_bundle_path


def load_env_file(env_path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    project_root = Path(__file__).resolve().parent
    load_env_file(project_root / ".env")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY is missing. Add it to .env first.")
        return 1

    req = request.Request(
        url="https://api.openai.com/v1/models",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="GET",
    )

    ssl_context = create_ssl_context()

    def fetch() -> tuple[list, int]:
        with request.urlopen(req, timeout=30, context=ssl_context) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return payload.get("data", []), resp.status

    try:
        models, _ = fetch()
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP ERROR {exc.code}: {exc.reason}")
        print(body[:600])
        return 2
    except error.URLError as exc:
        print(f"REQUEST FAILED: {exc}")
        if get_ca_bundle_path() is None:
            print("Tip: install certifi to improve certificate compatibility: pip install certifi")
        return 3
    except Exception as exc:
        print(f"REQUEST FAILED: {exc}")
        return 3

    print("API key is valid.")
    print(f"Accessible models: {len(models)}")
    for model in models[:10]:
        model_id = model.get("id", "<unknown>")
        print(f"- {model_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
