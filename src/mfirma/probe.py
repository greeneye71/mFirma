from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def probe_module(module_path: Path) -> list[dict[str, Any]]:
    """Enumera dati pubblici senza login e senza richiedere un PIN."""
    import pkcs11
    from pkcs11 import Attribute, ObjectClass

    module = module_path.expanduser().resolve(strict=True)
    library = pkcs11.lib(str(module))
    result: list[dict[str, Any]] = []
    for slot in library.get_slots(token_present=True):
        token = slot.get_token()
        item: dict[str, Any] = {
            "slot_id": slot.slot_id,
            "token_label": token.label,
            "token_serial": token.serial,
            "manufacturer": token.manufacturer_id,
            "model": token.model,
            "certificates": [],
        }
        try:
            with token.open() as session:
                for certificate in session.get_objects(
                    {Attribute.CLASS: ObjectClass.CERTIFICATE}
                ):
                    try:
                        label = certificate[Attribute.LABEL]
                    except Exception:
                        label = ""
                    try:
                        identifier = certificate[Attribute.ID]
                    except Exception:
                        identifier = b""
                    item["certificates"].append(
                        {
                            "label": label,
                            "id_hex": bytes(identifier).hex() if identifier else "",
                        }
                    )
        except Exception as exc:
            item["certificate_error"] = (
                "Il token non consente l'enumerazione pubblica senza login: "
                f"{type(exc).__name__}"
            )
        result.append(item)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enumera token e certificati PKCS#11 senza PIN"
    )
    parser.add_argument("module", type=Path, help="Percorso della DLL PKCS#11")
    args = parser.parse_args()
    try:
        print(json.dumps(probe_module(args.module), indent=2, ensure_ascii=False))
    except Exception as exc:
        parser.exit(2, f"Probe non riuscito: {exc}\n")


if __name__ == "__main__":
    main()
