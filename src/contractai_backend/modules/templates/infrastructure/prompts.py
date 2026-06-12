"""Prompts and prompt-building logic for Gemini Template Draft Generator."""


DOCUMENT_TYPE_RULES: dict[str, str] = {
    "COMPANY": (
        "- IMPORTANT: You MUST use the following canonical keys for client data: 'cliente_nombre', 'cliente_ruc', 'cliente_domicilio', 'representante_cliente'.\n"
        "- For financial data, use 'monto_retribucion' and 'moneda'.\n"
        "- For dates, use 'fecha_inicio' and 'fecha_fin'.\n"
        "- If the reference document does not explicitly state the client's RUC or name, you MUST add 'cliente_nombre' and 'cliente_ruc' to content.operational_fields so the backend can collect them."
    ),
    "LABOR": (
        "- IMPORTANT: You MUST use the following canonical keys for the employee: 'trabajador_nombre', 'trabajador_dni', 'trabajador_domicilio'.\n"
        "- For the job role, use 'cargo'.\n"
        "- For the remuneration, ALWAYS use 'salario' (must be type number), 'moneda' (PEN/USD), and 'periodicidad' (e.g. MENSUAL).\n"
        "- For the contract type, use 'modalidad'.\n"
        "- For dates, use 'fecha_inicio' and 'fecha_fin'.\n"
        "- Any of these canonical keys that do not naturally appear in the text MUST be added to content.operational_fields. They are mandatory for backend processing."
    )
}

BASE_SYSTEM_INSTRUCTIONS = [
    "Use only these field types: text, number, date, time, boolean.",
    "Use type 'time' for hour-only values such as hora_inicio, hora_fin, hora_ingreso or horario_refrigerio.",
    "Use type 'text' for identifiers such as DNI and RUC.",
    "Use type 'text' for fields expressed in words or letters, such as monto_literal or remuneracion_en_letras.",
    "Use snake_case for keys.",
    "Use Jinja placeholders like {{ key }} in body_md.",
    "Provide a useful placeholder example for every field and operational field. Use examples prefixed with 'Ej.' and never instructional text like 'Ingrese', 'Seleccione' or 'Indique'.",
    "Respect DOCUMENT_TYPE and FORMAT_CODE as the target base format for the draft.",
    "For employer-side data that already exists as an auto variable, use the canonical auto variable name instead of creating aliases like representante_nombre_empresa or ruc_empresa.",
    "Do not use filters inside placeholders.",
    "Each placeholder must appear at most once across content.fields and content.operational_fields.",
    "If a placeholder appears in body_md, define it ONLY in content.fields. If it is required by backend workflows but does not appear in body_md, define it ONLY in content.operational_fields.",
    "Reuse one canonical key per fact. Do not invent naming variants for the same party attribute unless the contract text clearly distinguishes them as different facts.",
    "Any placeholder that appears directly in body_md must be marked as required=true. Optional visible placeholders are not allowed because they break the contract text when empty.",
    "Use content.operational_fields for extra form fields needed by backend workflows when they should not appear in body_md.",
    "When the contract defines a validity term, duration, plazo or vigencia, expose the contract start and end as dedicated placeholders if they belong in the contract text; otherwise put them in content.operational_fields, and set content.contract_date_mapping accordingly.",
    "A duration-only field such as duracion_contrato or plazo_contrato is not equivalent to start_date or end_date and must not be mapped as either boundary.",
    "The fields referenced by content.contract_date_mapping must exist either in content.fields or content.operational_fields. Prefer type 'date' for those fields.",
    "If the contract does not expose both dates clearly enough, set content.contract_date_mapping to null and add a warning describing the ambiguity.",
    "Preserve distinct placeholders from the reference unless they are clearly invalid. Do not aggressively merge or remove fields.",
    "Convert reference markers written as [NOMBRE DEL CAMPO] into proper Jinja placeholders instead of leaving them literal in body_md.",
    "Do not include signature blocks, underscore signature lines, signer labels, or representative placeholders at the end of body_md. Signature rendering is handled by the backend.",
    "Use Spanish legal language in body_md."
]

CONDITIONAL_INSTRUCTIONS = {
    "organization_context": "- Use ORGANIZATION_CONTEXT only as drafting context. Do not hardcode those values in body_md when an auto variable exists.",
    "reference_context": "- Preserve the original contract structure from REFERENCE_CONTEXT as faithfully as possible. Replace variable values with placeholders, but do not freely rewrite or summarize clauses.",
    "reference_outline": "- Preserve every item in clause_sequence when available, and otherwise preserve the order of structure_sequence. Do not omit structural markers that appear in the reference.",
    "validation_feedback": "- Correct every listed issue in VALIDATION_FEEDBACK in this attempt.",
    "generation_mode_strict": "- Since GENERATION_MODE is strict, stay as close as possible to the original wording. Do not add new legal clauses that are absent from the reference just to make the template operational.",
    "generation_mode_adaptive": "- Since GENERATION_MODE is adaptive, the reference is guidance, not a literal constraint. You may add a concise vigencia clause to body_md when explicit contract start and end placeholders are needed."
}

def build_system_prompt(*,
    auto_variables: set[str],
    document_type: str,
    has_organization: bool,
    has_reference: bool,
    has_outline: bool,
    has_feedback: bool,
    generation_mode: str
) -> str:
    """Builds the structured system prompt for template draft generation."""
    # Start with base schema and role definition
    prompt_parts = [
        "You are a legal template generator. Return ONLY valid JSON.\n"
        "The JSON must match this schema:\n"
        "{\n"
        '  "name": string,\n'
        '  "description": string|null,\n'
        '  "content": {\n'
        '    "body_md": string,\n'
        '    "fields": [\n'
        '      {"key": string, "label": string, "type": string, "required": boolean, "placeholder": string|null}\n'
        "    ],\n"
        '    "operational_fields": [\n'
        '      {"key": string, "label": string, "type": string, "required": boolean, "placeholder": string|null}\n'
        "    ],\n"
        '    "contract_date_mapping": {"start_date_field": string, "end_date_field": string} | null,\n'
        '    "version": "1.0"\n'
        "  },\n"
        '  "warnings": [string],\n'
        '  "source": {}\n'
        "}\n",
        "Rules:"
    ]

    # 1. Base instructions
    for rule in BASE_SYSTEM_INSTRUCTIONS:
        prompt_parts.append(f"- {rule}")

    # 2. Auto variables rule
    vars_list = ", ".join(sorted(auto_variables))
    prompt_parts.append(f"- Every placeholder must exist in fields or be one of these auto variables:\n  {vars_list}.")

    # 3. Conditional instructions (cleanly decoupled!)
    if has_organization:
        prompt_parts.append(CONDITIONAL_INSTRUCTIONS["organization_context"])
        prompt_parts.append("- Use only the auto variables that are relevant for the contract. Do not force every available variable into the template.")

    if has_reference:
        prompt_parts.append(CONDITIONAL_INSTRUCTIONS["reference_context"])

    if has_outline:
        prompt_parts.append(CONDITIONAL_INSTRUCTIONS["reference_outline"])
        prompt_parts.append("- Preserve section titles and the closing section when they appear in the reference.")

    if has_feedback:
        prompt_parts.append(CONDITIONAL_INSTRUCTIONS["validation_feedback"])

    if generation_mode == "strict":
        prompt_parts.append(CONDITIONAL_INSTRUCTIONS["generation_mode_strict"])
    elif generation_mode == "adaptive":
        prompt_parts.append(CONDITIONAL_INSTRUCTIONS["generation_mode_adaptive"])

    # 4. Document-type specific rules
    if document_type in DOCUMENT_TYPE_RULES:
        prompt_parts.append(DOCUMENT_TYPE_RULES[document_type])

    return "\n".join(prompt_parts) + "\n"
