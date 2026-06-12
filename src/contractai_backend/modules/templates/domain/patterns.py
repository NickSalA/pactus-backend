"""Regular expression patterns and declarative rules used across the templates module."""

import re

# ==============================================================================
# 1. TEMPLATE AUTHORING SERVICE PATTERNS
# ==============================================================================
STALE_AI_WARNING_PATTERNS = (
    re.compile(r"^El campo '.*' no est[aá] siendo utilizado en el cuerpo del documento\.?$", re.IGNORECASE),
    re.compile(r"^Campos definidos pero no usados:", re.IGNORECASE),
)

CONTRACT_CLOSING_PATTERNS = (
    r"(?im)^en fe de lo cual\b",
    r"(?im)^en se[nñ]al de conformidad\b",
    r"(?im)^para constancia\b",
    r"(?im)^firman\b",
    r"(?im)^suscriben\b",
)

LABOR_CLASSIFIER_PATTERNS = (
    (r"\btrabajador(?:es)?\b", 2),
    (r"\bemplead(?:o|a|os|as)\b", 2),
    (r"\bempleador\b", 2),
    (r"\bremuneraci[oó]n\b", 2),
    (r"\bjornada\b", 2),
    (r"\bvacaciones\b", 2),
    (r"\bperiodo de prueba\b", 3),
    (r"\bplanilla\b", 3),
    (r"\bsubordinaci[oó]n\b", 3),
    (r"\bsujeto a modalidad\b", 4),
    (r"\bcontrato de trabajo\b", 4),
    (r"\bdecreto legislativo\s*(?:n[°oº]?\s*)?728\b", 4),
    (r"\bley de productividad y competitividad laboral\b", 4),
)

COMPANY_CLASSIFIER_PATTERNS = (
    (r"\bempresa(?:s)?\b", 1),
    (r"\bcliente(?:s)?\b", 2),
    (r"\bproveedor(?:es)?\b", 2),
    (r"\bmanagement\b", 4),
    (r"\bgerenc(?:ia|iamiento|ial)\b", 4),
    (r"\bservicio(?:s)?\b", 1),
    (r"\bpersona jur[ií]dica\b", 2),
    (r"\bsociedad an[oó]nima\b", 2),
    (r"\br\.?u\.?c\.?\b", 1),
    (r"\bcontrato comercial\b", 3),
)

# ==============================================================================
# 2. RENDERED CONTRACT FORMATTER PATTERNS
# ==============================================================================
SIGNATURE_BLOCK_MARKER = 'data-generated-signatures="true"'
UNDERSCORE_LINE_PATTERN = re.compile(r"^_{8,}\s*$")
CLOSING_LINE_PATTERN = re.compile(r"^(?:en fe de lo cual|en se[nñ]al de conformidad|para constancia|firman|suscriben)\b", re.IGNORECASE)
SIGNATURE_TITLE_PATTERN = re.compile(
    r"^(?:la empresa|el gerente|la contratista|la contraparte|el empleador|el trabajador)$",
    re.IGNORECASE,
)
SIGNATURE_PLACEHOLDER_PATTERN = re.compile(r"^{{\s*(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)\s*}}$")
SIGNATURE_PLACEHOLDER_KEYS = frozenset(
    {
        "representante_nombre",
        "representante_nombre_empresa",
        "representante_nombre_empleador",
        "gerente_representante_nombre",
        "contratista_representante_nombre",
        "representante_nombre_contratista",
        "representante_nombre_gerente",
        "contratista_nombre_representante",
        "gerente_nombre_representante",
        "trabajador_nombre",
        "empleador_razon_social",
        "gerente_razon_social",
        "contratista_razon_social",
    }
)

# ==============================================================================
# 3. TEMPLATE CONTENT SYNCHRONIZER PATTERNS
# ==============================================================================
BRACKET_PLACEHOLDER_PATTERN = re.compile(r"\[([^\[\]\n]{2,200})\]")
TIME_PLACEHOLDER_PATTERN = re.compile(r"^(?:[01]?\d|2[0-3]):[0-5]\d(?:\s?(?:AM|PM|am|pm))?$")
MARKDOWN_IMAGE_PATTERN_MULTILINE = re.compile(r"^\s*!\[[^\]]*\]\([^\)]+\)\s*$", re.MULTILINE)
REFERENCE_IMAGE_ARTIFACT_PATTERN_MULTILINE = re.compile(r"^\s*!{{[^{}\n]+}}\([^\)]+\)\s*$", re.MULTILINE)
LEGACY_DATE_FILTER_PATTERN = re.compile(r"{{\s*(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)\s*\|\s*date\s*:\s*(?P<quote>['\"])(?P<fmt>.*?)\2\s*}}")
SHORTHAND_DATE_FILTER_PATTERN = re.compile(r"{{\s*(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)\s*\|\s*date\s*\(\s*(?P<quote>['\"])(?P<fmt>.*?)\2\s*\)\s*}}")
DATE_COMPONENT_FILTER_PATTERN = re.compile(r"{{\s*(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)\s*\|\s*(?P<component>day|month|year)\s*}}")
IGNORED_BRACKET_MARKERS = frozenset({"cierre_documento"})

AUTO_VARIABLE_ALIASES = {
    "representante_nombre_empresa": "representante_nombre",
    "representante_nombre_empleador": "representante_nombre",
    "representante_dni_empresa": "representante_dni",
    "representante_dni_empleador": "representante_dni",
    "ruc_empresa": "empleador_ruc",
    "empresa_ruc": "empleador_ruc",
    "razon_social_empresa": "empleador_razon_social",
    "empresa_razon_social": "empleador_razon_social",
    "domicilio_empresa": "empleador_domicilio",
    "empresa_domicilio": "empleador_domicilio",
    "objeto_social_empresa": "empleador_objeto_social",
    "empresa_objeto_social": "empleador_objeto_social",
    "empleador_tipo_sociedad": "empleador_descripcion",
    "tipo_sociedad_empresa": "empleador_descripcion",
}
MANUAL_FIELD_ALIASES = {
    "remuneracion_mensual_fija": "remuneracion_mensual",
}
PLACEHOLDER_KEY_ALIASES = {
    **AUTO_VARIABLE_ALIASES,
    **MANUAL_FIELD_ALIASES,
}

START_DATE_KEYS = (
    "contrato_fecha_inicio",
    "contract_start_date",
    "fecha_inicio",
    "start_date",
)
END_DATE_KEYS = (
    "contrato_fecha_fin",
    "contract_end_date",
    "fecha_fin",
    "end_date",
)
CONTRACT_DATE_HINTS = frozenset({"contrato", "contract", "vigencia", "plazo", "periodo"})
START_DATE_HINTS = frozenset({"inicio", "start", "desde", "inicial", "comienzo", "inicio_real"})
END_DATE_HINTS = frozenset({"fin", "end", "hasta", "final", "termino", "terminacion", "vencimiento"})
DATE_VALUE_HINTS = frozenset({"fecha", "date"})
SERVICE_HINTS = frozenset({"servicio", "service", "prestacion", "item"})

# ==============================================================================
# 4. TEMPLATE PLACEHOLDER VALIDATOR PATTERNS
# ==============================================================================
EXPRESSION_PATTERN = re.compile(r"{{\s*(.*?)\s*}}")
SIMPLE_PLACEHOLDER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
SUPPORTED_FORMAT_DATE_EXPRESSION_PATTERN = re.compile(
    r"^(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)\s*\|\s*format_date\s*\(\s*(?P<quote>['\"])(?P<fmt>.*?)\2\s*\)$"
)
CLAUSE_PATTERN = re.compile(r"\*\*(?P<label>[A-ZÁÉÍÓÚÑ ]+?)\.\-\*\*", re.IGNORECASE)
MARKDOWN_HEADING_PATTERN = re.compile(r"^#{1,6}\s+(?P<title>.+)$")
NAMED_STRUCTURE_PATTERN = re.compile(
    r"^(?:\*\*)?(?P<prefix>cl[aá]usula|art[ií]culo|secci[oó]n|cap[ií]tulo)\s+(?P<identifier>[A-Z0-9IVXLCM]+(?:\.\d+)*)",
    re.IGNORECASE,
)
CLAUSE_ORDER = {
    "PRIMERA": 1,
    "SEGUNDA": 2,
    "TERCERA": 3,
    "CUARTA": 4,
    "QUINTA": 5,
    "SEXTA": 6,
    "SEPTIMA": 7,
    "SETIMA": 7,
    "OCTAVA": 8,
    "NOVENA": 9,
    "DECIMA": 10,
    "DECIMO PRIMERA": 11,
    "DECIMO SEGUNDA": 12,
    "DECIMO TERCERA": 13,
    "DECIMO CUARTA": 14,
    "DECIMO QUINTA": 15,
    "DECIMO SEXTA": 16,
    "DECIMO SEPTIMA": 17,
    "DECIMO OCTAVA": 18,
    "DECIMO NOVENA": 19,
    "VIGESIMA": 20,
}
AUTO_VARIABLES = frozenset(
    {
        "empleador_razon_social",
        "empleador_ruc",
        "empleador_domicilio",
        "empleador_descripcion",
        "empleador_objeto_social",
        "representante_nombre",
        "representante_dni",
        "jurisdiccion",
        "lugar_firma",
        "autorizacion_entidad",
        "autorizacion_fecha",
        "autorizacion_emitida_por",
        "empleador_email",
        "empleador_telefono",
        "day_sign",
        "month_sign",
        "year_sign",
    }
)

# ==============================================================================
# 5. TEMPLATE REFERENCE PREPROCESSOR PATTERNS
# ==============================================================================
WHITESPACE_PATTERN = re.compile(r"\s+")
MULTI_BLANK_PATTERN = re.compile(r"\n{3,}")
CLAUSE_HEADING_PATTERN = re.compile(
    r"^(cl[aá]usula|art[ií]culo|cap[ií]tulo|secci[oó]n|primera|segunda|tercera|cuarta|quinta|sexta|septima|séptima|octava|novena|d[eé]cima|und[eé]cima|duod[eé]cima)\b",
    re.IGNORECASE,
)
PAGE_LINE_PATTERN = re.compile(r"^(p[aá]gina\s+\d+|\d+\s*/\s*\d+)$", re.IGNORECASE)
CLAUSE_LABEL_PATTERN = re.compile(r"\*\*(?P<label>[A-ZÁÉÍÓÚÑ ]+?)\s*\.\-\*\*", re.IGNORECASE)
MARKDOWN_IMAGE_PATTERN = re.compile(r"^!\[[^\]]*\]\([^\)]+\)$")
REFERENCE_IMAGE_ARTIFACT_PATTERN = re.compile(r"^!{{[^{}\n]+}}\([^\)]+\)$")
POSITIVE_KEYWORDS = (
    "comparecen",
    "partes",
    "objeto",
    "servicio",
    "plazo",
    "vigencia",
    "remuneracion",
    "remuneración",
    "honorarios",
    "pago",
    "obligaciones",
    "confidencialidad",
    "resolucion",
    "resolución",
    "terminacion",
    "terminación",
)
NEGATIVE_KEYWORDS = ("firma", "firmas", "anexo", "anexos", "huella", "sello")
