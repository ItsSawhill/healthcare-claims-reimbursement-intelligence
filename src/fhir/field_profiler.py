"""Field profiling utilities for local FHIR resource exploration."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable

from .resource_loader import FHIRResource


BLUE_BUTTON_EOB_TYPES = {"CARRIER", "DME", "HHA", "HOSPICE", "INPATIENT", "OUTPATIENT", "SNF", "PDE"}
BLUE_BUTTON_EOB_TYPE_SYSTEM = "https://bluebutton.cms.gov/resources/codesystem/eob-type"
CMS_ADJUDICATION_SYSTEMS = {
    "https://bluebutton.cms.gov/fhir/CodeSystem/Adjudication",
    "https://bluebutton.cms.gov/resources/codesystem/adjudication",
}
CARIN_ADJUDICATION_SYSTEM = "http://hl7.org/fhir/us/carin-bb/CodeSystem/C4BBAdjudication"

CMS_ADJUDICATION_DESCRIPTIONS = {
    "CLM_LINE_NCVRD_CHRG_AMT": "Non-Covered Charge Amount",
    "CLM_LINE_ALOWD_CHRG_AMT": "Line Allowed Charge Amount",
    "CLM_LINE_SBMT_CHRG_AMT": "Line Submitted Charge Amount",
    "CLM_LINE_PRVDR_PMT_AMT": "Line Provider Payment Amount",
    "CLM_LINE_BENE_PMT_AMT": "Line Paid By Beneficiary Amount",
    "CLM_LINE_BENE_PD_AMT": "Payment Amount to Beneficiary",
    "CLM_LINE_CVRD_PD_AMT": "Payment Amount",
    "CLM_LINE_BLOOD_DDCTBL_AMT": "Blood Deductible Amount",
    "CLM_LINE_MDCR_DDCTBL_AMT": "Cash Deductible Amount",
    "CLM_LINE_INSTNL_ADJSTD_AMT": "Revenue Center Coinsurance/Wage Adjusted Coinsurance Amount",
    "CLM_LINE_INSTNL_RDCD_AMT": "Revenue Center Reduced Coinsurance Amount",
    "CLM_LINE_INSTNL_MSP1_PD_AMT": "Revenue Center 1st MSP Paid Amount",
    "CLM_LINE_INSTNL_MSP2_PD_AMT": "Revenue Center 2nd MSP Paid Amount",
    "CLM_LINE_INSTNL_RATE_AMT": "Revenue Center Rate Amount",
    "CLM_SBMT_CHRG_AMT": "Total Charge Amount",
    "CLM_PRVDR_PMT_AMT": "Provider Payment Amount",
    "CLM_BENE_PMT_AMT": "Paid By Beneficiary Amount",
    "CLM_ALOWD_CHRG_AMT": "Allowed Charge Amount",
    "CLM_LINE_MDCR_COINSRNC_AMT": "Coinsurance Amount",
    "CLM_MDCR_PRFNL_PRMRY_PYR_AMT": "Primary Payer Paid Amount",
    "CLM_BENE_PRMRY_PYR_PD_AMT": "Line Primary Payer Paid Amount",
    "https://bluebutton.cms.gov/resources/variables/cvrd_d_plan_pd_amt": "Amount paid by Part D plan for the PDE",
    "https://bluebutton.cms.gov/resources/variables/gdc_blw_oopt_amt": "Gross Drug Cost Below Part D Out-of-Pocket Threshold",
    "https://bluebutton.cms.gov/resources/variables/gdc_abv_oopt_amt": "Gross Drug Cost Above Part D Out-of-Pocket Threshold",
    "https://bluebutton.cms.gov/resources/variables/ptnt_pay_amt": "Amount Paid by Patient",
    "https://bluebutton.cms.gov/resources/variables/othr_troop_amt": "Other True Out-of-Pocket Amount",
    "https://bluebutton.cms.gov/resources/variables/lics_amt": "Low Income Cost Sharing Subsidy Amount",
    "https://bluebutton.cms.gov/resources/variables/plro_amt": "Patient Liability Reduction Other Paid Amount",
    "https://bluebutton.cms.gov/resources/variables/tot_rx_cst_amt": "Total drug cost",
    "https://bluebutton.cms.gov/resources/variables/rptd_gap_dscnt_num": "Gap Discount Amount",
}

FINANCIAL_FIELD_CODES = {
    "submitted amount": {"CLM_LINE_SBMT_CHRG_AMT", "CLM_SBMT_CHRG_AMT"},
    "allowed amount": {"CLM_LINE_ALOWD_CHRG_AMT", "CLM_ALOWD_CHRG_AMT"},
    "provider paid amount": {"CLM_LINE_PRVDR_PMT_AMT", "CLM_PRVDR_PMT_AMT"},
    "beneficiary paid amount": {"CLM_LINE_BENE_PMT_AMT", "CLM_BENE_PMT_AMT"},
    "payment amount to beneficiary": {"CLM_LINE_BENE_PD_AMT"},
    "covered paid amount": {"CLM_LINE_CVRD_PD_AMT"},
    "deductible": {"CLM_LINE_BLOOD_DDCTBL_AMT", "CLM_LINE_MDCR_DDCTBL_AMT"},
    "coinsurance": {"CLM_LINE_MDCR_COINSRNC_AMT", "CLM_LINE_INSTNL_ADJSTD_AMT", "CLM_LINE_INSTNL_RDCD_AMT"},
    "non-covered charge": {"CLM_LINE_NCVRD_CHRG_AMT"},
    "part d plan paid amount": {"https://bluebutton.cms.gov/resources/variables/cvrd_d_plan_pd_amt"},
    "part d patient paid amount": {"https://bluebutton.cms.gov/resources/variables/ptnt_pay_amt"},
    "part d total drug cost": {"https://bluebutton.cms.gov/resources/variables/tot_rx_cst_amt"},
}


@dataclass(frozen=True)
class FHIRFieldProfile:
    """Summary of observed FHIR resource shape and selected EOB fields."""

    resource_counts: dict[str, int]
    resource_ids: list[dict[str, str | None]]
    top_level_fields_by_type: dict[str, list[str]]
    nested_field_paths: list[str]
    array_paths: list[str]
    object_paths: list[str]
    eob_claim_types: list[str]
    adjudication_category_codes: list[str]
    candidate_financial_amount_paths: list[str]
    earliest_service_date: str | None
    latest_service_date: str | None
    missing_field_counts: dict[str, int]


@dataclass(frozen=True)
class FinancialAdjudicationObservation:
    """Observed item-level adjudication amount and all associated codings."""

    eob_id: str | None
    eob_type: str
    item_sequence: int | None
    path: str
    amount: float | None
    currency: str | None
    codings: list[dict[str, str | None]]


@dataclass(frozen=True)
class ServiceCodingObservation:
    """Observed service or product coding from an EOB item."""

    eob_id: str | None
    eob_type: str
    item_sequence: int | None
    path: str
    system: str | None
    code: str | None
    display: str | None
    version: str | None


@dataclass(frozen=True)
class DiagnosisObservation:
    """Observed EOB diagnosis coding."""

    eob_id: str | None
    eob_type: str
    sequence: int | None
    path: str
    system: str | None
    code: str | None
    display: str | None
    diagnosis_type: str | None


def _iter_paths(value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            yield path, child
            yield from _iter_paths(child, path)
    elif isinstance(value, list):
        array_path = f"{prefix}[]" if prefix else "[]"
        yield array_path, value
        for child in value:
            if isinstance(child, dict):
                yield array_path, child
            yield from _iter_paths(child, array_path)


def list_top_level_fields(resources: list[FHIRResource]) -> dict[str, list[str]]:
    """List observed top-level fields grouped by resourceType."""
    fields: dict[str, set[str]] = defaultdict(set)
    for resource in resources:
        fields[str(resource.get("resourceType", "<missing>"))].update(resource.keys())
    return {resource_type: sorted(values) for resource_type, values in sorted(fields.items())}


def list_nested_field_paths(resources: list[FHIRResource]) -> list[str]:
    """Return all observed nested field paths using [] to represent arrays."""
    paths: set[str] = set()
    for resource in resources:
        paths.update(path for path, _ in _iter_paths(resource))
    return sorted(paths)


def profile_arrays_and_objects(resources: list[FHIRResource]) -> tuple[list[str], list[str]]:
    """Return observed array paths and nested object paths."""
    array_paths: set[str] = set()
    object_paths: set[str] = set()
    for resource in resources:
        for path, value in _iter_paths(resource):
            if isinstance(value, list):
                array_paths.add(path)
            elif isinstance(value, dict):
                object_paths.add(path)
    return sorted(array_paths), sorted(object_paths)


def _values_at_path(value: Any, path: str) -> list[Any]:
    parts = path.split(".") if path else []
    values = [value]
    for part in parts:
        next_values: list[Any] = []
        list_part = part.endswith("[]")
        key = part[:-2] if list_part else part
        for item in values:
            if isinstance(item, dict) and key in item:
                child = item[key]
                if list_part:
                    if isinstance(child, list):
                        next_values.extend(child)
                else:
                    next_values.append(child)
        values = next_values
    return values


def _coding_codes(value: Any) -> list[str]:
    codes: list[str] = []
    if isinstance(value, dict):
        for coding in value.get("coding", []) or []:
            if isinstance(coding, dict) and coding.get("code") is not None:
                codes.append(str(coding["code"]))
        if value.get("text") is not None:
            codes.append(str(value["text"]))
    return codes


def _codings(value: Any) -> list[dict[str, str | None]]:
    codings: list[dict[str, str | None]] = []
    if isinstance(value, dict):
        for coding in value.get("coding", []) or []:
            if isinstance(coding, dict):
                codings.append(
                    {
                        "system": coding.get("system"),
                        "code": coding.get("code"),
                        "display": coding.get("display"),
                        "version": coding.get("version"),
                    }
                )
    return codings


def get_eob_type(resource: FHIRResource) -> str:
    """Return the Blue Button EOB type code when available."""
    if resource.get("resourceType") != "ExplanationOfBenefit":
        return "<not-eob>"
    fallback: str | None = None
    for coding in _codings(resource.get("type")):
        code = coding.get("code")
        system = coding.get("system")
        if code in BLUE_BUTTON_EOB_TYPES and (
            system in {BLUE_BUTTON_EOB_TYPE_SYSTEM, "https://bluebutton.cms.gov/resources/codesystem/eob-type"}
            or code == code.upper()
        ):
            return code
        if fallback is None and code:
            fallback = code
    return fallback or "<unknown>"


def eob_resources(resources: list[FHIRResource]) -> list[FHIRResource]:
    """Return only ExplanationOfBenefit resources."""
    return [resource for resource in resources if resource.get("resourceType") == "ExplanationOfBenefit"]


def count_eobs_by_type(resources: list[FHIRResource]) -> dict[str, int]:
    """Count ExplanationOfBenefit resources by Blue Button claim type."""
    return dict(Counter(get_eob_type(resource) for resource in eob_resources(resources)))


def identify_eob_claim_types(resources: list[FHIRResource]) -> list[str]:
    """List observed ExplanationOfBenefit.type codes and text values."""
    observed: set[str] = set()
    for resource in resources:
        if resource.get("resourceType") == "ExplanationOfBenefit":
            observed.update(_coding_codes(resource.get("type")))
    return sorted(observed)


def identify_adjudication_category_codes(resources: list[FHIRResource]) -> list[str]:
    """List observed adjudication category codes without assigning meanings."""
    observed: set[str] = set()
    for resource in resources:
        if resource.get("resourceType") != "ExplanationOfBenefit":
            continue
        for path in ["item[].adjudication[]", "addItem[].adjudication[]", "total[]"]:
            for adjudication in _values_at_path(resource, path):
                if isinstance(adjudication, dict):
                    observed.update(_coding_codes(adjudication.get("category")))
    return sorted(observed)


def extract_financial_adjudications(resources: list[FHIRResource]) -> list[FinancialAdjudicationObservation]:
    """Extract item-level EOB adjudication amounts with all category codings."""
    observations: list[FinancialAdjudicationObservation] = []
    for resource in eob_resources(resources):
        eob_type = get_eob_type(resource)
        for item in resource.get("item", []) or []:
            if not isinstance(item, dict):
                continue
            sequence = item.get("sequence")
            for adjudication in item.get("adjudication", []) or []:
                if not isinstance(adjudication, dict):
                    continue
                amount = adjudication.get("amount") if isinstance(adjudication.get("amount"), dict) else {}
                value = amount.get("value")
                numeric_value = float(value) if isinstance(value, int | float) else None
                observations.append(
                    FinancialAdjudicationObservation(
                        eob_id=resource.get("id"),
                        eob_type=eob_type,
                        item_sequence=sequence if isinstance(sequence, int) else None,
                        path="ExplanationOfBenefit.item[].adjudication[].amount.value",
                        amount=numeric_value,
                        currency=amount.get("currency"),
                        codings=_codings(adjudication.get("category")),
                    )
                )
    return observations


def _preferred_financial_code(observation: FinancialAdjudicationObservation) -> str | None:
    for coding in observation.codings:
        code = coding.get("code")
        system = coding.get("system")
        if system in CMS_ADJUDICATION_SYSTEMS and code:
            return code
        if code in CMS_ADJUDICATION_DESCRIPTIONS:
            return code
    for coding in observation.codings:
        code = coding.get("code")
        if code:
            return code
    return None


def summarize_financial_adjudications(resources: list[FHIRResource]) -> list[dict[str, Any]]:
    """Summarize observed financial adjudication codes by EOB type and amount coverage."""
    grouped: dict[str, dict[str, Any]] = {}
    for observation in extract_financial_adjudications(resources):
        code = _preferred_financial_code(observation) or "<missing>"
        row = grouped.setdefault(
            code,
            {
                "adjudication_code": code,
                "description": CMS_ADJUDICATION_DESCRIPTIONS.get(code),
                "observed_fhir_path": observation.path,
                "claim_types_observed": set(),
                "occurrence_count": 0,
                "amount_populated_count": 0,
                "amount_coverage": 0.0,
                "carin_codes_observed": set(),
                "proposed_analytical_meaning": _financial_meaning_for_code(code),
                "mapping_status": "candidate",
                "notes": "",
            },
        )
        row["claim_types_observed"].add(observation.eob_type)
        row["occurrence_count"] += 1
        if observation.amount is not None:
            row["amount_populated_count"] += 1
        for coding in observation.codings:
            if coding.get("system") == CARIN_ADJUDICATION_SYSTEM and coding.get("code"):
                row["carin_codes_observed"].add(coding["code"])

    for row in grouped.values():
        row["claim_types_observed"] = "|".join(sorted(row["claim_types_observed"]))
        row["carin_codes_observed"] = "|".join(sorted(row["carin_codes_observed"]))
        row["amount_coverage"] = (
            row["amount_populated_count"] / row["occurrence_count"] if row["occurrence_count"] else 0.0
        )
        if row["description"] and row["proposed_analytical_meaning"]:
            row["mapping_status"] = "confirmed"
        elif row["description"]:
            row["mapping_status"] = "candidate"
        else:
            row["mapping_status"] = "unsupported"
            row["notes"] = "Code was observed in sample data but is not in the local CMS adjudication description table."
    return sorted(grouped.values(), key=lambda item: item["adjudication_code"])


def _financial_meaning_for_code(code: str) -> str | None:
    for meaning, codes in FINANCIAL_FIELD_CODES.items():
        if code in codes:
            return meaning
    return None


def unknown_financial_codes(resources: list[FHIRResource]) -> list[str]:
    """Return observed preferred adjudication codes not recognized locally."""
    unknown: set[str] = set()
    for observation in extract_financial_adjudications(resources):
        code = _preferred_financial_code(observation)
        if code and code not in CMS_ADJUDICATION_DESCRIPTIONS:
            unknown.add(code)
    return sorted(unknown)


def identify_candidate_financial_amount_paths(resources: list[FHIRResource]) -> list[str]:
    """Identify observed numeric amount-like paths without interpreting code meanings."""
    candidates: set[str] = set()
    amount_markers = ("amount", "money", "adjudication", "benefit", "cost", "payment", "total")
    for resource in resources:
        if resource.get("resourceType") != "ExplanationOfBenefit":
            continue
        for path, value in _iter_paths(resource):
            if path.endswith(".value") and isinstance(value, int | float):
                normalized = path.lower()
                if any(marker in normalized for marker in amount_markers):
                    candidates.add(path)
    return sorted(candidates)


def extract_service_codings(resources: list[FHIRResource]) -> list[ServiceCodingObservation]:
    """Extract all item.service and item.productOrService codings."""
    observations: list[ServiceCodingObservation] = []
    for resource in eob_resources(resources):
        eob_type = get_eob_type(resource)
        for item in resource.get("item", []) or []:
            if not isinstance(item, dict):
                continue
            sequence = item.get("sequence")
            for field_name in ["service", "productOrService"]:
                for coding in _codings(item.get(field_name)):
                    observations.append(
                        ServiceCodingObservation(
                            eob_id=resource.get("id"),
                            eob_type=eob_type,
                            item_sequence=sequence if isinstance(sequence, int) else None,
                            path=f"ExplanationOfBenefit.item[].{field_name}.coding[]",
                            system=coding.get("system"),
                            code=coding.get("code"),
                            display=coding.get("display"),
                            version=coding.get("version"),
                        )
                    )
    return observations


def extract_diagnoses(resources: list[FHIRResource]) -> list[DiagnosisObservation]:
    """Extract observed EOB diagnosis codes and diagnosis type codings."""
    observations: list[DiagnosisObservation] = []
    for resource in eob_resources(resources):
        eob_type = get_eob_type(resource)
        for diagnosis in resource.get("diagnosis", []) or []:
            if not isinstance(diagnosis, dict):
                continue
            sequence = diagnosis.get("sequence")
            type_codes = []
            for diagnosis_type in diagnosis.get("type", []) or []:
                type_codes.extend(coding.get("code") for coding in _codings(diagnosis_type) if coding.get("code"))
            diagnosis_type_text = "|".join(sorted(type_codes)) if type_codes else None
            for field_name in ["diagnosisCodeableConcept", "diagnosisReference"]:
                for coding in _codings(diagnosis.get(field_name)):
                    observations.append(
                        DiagnosisObservation(
                            eob_id=resource.get("id"),
                            eob_type=eob_type,
                            sequence=sequence if isinstance(sequence, int) else None,
                            path=f"ExplanationOfBenefit.diagnosis[].{field_name}.coding[]",
                            system=coding.get("system"),
                            code=coding.get("code"),
                            display=coding.get("display"),
                            diagnosis_type=diagnosis_type_text,
                        )
                    )
    return observations


def discover_provider_references(resources: list[FHIRResource]) -> list[dict[str, Any]]:
    """Discover provider identifiers/references across EOB provider and careTeam fields."""
    observations: list[dict[str, Any]] = []
    for resource in eob_resources(resources):
        eob_type = get_eob_type(resource)
        provider = resource.get("provider")
        if isinstance(provider, dict):
            observations.append(
                {
                    "eob_id": resource.get("id"),
                    "eob_type": eob_type,
                    "path": "ExplanationOfBenefit.provider",
                    "reference": provider.get("reference"),
                    "identifier_system": (provider.get("identifier") or {}).get("system")
                    if isinstance(provider.get("identifier"), dict)
                    else None,
                    "identifier_value": (provider.get("identifier") or {}).get("value")
                    if isinstance(provider.get("identifier"), dict)
                    else None,
                    "role_code": None,
                }
            )
        for care_team in resource.get("careTeam", []) or []:
            if not isinstance(care_team, dict):
                continue
            care_provider = care_team.get("provider")
            role_codes = []
            if isinstance(care_team.get("role"), dict):
                role_codes = [coding.get("code") for coding in _codings(care_team.get("role")) if coding.get("code")]
            if isinstance(care_provider, dict):
                identifier = care_provider.get("identifier") if isinstance(care_provider.get("identifier"), dict) else {}
                observations.append(
                    {
                        "eob_id": resource.get("id"),
                        "eob_type": eob_type,
                        "path": "ExplanationOfBenefit.careTeam[].provider",
                        "reference": care_provider.get("reference"),
                        "identifier_system": identifier.get("system"),
                        "identifier_value": identifier.get("value"),
                        "role_code": "|".join(role_codes) if role_codes else None,
                    }
                )
        for item in resource.get("item", []) or []:
            if not isinstance(item, dict):
                continue
            for field_name in ["careTeamSequence", "careTeamLinkId"]:
                if field_name in item:
                    observations.append(
                        {
                            "eob_id": resource.get("id"),
                            "eob_type": eob_type,
                            "path": f"ExplanationOfBenefit.item[].{field_name}",
                            "reference": str(item.get(field_name)),
                            "identifier_system": None,
                            "identifier_value": None,
                            "role_code": None,
                        }
                    )
    return observations


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def identify_service_date_range(resources: list[FHIRResource]) -> tuple[str | None, str | None]:
    """Return earliest and latest observed EOB service dates."""
    dates: list[date] = []
    date_paths = [
        "billablePeriod.start",
        "billablePeriod.end",
        "item[].servicedDate",
        "item[].servicedPeriod.start",
        "item[].servicedPeriod.end",
    ]
    for resource in resources:
        if resource.get("resourceType") != "ExplanationOfBenefit":
            continue
        for path in date_paths:
            for value in _values_at_path(resource, path):
                parsed = _parse_date(value)
                if parsed:
                    dates.append(parsed)
    if not dates:
        return None, None
    return min(dates).isoformat(), max(dates).isoformat()


def _field_populated(resource: FHIRResource, field: str) -> bool:
    financial_codes = {
        "submitted amount": FINANCIAL_FIELD_CODES["submitted amount"],
        "allowed amount": FINANCIAL_FIELD_CODES["allowed amount"],
        "provider paid amount": FINANCIAL_FIELD_CODES["provider paid amount"],
        "covered paid amount": FINANCIAL_FIELD_CODES["covered paid amount"],
        "beneficiary paid amount": FINANCIAL_FIELD_CODES["beneficiary paid amount"],
    }
    if field == "patient reference":
        return bool((resource.get("patient") or {}).get("reference")) if isinstance(resource.get("patient"), dict) else False
    if field == "billable period start":
        return bool((resource.get("billablePeriod") or {}).get("start")) if isinstance(resource.get("billablePeriod"), dict) else False
    if field == "billable period end":
        return bool((resource.get("billablePeriod") or {}).get("end")) if isinstance(resource.get("billablePeriod"), dict) else False
    if field == "provider":
        return bool(resource.get("provider") or resource.get("careTeam"))
    if field == "diagnosis":
        return bool(resource.get("diagnosis"))
    if field == "items":
        return bool(resource.get("item"))
    if field == "HCPCS/service":
        return any(
            isinstance(item, dict) and (item.get("service") or item.get("productOrService"))
            for item in resource.get("item", []) or []
        )
    if field in financial_codes:
        return any(
            _preferred_financial_code(obs) in financial_codes[field]
            for obs in extract_financial_adjudications([resource])
        )
    if field == "payment":
        return bool(resource.get("payment"))
    if field == "insurance/coverage":
        return bool(resource.get("insurance"))
    return False


def calculate_field_availability(resources: list[FHIRResource], fields: list[str] | None = None) -> list[dict[str, Any]]:
    """Calculate selected field availability by EOB claim type."""
    fields = fields or [
        "patient reference",
        "billable period start",
        "billable period end",
        "provider",
        "diagnosis",
        "items",
        "HCPCS/service",
        "submitted amount",
        "allowed amount",
        "provider paid amount",
        "covered paid amount",
        "beneficiary paid amount",
        "payment",
        "insurance/coverage",
    ]
    grouped: dict[str, list[FHIRResource]] = defaultdict(list)
    for resource in eob_resources(resources):
        grouped[get_eob_type(resource)].append(resource)

    rows: list[dict[str, Any]] = []
    for eob_type, group in sorted(grouped.items()):
        for field in fields:
            populated = sum(1 for resource in group if _field_populated(resource, field))
            rows.append(
                {
                    "eob_type": eob_type,
                    "field": field,
                    "resource_count": len(group),
                    "populated_count": populated,
                    "populated_percentage": populated / len(group) if group else 0.0,
                }
            )
    return rows


def build_profile_summary(resources: list[FHIRResource]) -> dict[str, Any]:
    """Build an analytics-preview summary from local FHIR resources."""
    eobs = eob_resources(resources)
    service_codings = extract_service_codings(resources)
    diagnoses = extract_diagnoses(resources)
    financial_observations = extract_financial_adjudications(resources)
    earliest, latest = identify_service_date_range(resources)
    eobs_with_financial = {obs.eob_id for obs in financial_observations}
    eobs_with_provider = {
        obs["eob_id"]
        for obs in discover_provider_references(resources)
        if obs.get("reference") or obs.get("identifier_value")
    }
    items = [
        (resource.get("id"), item)
        for resource in eobs
        for item in (resource.get("item", []) or [])
        if isinstance(item, dict)
    ]
    items_with_hcpcs = {
        (obs.eob_id, obs.item_sequence)
        for obs in service_codings
        if obs.code and obs.system and ("hcpcs" in obs.system.lower() or "cpt" in obs.system.lower())
    }
    return {
        "patient_resource_count": sum(1 for resource in resources if resource.get("resourceType") == "Patient"),
        "coverage_resource_count": sum(1 for resource in resources if resource.get("resourceType") == "Coverage"),
        "eob_resource_count": len(eobs),
        "eob_types": count_eobs_by_type(resources),
        "claim_line_count": len(items),
        "diagnosis_count": len(diagnoses),
        "unique_service_codes": sorted({obs.code for obs in service_codings if obs.code}),
        "service_date_min": earliest,
        "service_date_max": latest,
        "percentage_eobs_with_financial_data": len(eobs_with_financial) / len(eobs) if eobs else 0.0,
        "percentage_items_with_hcpcs": len(items_with_hcpcs) / len(items) if items else 0.0,
        "percentage_eobs_with_provider_reference": len(eobs_with_provider) / len(eobs) if eobs else 0.0,
        "unknown_adjudication_code_count": len(unknown_financial_codes(resources)),
    }


def report_missing_fields(resources: list[FHIRResource], paths: list[str]) -> dict[str, int]:
    """Count resources where each requested path is absent or null."""
    missing: dict[str, int] = {}
    for path in paths:
        count = 0
        for resource in resources:
            values = _values_at_path(resource, path)
            if not values or all(value is None for value in values):
                count += 1
        missing[path] = count
    return missing


def profile_resources(resources: list[FHIRResource], missing_field_paths: list[str] | None = None) -> FHIRFieldProfile:
    """Profile local FHIR resources for shape, EOB dates, and financial candidates."""
    missing_field_paths = missing_field_paths or ["id", "resourceType"]
    array_paths, object_paths = profile_arrays_and_objects(resources)
    earliest, latest = identify_service_date_range(resources)
    resource_ids = [
        {
            "resourceType": resource.get("resourceType"),
            "id": resource.get("id"),
        }
        for resource in resources
    ]
    return FHIRFieldProfile(
        resource_counts=dict(Counter(resource.get("resourceType", "<missing>") for resource in resources)),
        resource_ids=resource_ids,
        top_level_fields_by_type=list_top_level_fields(resources),
        nested_field_paths=list_nested_field_paths(resources),
        array_paths=array_paths,
        object_paths=object_paths,
        eob_claim_types=identify_eob_claim_types(resources),
        adjudication_category_codes=identify_adjudication_category_codes(resources),
        candidate_financial_amount_paths=identify_candidate_financial_amount_paths(resources),
        earliest_service_date=earliest,
        latest_service_date=latest,
        missing_field_counts=report_missing_fields(resources, missing_field_paths),
    )
