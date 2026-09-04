class MFirmaError(Exception):
    code = "UNKNOWN"


class FileChangedError(MFirmaError):
    code = "FILE_CHANGED"


class OutputExistsError(MFirmaError):
    code = "OUTPUT_EXISTS"


class PdfInvalidError(MFirmaError):
    code = "PDF_INVALID"


class SignatureFailedError(MFirmaError):
    code = "SIGNATURE_FAILED"


class ProviderConfigurationError(MFirmaError):
    code = "MODULE_LOAD_FAILED"


class SignedOutputInvalidError(MFirmaError):
    code = "SIGNED_OUTPUT_INVALID"
