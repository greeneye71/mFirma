from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _public_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").rstrip("\0 ")
    return str(value).rstrip("\0 ")


def _public_hex(value: object) -> str:
    """Encode a public byte field losslessly for the parent process."""
    if value is None:
        return ""
    if isinstance(value, str):
        value = value.encode("utf-8")
    try:
        return bytes(value).hex()  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return ""


def _certificate_details(value: object) -> dict[str, object]:
    try:
        from cryptography import x509

        certificate = x509.load_der_x509_certificate(bytes(value))  # type: ignore[arg-type]
    except Exception:
        return {}

    try:
        usage = certificate.extensions.get_extension_for_class(x509.KeyUsage).value
        key_usage = {
            "digital_signature": usage.digital_signature,
            "content_commitment": usage.content_commitment,
        }
    except x509.ExtensionNotFound:
        key_usage = {}

    return {
        "subject": certificate.subject.rfc4514_string(),
        "issuer": certificate.issuer.rfc4514_string(),
        "not_before": certificate.not_valid_before_utc.date().isoformat(),
        "not_after": certificate.not_valid_after_utc.date().isoformat(),
        "key_usage": key_usage,
    }


def _certificate_key_usage(value: object) -> dict[str, bool]:
    details = _certificate_details(value)
    key_usage = details.get("key_usage", {})
    return key_usage if isinstance(key_usage, dict) else {}


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
            "token_label": _public_text(token.label),
            "token_serial": _public_text(token.serial),
            "token_serial_hex": _public_hex(token.serial),
            "manufacturer": _public_text(token.manufacturer_id),
            "model": _public_text(token.model),
            "certificates": [],
        }
        try:
            with token.open() as session:
                for certificate in session.get_objects(
                    {Attribute.CLASS: ObjectClass.CERTIFICATE}
                ):
                    try:
                        label = _public_text(certificate[Attribute.LABEL])
                    except Exception:
                        label = ""
                    try:
                        identifier = certificate[Attribute.ID]
                    except Exception:
                        identifier = b""
                    try:
                        details = _certificate_details(certificate[Attribute.VALUE])
                    except Exception:
                        details = {}
                    item["certificates"].append(
                        {
                            "label": label,
                            "id_hex": bytes(identifier).hex() if identifier else "",
                            **details,
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
