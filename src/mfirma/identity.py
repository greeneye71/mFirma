from __future__ import annotations


def distinguished_name_value(value: str, oid_name: str = "COMMON_NAME") -> str:
    if not value:
        return ""
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID

        name = x509.Name.from_rfc4514_string(value)
        attributes = name.get_attributes_for_oid(getattr(NameOID, oid_name))
        return str(attributes[0].value).strip() if attributes else ""
    except (AttributeError, IndexError, TypeError, ValueError):
        return ""


def signer_display_name(subject: str, label: str = "") -> str:
    return distinguished_name_value(subject) or subject.strip() or label.strip()
