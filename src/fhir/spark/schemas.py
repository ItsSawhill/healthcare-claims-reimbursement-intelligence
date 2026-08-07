"""Schemas and claim-type configuration for Spark FHIR transformations."""

from __future__ import annotations

from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


FHIR_BUNDLE_SCHEMA = StructType(
    [
        StructField("resourceType", StringType()),
        StructField("id", StringType()),
        StructField("entry", ArrayType(StructType([StructField("resource", StringType())]))),
    ]
)

BRONZE_SCHEMA = StructType(
    [
        StructField("resource_type", StringType()),
        StructField("resource_id", StringType()),
        StructField("patient_reference", StringType()),
        StructField("bundle_id", StringType()),
        StructField("source_file", StringType()),
        StructField("source_system", StringType()),
        StructField("raw_json", StringType()),
        StructField("ingested_at", TimestampType()),
        StructField("ingestion_run_id", StringType()),
        StructField("valid_resource", BooleanType()),
        StructField("validation_error", StringType()),
    ]
)

CODING_SCHEMA = StructType(
    [
        StructField("system", StringType()),
        StructField("code", StringType()),
        StructField("display", StringType()),
        StructField("version", StringType()),
    ]
)

CODEABLE_CONCEPT_SCHEMA = StructType([StructField("coding", ArrayType(CODING_SCHEMA)), StructField("text", StringType())])

IDENTIFIER_SCHEMA = StructType(
    [
        StructField("system", StringType()),
        StructField("value", StringType()),
        StructField("type", CODEABLE_CONCEPT_SCHEMA),
    ]
)

REFERENCE_SCHEMA = StructType(
    [
        StructField("reference", StringType()),
        StructField("identifier", IDENTIFIER_SCHEMA),
        StructField("display", StringType()),
    ]
)

PERIOD_SCHEMA = StructType([StructField("start", StringType()), StructField("end", StringType())])

ADDRESS_SCHEMA = ArrayType(
    StructType(
        [
            StructField("state", StringType()),
            StructField("postalCode", StringType()),
            StructField("use", StringType()),
        ]
    )
)

COVERAGE_PAYOR_SCHEMA = ArrayType(REFERENCE_SCHEMA)

COVERAGE_TYPE_SCHEMA = CODEABLE_CONCEPT_SCHEMA

CARE_TEAM_SCHEMA = ArrayType(
    StructType(
        [
            StructField("sequence", IntegerType()),
            StructField("provider", REFERENCE_SCHEMA),
            StructField("role", CODEABLE_CONCEPT_SCHEMA),
        ]
    )
)

DIAGNOSIS_SCHEMA = ArrayType(
    StructType(
        [
            StructField("sequence", IntegerType()),
            StructField("diagnosisCodeableConcept", CODEABLE_CONCEPT_SCHEMA),
            StructField("diagnosisReference", REFERENCE_SCHEMA),
            StructField("type", ArrayType(CODEABLE_CONCEPT_SCHEMA)),
        ]
    )
)

ADJUDICATION_SCHEMA = ArrayType(
    StructType(
        [
            StructField("category", CODEABLE_CONCEPT_SCHEMA),
            StructField("amount", StructType([StructField("value", DoubleType()), StructField("currency", StringType())])),
            StructField("reason", CODEABLE_CONCEPT_SCHEMA),
        ]
    )
)

ITEM_SCHEMA = ArrayType(
    StructType(
        [
            StructField("sequence", IntegerType()),
            StructField("careTeamSequence", ArrayType(IntegerType())),
            StructField("careTeamLinkId", ArrayType(IntegerType())),
            StructField("diagnosisSequence", ArrayType(IntegerType())),
            StructField("diagnosisLinkId", ArrayType(IntegerType())),
            StructField("service", CODEABLE_CONCEPT_SCHEMA),
            StructField("productOrService", CODEABLE_CONCEPT_SCHEMA),
            StructField("servicedDate", StringType()),
            StructField("servicedPeriod", PERIOD_SCHEMA),
            StructField("quantity", StructType([StructField("value", DoubleType())])),
            StructField("adjudication", ADJUDICATION_SCHEMA),
        ]
    )
)

INSURANCE_SCHEMA = ArrayType(
    StructType(
        [
            StructField("focal", BooleanType()),
            StructField("coverage", REFERENCE_SCHEMA),
        ]
    )
)

CLAIM_TYPE_PROFILES = {
    "PDE": {
        "expected_service_code_system": "http://hl7.org/fhir/sid/ndc",
        "expected_financial_concepts": ["part_d_plan_paid_amount", "part_d_patient_paid_amount", "part_d_total_drug_cost"],
        "diagnosis_expected": False,
        "provider_fields": ["provider.identifier", "careTeam.provider.identifier"],
        "status": "supported_observed",
    },
    "CARRIER": {
        "expected_service_code_system": "https://bluebutton.cms.gov/resources/codesystem/hcpcs",
        "expected_financial_concepts": ["submitted_amount", "allowed_amount", "provider_paid_amount"],
        "diagnosis_expected": True,
        "provider_fields": ["careTeam.provider.identifier", "provider.identifier"],
        "status": "supported_observed",
    },
    "OUTPATIENT": {
        "expected_service_code_system": "https://bluebutton.cms.gov/resources/codesystem/hcpcs",
        "expected_financial_concepts": ["submitted_amount", "covered_paid_amount"],
        "diagnosis_expected": True,
        "provider_fields": ["provider.reference"],
        "status": "supported_observed",
    },
    "INPATIENT": {"status": "future_profile"},
    "SNF": {"status": "future_profile"},
    "HHA": {"status": "future_profile"},
    "HOSPICE": {"status": "future_profile"},
    "DME": {"status": "future_profile"},
}

SUPPORTED_OBSERVED_CLAIM_TYPES = ["PDE", "CARRIER", "OUTPATIENT"]

CMS_ADJUDICATION_SYSTEMS = [
    "https://bluebutton.cms.gov/fhir/CodeSystem/Adjudication",
    "https://bluebutton.cms.gov/resources/codesystem/adjudication",
]

FINANCIAL_CODE_MAPPING = {
    "CLM_LINE_SBMT_CHRG_AMT": ("confirmed", "submitted_amount"),
    "CLM_SBMT_CHRG_AMT": ("confirmed", "submitted_amount"),
    "CLM_LINE_ALOWD_CHRG_AMT": ("confirmed", "allowed_amount"),
    "CLM_ALOWD_CHRG_AMT": ("confirmed", "allowed_amount"),
    "CLM_LINE_PRVDR_PMT_AMT": ("confirmed", "provider_paid_amount"),
    "CLM_PRVDR_PMT_AMT": ("confirmed", "provider_paid_amount"),
    "CLM_LINE_CVRD_PD_AMT": ("confirmed", "covered_paid_amount"),
    "CLM_LINE_BENE_PMT_AMT": ("confirmed", "beneficiary_paid_amount"),
    "CLM_BENE_PMT_AMT": ("confirmed", "beneficiary_paid_amount"),
    "CLM_LINE_BENE_PD_AMT": ("confirmed", "beneficiary_payment_amount"),
    "CLM_LINE_MDCR_DDCTBL_AMT": ("confirmed", "deductible_amount"),
    "CLM_LINE_BLOOD_DDCTBL_AMT": ("confirmed", "deductible_amount"),
    "CLM_LINE_MDCR_COINSRNC_AMT": ("confirmed", "coinsurance_amount"),
    "CLM_LINE_NCVRD_CHRG_AMT": ("confirmed", "noncovered_amount"),
    "https://bluebutton.cms.gov/resources/variables/cvrd_d_plan_pd_amt": ("confirmed", "part_d_plan_paid_amount"),
    "https://bluebutton.cms.gov/resources/variables/ptnt_pay_amt": ("confirmed", "part_d_patient_paid_amount"),
    "https://bluebutton.cms.gov/resources/variables/tot_rx_cst_amt": ("confirmed", "part_d_total_drug_cost"),
    "https://bluebutton.cms.gov/resources/variables/gdc_abv_oopt_amt": ("candidate", "part_d_gross_drug_cost_above_oop"),
    "https://bluebutton.cms.gov/resources/variables/gdc_blw_oopt_amt": ("candidate", "part_d_gross_drug_cost_below_oop"),
    "https://bluebutton.cms.gov/resources/variables/lics_amt": ("candidate", "part_d_low_income_subsidy"),
    "https://bluebutton.cms.gov/resources/variables/othr_troop_amt": ("candidate", "part_d_other_troop"),
    "https://bluebutton.cms.gov/resources/variables/plro_amt": ("candidate", "part_d_patient_liability_reduction_other"),
    "https://bluebutton.cms.gov/resources/variables/rptd_gap_dscnt_num": ("candidate", "part_d_gap_discount"),
}
