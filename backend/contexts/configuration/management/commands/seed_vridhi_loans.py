from __future__ import annotations

from uuid import UUID

from django.core.management import call_command
from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import transaction

from contexts.configuration.models import (
    CatalogueStatus,
    Domain,
    Service,
    ServiceDocumentRequirement,
    ServiceDocumentRequirementSet,
    ServiceOperationalField,
    ServiceProcessStep,
    Vertical,
)


SERVICES = {'MSY_LOAN': {'name': 'M.S.Y. Loan',
              'description': 'M.S.Y. loan documentation and processing.',
              'fields': (),
              'documents': (('AADHAAR_CARD', 'Aadhaar Card', '', 'IDENTITY_KYC', True, 10),
                            ('PAN_CARD', 'PAN Card', '', 'IDENTITY_KYC', True, 20),
                            ('PASSPORT_PHOTO',
                             'Passport Size Photograph',
                             '',
                             'IDENTITY_KYC',
                             True,
                             30),
                            ('UDYAM_CERTIFICATE',
                             'Udyam Registration Certificate',
                             '',
                             'REGISTRATION',
                             True,
                             40),
                            ('DOMICILE_CERTIFICATE',
                             'Domicile Certificate',
                             '',
                             'OTHER',
                             True,
                             50),
                            ('PROJECT_REPORT', 'Project Report', '', 'OTHER', True, 60),
                            ('EDUCATIONAL_QUALIFICATION',
                             'Educational Qualification Proof',
                             '',
                             'OTHER',
                             True,
                             70),
                            ('EMAIL_ID', 'Email ID', '', 'OTHER', True, 80),
                            ('BANK_DETAILS', 'Bank Details', '', 'BANKING', True, 90),
                            ('AFFIDAVIT', 'Affidavit', '', 'LEGAL', True, 100),
                            ('MUDRA_FORM_ANNEXURE',
                             'Mudra Form with Annexure',
                             '',
                             'OTHER',
                             True,
                             110),
                            ('BS79_RENTED_SHOP',
                             'BS-79 (For Rented Shop)',
                             '',
                             'OTHER',
                             False,
                             120),
                            ('OWNER_ELECTRICITY_BILL',
                             "Owner's Electricity Bill (For Rented Shop)",
                             '',
                             'OTHER',
                             False,
                             130),
                            ('RESIDENTIAL_ELECTRICITY_BILL',
                             'Residential Electricity Bill',
                             '',
                             'OTHER',
                             True,
                             140),
                            ('RENT_AGREEMENT',
                             'Rent Agreement (If Shop is Rented)',
                             '',
                             'LEGAL',
                             False,
                             150),
                            ('TERM_LOAN_QUOTATION',
                             'Quotation for Term Loan',
                             '',
                             'OTHER',
                             True,
                             160),
                            ('CC_STOCK_STATEMENT',
                             'Stock Statement (For CC Limit)',
                             '',
                             'OTHER',
                             False,
                             170))},
 'BRE_LOAN': {'name': 'B.R.E. Loan',
              'description': 'B.R.E. loan documentation and processing.',
              'fields': (),
              'documents': (('PAN_CARD', 'PAN Card', '', 'IDENTITY_KYC', True, 10),
                            ('AADHAAR_CARD', 'Aadhaar Card', '', 'IDENTITY_KYC', True, 20),
                            ('UDYAM_GST_CERTIFICATE',
                             'Udyam/GST Certificate',
                             '',
                             'REGISTRATION',
                             True,
                             30),
                            ('GST_PORTAL_ACCESS',
                             'GST Portal Access Confirmation',
                             'GST portal access is required for this service. Portal '
                             'passwords must not be uploaded or stored in the document '
                             'repository.',
                             'OTHER',
                             True,
                             40),
                            ('ITR_PORTAL_ACCESS',
                             'ITR Portal Access Confirmation',
                             'ITR portal access is required for this service. Portal '
                             'passwords must not be uploaded or stored in the document '
                             'repository.',
                             'OTHER',
                             True,
                             50),
                            ('BANK_STATEMENT_13_MONTHS',
                             'Last 13 Months Bank Statement',
                             '',
                             'BANKING',
                             True,
                             60),
                            ('MOBILE_NUMBER', 'Mobile Number', '', 'OTHER', True, 70),
                            ('EMAIL_ID', 'Email ID', '', 'OTHER', True, 80),
                            ('RENT_AGREEMENT_ELECTRICITY',
                             'Rent Agreement & Electricity Bill (If Applicable)',
                             '',
                             'OTHER',
                             False,
                             90),
                            ('RESIDENTIAL_ELECTRICITY_BILL',
                             'Latest Residential Electricity Bill',
                             '',
                             'OTHER',
                             True,
                             100))},
 'MUDRA_LOAN': {'name': 'Mudra Loan',
                'description': 'Mudra loan documentation and processing.',
                # Mudra Phase 1 (configuration foundation only): operational
                # field definitions. Values are stored on
                # WorkItem.operational_data at runtime; no runtime workflow,
                # transition, or WorkProcessState behaviour is implemented here.
                # 'required' below is the generic field-validation flag only.
                # Conditional business rules (e.g. CIBIL score gating
                # eligibility, mandatory rejection reason) belong to later
                # phases and are intentionally NOT encoded as universal
                # required=True here.
                'fields': ({'key': 'requested_loan_amount',
                            'label': 'Requested Loan Amount',
                            'field_type': 'NUMBER',
                            'required': True,
                            'options': [],
                            'display_order': 10},
                           {'key': 'loan_purpose',
                            'label': 'Loan Purpose',
                            'field_type': 'TEXT',
                            'required': True,
                            'options': [],
                            'display_order': 20},
                           {'key': 'business_activity',
                            'label': 'Business / Activity',
                            'field_type': 'TEXT',
                            'required': True,
                            'options': [],
                            'display_order': 30},
                           {'key': 'application_reference',
                            'label': 'Application Reference Number',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 40},
                           {'key': 'application_date',
                            'label': 'Application Date',
                            'field_type': 'DATE',
                            'required': False,
                            'options': [],
                            'display_order': 50},
                           {'key': 'cibil_score',
                            'label': 'CIBIL Score',
                            'field_type': 'NUMBER',
                            'required': False,
                            'options': [],
                            'display_order': 60},
                           {'key': 'cibil_bureau',
                            'label': 'Credit Bureau',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 70},
                           {'key': 'cibil_check_date',
                            'label': 'CIBIL Check Date',
                            'field_type': 'DATE',
                            'required': False,
                            'options': [],
                            'display_order': 80},
                           {'key': 'cibil_result',
                            'label': 'CIBIL Result',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 90},
                           {'key': 'cibil_report_reference',
                            'label': 'CIBIL Report Reference',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 100},
                           {'key': 'cibil_remarks',
                            'label': 'CIBIL Remarks',
                            'field_type': 'LONG_TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 110},
                           {'key': 'eligibility_result',
                            'label': 'Eligibility Result',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 120},
                           {'key': 'eligibility_date',
                            'label': 'Eligibility Date',
                            'field_type': 'DATE',
                            'required': False,
                            'options': [],
                            'display_order': 130},
                           {'key': 'rejection_reason',
                            'label': 'Rejection Reason',
                            'field_type': 'LONG_TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 140},
                           {'key': 'project_report_prepared',
                            'label': 'Project Report Prepared',
                            'field_type': 'BOOLEAN',
                            'required': False,
                            'options': [],
                            'display_order': 150},
                           {'key': 'project_report_date',
                            'label': 'Project Report Date',
                            'field_type': 'DATE',
                            'required': False,
                            'options': [],
                            'display_order': 160},
                           {'key': 'bank_name',
                            'label': 'Bank Name',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 170},
                           {'key': 'bank_branch',
                            'label': 'Bank Branch',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 180},
                           {'key': 'bank_file_transfer_date',
                            'label': 'File Transfer Date',
                            'field_type': 'DATE',
                            'required': False,
                            'options': [],
                            'display_order': 190},
                           {'key': 'bank_reference',
                            'label': 'Bank Reference',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 200},
                           {'key': 'bank_acknowledgement_date',
                            'label': 'Bank Acknowledgement Date',
                            'field_type': 'DATE',
                            'required': False,
                            'options': [],
                            'display_order': 210},
                           {'key': 'bank_verification_status',
                            'label': 'Bank Verification Status',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 220},
                           {'key': 'bank_verification_date',
                            'label': 'Bank Verification Date',
                            'field_type': 'DATE',
                            'required': False,
                            'options': [],
                            'display_order': 230},
                           {'key': 'bank_verification_remarks',
                            'label': 'Bank Verification Remarks',
                            'field_type': 'LONG_TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 240},
                           {'key': 'ro_name',
                            'label': 'RO Name / Reference',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 250},
                           {'key': 'ro_review_status',
                            'label': 'RO Review Status',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 260},
                           {'key': 'ro_review_date',
                            'label': 'RO Review Date',
                            'field_type': 'DATE',
                            'required': False,
                            'options': [],
                            'display_order': 270},
                           {'key': 'ro_review_remarks',
                            'label': 'RO Review Remarks',
                            'field_type': 'LONG_TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 280},
                           {'key': 'sanctioned_amount',
                            'label': 'Sanctioned Amount',
                            'field_type': 'NUMBER',
                            'required': False,
                            'options': [],
                            'display_order': 290},
                           {'key': 'sanction_date',
                            'label': 'Sanction Date',
                            'field_type': 'DATE',
                            'required': False,
                            'options': [],
                            'display_order': 300},
                           {'key': 'sanction_reference',
                            'label': 'Sanction Reference',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 310},
                           {'key': 'sanction_remarks',
                            'label': 'Sanction Remarks',
                            'field_type': 'LONG_TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 320},
                           {'key': 'sanction_conditions_status',
                            'label': 'Sanction Conditions Status',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 330},
                           {'key': 'sanction_conditions_completed_date',
                            'label': 'Sanction Conditions Completed Date',
                            'field_type': 'DATE',
                            'required': False,
                            'options': [],
                            'display_order': 340},
                           {'key': 'disbursement_ready_date',
                            'label': 'Disbursement Ready Date',
                            'field_type': 'DATE',
                            'required': False,
                            'options': [],
                            'display_order': 350},
                           {'key': 'disbursed_amount',
                            'label': 'Disbursed Amount',
                            'field_type': 'NUMBER',
                            'required': False,
                            'options': [],
                            'display_order': 360},
                           {'key': 'disbursement_date',
                            'label': 'Disbursement Date',
                            'field_type': 'DATE',
                            'required': False,
                            'options': [],
                            'display_order': 370},
                           {'key': 'disbursement_reference',
                            'label': 'Disbursement Reference',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 380},
                           {'key': 'mudra_outcome',
                            'label': 'Mudra Outcome',
                            'field_type': 'TEXT',
                            'required': False,
                            'options': [],
                            'display_order': 390},
                           {'key': 'closure_date',
                            'label': 'Closure Date',
                            'field_type': 'DATE',
                            'required': False,
                            'options': [],
                            'display_order': 400}),
                # Mudra Phase 1: authoritative service process-step
                # DEFINITIONS only (configuration.ServiceProcessStep). These
                # are the 10 locked Mudra process positions. They do NOT create
                # runtime WorkProcessState rows and do NOT implement any
                # transition. Client 18-stage -> 10-step mapping:
                #   Lead/Application/KYC/Checklist/Document Tagging -> APPLICATION
                #   CIBIL/Eligibility                               -> CREDIT_ELIGIBILITY
                #   Project Report                                  -> FILE_PREPARATION
                #   Bank Transfer/Bank Received                     -> BANK_SUBMITTED
                #   Bank Verification                               -> BANK_VERIFICATION
                #   Pending Task / Re-QC loop                       -> BANK_PENDING
                #   RO Review                                       -> RO_REVIEW
                #   Sanction/Sanction Conditions                    -> SANCTIONED
                #   Disbursement Ready/Disbursement                 -> DISBURSEMENT
                #   Closed                                          -> CLOSED
                'process_steps': (('APPLICATION', 'Application & KYC', 10),
                                  ('CREDIT_ELIGIBILITY', 'Credit & Eligibility', 20),
                                  ('FILE_PREPARATION', 'File Preparation', 30),
                                  ('BANK_SUBMITTED', 'Bank Submitted', 40),
                                  ('BANK_VERIFICATION', 'Bank Verification', 50),
                                  ('BANK_PENDING', 'Bank Pending', 60),
                                  ('RO_REVIEW', 'RO Review', 70),
                                  ('SANCTIONED', 'Sanctioned', 80),
                                  ('DISBURSEMENT', 'Disbursement', 90),
                                  ('CLOSED', 'Closed', 100)),
                'documents': (('AADHAAR_CARD',
                               'Aadhaar Card',
                               '',
                               'IDENTITY_KYC',
                               True,
                               10),
                              ('PAN_CARD', 'PAN Card', '', 'IDENTITY_KYC', True, 20),
                              ('DOMICILE_CERTIFICATE',
                               'Domicile Certificate',
                               '',
                               'OTHER',
                               True,
                               30),
                              ('PROJECT_REPORT', 'Project Report', '', 'OTHER', True, 40),
                              ('AFFIDAVIT', 'Affidavit', '', 'LEGAL', True, 50),
                              ('QUOTATION', 'Quotation', '', 'OTHER', True, 60),
                              ('PASSPORT_PHOTO',
                               'Passport Size Photograph',
                               '',
                               'IDENTITY_KYC',
                               True,
                               70),
                              ('ELECTRICITY_BILL',
                               'Electricity Bill',
                               '',
                               'OTHER',
                               True,
                               80),
                              ('BANK_DETAILS', 'Bank Details', '', 'BANKING', True, 90),
                              ('UDYAM_CERTIFICATE',
                               'Udyam Registration Certificate',
                               '',
                               'REGISTRATION',
                               True,
                               100),
                              # Mudra Phase 1: architecture-approved later-stage
                              # documents. Marked non-mandatory so they do not
                              # block generic completion of every Mudra file up
                              # front; stage-specific enforcement belongs to
                              # later phases.
                              ('CIBIL_REPORT',
                               'CIBIL / Credit Report',
                               '',
                               'BANKING',
                               False,
                               110),
                              ('SANCTION_LETTER',
                               'Sanction Letter',
                               '',
                               'BANKING',
                               False,
                               120),
                              ('SANCTION_CONDITIONS_EVIDENCE',
                               'Sanction Conditions Evidence',
                               '',
                               'BANKING',
                               False,
                               130),
                              ('DISBURSEMENT_EVIDENCE',
                               'Disbursement Evidence',
                               '',
                               'BANKING',
                               False,
                               140))},
 'CAR_LOAN': {'name': 'Car Loan',
              'description': 'Car loan documentation and processing.',
              'fields': ({'key': 'requested_loan_amount',
                          'label': 'Requested Loan Amount',
                          'field_type': 'NUMBER',
                          'required': True,
                          'options': [],
                          'display_order': 10},
                         {'key': 'applicant_type',
                          'label': 'Applicant Type',
                          'field_type': 'SELECT',
                          'required': True,
                          'options': ['Individual', 'Joint', 'Business'],
                          'display_order': 20},
                         {'key': 'employment_type',
                          'label': 'Employment Type',
                          'field_type': 'SELECT',
                          'required': True,
                          'options': ['Salaried', 'Self Employed', 'Business', 'Other'],
                          'display_order': 30},
                         {'key': 'vehicle_condition',
                          'label': 'Vehicle Condition',
                          'field_type': 'SELECT',
                          'required': True,
                          'options': ['New', 'Used'],
                          'display_order': 40},
                         {'key': 'vehicle_make_model',
                          'label': 'Vehicle Make / Model',
                          'field_type': 'TEXT',
                          'required': True,
                          'options': [],
                          'display_order': 50},
                         {'key': 'vehicle_price',
                          'label': 'Vehicle / On-Road Price',
                          'field_type': 'NUMBER',
                          'required': True,
                          'options': [],
                          'display_order': 60},
                         {'key': 'preferred_lender',
                          'label': 'Preferred Bank / Lender',
                          'field_type': 'TEXT',
                          'required': False,
                          'options': [],
                          'display_order': 70},
                         {'key': 'existing_monthly_emi',
                          'label': 'Existing Monthly EMI',
                          'field_type': 'NUMBER',
                          'required': False,
                          'options': [],
                          'display_order': 80}),
              'documents': (('AADHAAR_CARD', 'Aadhaar Card', '', 'IDENTITY_KYC', True, 10),
                            ('PAN_CARD', 'PAN Card', '', 'IDENTITY_KYC', True, 20),
                            ('VEHICLE_QUOTATION',
                             'Vehicle Quotation',
                             '',
                             'OTHER',
                             True,
                             30),
                            ('BUSINESS_BANK_6_MONTHS',
                             'Last 6 Months Business Bank Statement',
                             '',
                             'BANKING',
                             True,
                             40),
                            ('GUARANTOR_KYC',
                             'Guarantor KYC',
                             '',
                             'IDENTITY_KYC',
                             True,
                             50),
                            ('ITR_2_YEARS',
                             'Latest 2 Years ITR',
                             '',
                             'INCOME_TAX',
                             True,
                             60),
                            ('SALARY_SLIPS_3_MONTHS',
                             'Last 3 Months Salary Slips (For Salaried Applicants)',
                             '',
                             'OTHER',
                             False,
                             70))},
 'HOME_LOAN': {'name': 'Home Loan',
               'description': 'Home loan documentation and processing.',
               'fields': ({'key': 'requested_loan_amount',
                           'label': 'Requested Loan Amount',
                           'field_type': 'NUMBER',
                           'required': True,
                           'options': [],
                           'display_order': 10},
                          {'key': 'applicant_type',
                           'label': 'Applicant Type',
                           'field_type': 'TEXT',
                           'required': True,
                           'options': [],
                           'display_order': 20},
                          {'key': 'employment_type',
                           'label': 'Employment Type',
                           'field_type': 'TEXT',
                           'required': True,
                           'options': [],
                           'display_order': 30},
                          {'key': 'property_type',
                           'label': 'Property Type',
                           'field_type': 'TEXT',
                           'required': True,
                           'options': [],
                           'display_order': 40},
                          {'key': 'property_location',
                           'label': 'Property Location',
                           'field_type': 'TEXT',
                           'required': True,
                           'options': [],
                           'display_order': 50},
                          {'key': 'preferred_lender',
                           'label': 'Preferred Bank / Lender',
                           'field_type': 'TEXT',
                           'required': False,
                           'options': [],
                           'display_order': 60},
                          {'key': 'existing_monthly_emi',
                           'label': 'Existing Monthly EMI',
                           'field_type': 'NUMBER',
                           'required': False,
                           'options': [],
                           'display_order': 70}),
               'documents': (('AADHAAR_CARD', 'Aadhaar Card', '', 'IDENTITY_KYC', True, 10),
                             ('PAN_CARD', 'PAN Card', '', 'IDENTITY_KYC', True, 20),
                             ('ITR_COMPUTATION_2_YEARS',
                              'ITR with Computation (Last 2 Years)',
                              '',
                              'INCOME_TAX',
                              True,
                              30),
                             ('SALARY_SLIPS_3_MONTHS',
                              'Last 3 Months Salary Slips (For Salaried Applicants)',
                              '',
                              'OTHER',
                              False,
                              40),
                             ('BANK_STATEMENT_6_MONTHS',
                              'Last 6 Months Bank Statement',
                              '',
                              'BANKING',
                              True,
                              50),
                             ('EXISTING_LOAN_STATEMENT',
                              'Existing/Previous Loan Statement',
                              '',
                              'BANKING',
                              True,
                              60),
                             ('UDYAM_GST_BUSINESS',
                              'Udyam/GST Certificate (For Business Applicants)',
                              '',
                              'REGISTRATION',
                              False,
                              70))},
 'LAP_LOAN': {'name': 'Loan Against Property (LAP)',
              'description': 'Loan against property documentation and processing.',
              'fields': (),
              'documents': (('AADHAAR_CARD', 'Aadhaar Card', '', 'IDENTITY_KYC', True, 10),
                            ('PAN_CARD', 'PAN Card', '', 'IDENTITY_KYC', True, 20),
                            ('PASSPORT_PHOTOS_2',
                             'Two Passport Size Photographs',
                             '',
                             'IDENTITY_KYC',
                             True,
                             30),
                            ('BUSINESS_PROOF',
                             'Business Proof (GST/Udyam Registration)',
                             '',
                             'REGISTRATION',
                             True,
                             40),
                            ('BANK_STATEMENTS_2_YEARS',
                             'Last 2 Years Bank Statements',
                             '',
                             'BANKING',
                             True,
                             50),
                            ('PROPERTY_REGISTRY_CHAIN',
                             'Complete Property Registry/Chain Documents',
                             '',
                             'LEGAL',
                             True,
                             60),
                            ('CERTIFICATE_143',
                             '143 Certificate (If Applicable)',
                             '',
                             'LEGAL',
                             False,
                             70))},
 'MSME_LOAN': {'name': 'MSME Loan',
               'description': 'MSME loan documentation and processing.',
               'fields': ({'key': 'requested_loan_amount',
                           'label': 'Requested Loan Amount',
                           'field_type': 'NUMBER',
                           'required': True,
                           'options': [],
                           'display_order': 10},
                          {'key': 'business_name',
                           'label': 'Business Name',
                           'field_type': 'TEXT',
                           'required': True,
                           'options': [],
                           'display_order': 20},
                          {'key': 'business_constitution',
                           'label': 'Business Constitution',
                           'field_type': 'SELECT',
                           'required': True,
                           'options': ['Proprietorship',
                                       'Partnership',
                                       'LLP',
                                       'Private Limited',
                                       'Public Limited',
                                       'Other'],
                           'display_order': 30},
                          {'key': 'business_vintage_years',
                           'label': 'Business Vintage (Years)',
                           'field_type': 'NUMBER',
                           'required': True,
                           'options': [],
                           'display_order': 40},
                          {'key': 'annual_turnover',
                           'label': 'Approximate Annual Turnover',
                           'field_type': 'NUMBER',
                           'required': True,
                           'options': [],
                           'display_order': 50},
                          {'key': 'loan_purpose',
                           'label': 'Loan Purpose',
                           'field_type': 'LONG_TEXT',
                           'required': True,
                           'options': [],
                           'display_order': 60},
                          {'key': 'preferred_lender',
                           'label': 'Preferred Bank / Lender',
                           'field_type': 'TEXT',
                           'required': False,
                           'options': [],
                           'display_order': 70},
                          {'key': 'existing_business_loans',
                           'label': 'Existing Business Loan / EMI Details',
                           'field_type': 'LONG_TEXT',
                           'required': False,
                           'options': [],
                           'display_order': 80}),
               'documents': (('PAN_CARD', 'PAN Card', '', 'IDENTITY_KYC', True, 10),
                             ('AADHAAR_CARD', 'Aadhaar Card', '', 'IDENTITY_KYC', True, 20),
                             ('UDYAM_GST_CERTIFICATE',
                              'Udyam/GST Certificate',
                              '',
                              'REGISTRATION',
                              True,
                              30),
                             ('PASSPORT_PHOTOS_2',
                              'Two Passport Size Photographs',
                              '',
                              'IDENTITY_KYC',
                              True,
                              40),
                             ('BANK_STATEMENTS',
                              'Bank Statements',
                              '',
                              'BANKING',
                              True,
                              50),
                             ('DOMICILE_CERTIFICATE',
                              'Domicile Certificate',
                              '',
                              'OTHER',
                              True,
                              60),
                             ('RESIDENTIAL_ELECTRICITY_BILL',
                              'Residential Electricity Bill',
                              '',
                              'OTHER',
                              True,
                              70))},
 'LOAN_TAKE_OVER': {'name': 'Loan Take Over',
                    'description': 'Existing loan take-over documentation and processing.',
                    'fields': (),
                    'documents': (('PAN_CARD', 'PAN Card', '', 'IDENTITY_KYC', True, 10),
                                  ('AADHAAR_CARD',
                                   'Aadhaar Card',
                                   '',
                                   'IDENTITY_KYC',
                                   True,
                                   20),
                                  ('UDYAM_GST_CERTIFICATE',
                                   'Udyam/GST Certificate',
                                   '',
                                   'REGISTRATION',
                                   True,
                                   30),
                                  ('PASSPORT_PHOTOS_2',
                                   'Two Passport Size Photographs',
                                   '',
                                   'IDENTITY_KYC',
                                   True,
                                   40),
                                  ('BANK_STATEMENTS',
                                   'Bank Statements',
                                   '',
                                   'BANKING',
                                   True,
                                   50),
                                  ('DOMICILE_CERTIFICATE',
                                   'Domicile Certificate',
                                   '',
                                   'OTHER',
                                   True,
                                   60),
                                  ('RESIDENTIAL_ELECTRICITY_BILL',
                                   'Residential Electricity Bill',
                                   '',
                                   'OTHER',
                                   True,
                                   70))},
 'OD_LIMIT': {'name': 'OD (Overdraft) Limit',
              'description': 'Overdraft limit documentation and processing.',
              'fields': (),
              'documents': (('PAN_CARD', 'PAN Card', '', 'IDENTITY_KYC', True, 10),
                            ('AADHAAR_CARD', 'Aadhaar Card', '', 'IDENTITY_KYC', True, 20),
                            ('UDYAM_GST_CERTIFICATE',
                             'Udyam/GST Certificate',
                             '',
                             'REGISTRATION',
                             True,
                             30),
                            ('PASSPORT_PHOTOS_2',
                             'Two Passport Size Photographs',
                             '',
                             'IDENTITY_KYC',
                             True,
                             40),
                            ('BANK_STATEMENTS', 'Bank Statements', '', 'BANKING', True, 50),
                            ('DOMICILE_CERTIFICATE',
                             'Domicile Certificate',
                             '',
                             'OTHER',
                             True,
                             60),
                            ('RESIDENTIAL_ELECTRICITY_BILL',
                             'Residential Electricity Bill',
                             '',
                             'OTHER',
                             True,
                             70),
                            ('ITR_COMPUTATION_2_YEARS',
                             'ITR with Computation (Last 2 Years)',
                             '',
                             'INCOME_TAX',
                             True,
                             80))},
 'COMMERCIAL_LOAN': {'name': 'Commercial Loan',
                     'description': 'Commercial loan documentation and processing.',
                     'fields': (),
                     'documents': (('PAN_CARD', 'PAN Card', '', 'IDENTITY_KYC', True, 10),
                                   ('AADHAAR_CARD',
                                    'Aadhaar Card',
                                    '',
                                    'IDENTITY_KYC',
                                    True,
                                    20),
                                   ('UDYAM_GST_CERTIFICATE',
                                    'Udyam/GST Certificate',
                                    '',
                                    'REGISTRATION',
                                    True,
                                    30),
                                   ('PROJECT_REPORT',
                                    'Project Report',
                                    '',
                                    'OTHER',
                                    True,
                                    40),
                                   ('QUOTATION', 'Quotation', '', 'OTHER', True, 50),
                                   ('BANK_STATEMENT_6_MONTHS',
                                    'Last 6 Months Bank Statement',
                                    '',
                                    'BANKING',
                                    True,
                                    60),
                                   ('GUARANTOR_KYC',
                                    'Guarantor KYC',
                                    '',
                                    'IDENTITY_KYC',
                                    True,
                                    70),
                                   ('DRIVING_LICENSE',
                                    'Driving License',
                                    '',
                                    'IDENTITY_KYC',
                                    True,
                                    80))}}

APPROVED_SERVICE_CODES = frozenset(SERVICES)


def _update_audited(instance, values, principal_id):
    changed = []

    for field, value in values.items():
        if getattr(instance, field) != value:
            setattr(instance, field, value)
            changed.append(field)

    if not changed:
        return

    instance.updated_by = principal_id
    changed.extend(
        [
            "updated_by",
            "updated_at",
        ]
    )

    instance.save(update_fields=changed)


def _seed_service(
    *,
    tenant_id,
    principal_id,
    domain,
    code,
    definition,
):
    service, service_created = Service.objects.get_or_create(
        tenant_id=tenant_id,
        domain_id=domain.id,
        code=code,
        defaults={
            "created_by": principal_id,
            "updated_by": principal_id,
            "name": definition["name"],
            "description": definition["description"],
            "status": CatalogueStatus.ACTIVE,
        },
    )

    _update_audited(
        service,
        {
            "name": definition["name"],
            "description": definition["description"],
            "status": CatalogueStatus.ACTIVE,
        },
        principal_id,
    )

    field_created = 0
    field_existing = 0

    expected_keys = set()

    for field_definition in definition["fields"]:
        expected_keys.add(field_definition["key"])

        business_defaults = {
            "label": field_definition["label"],
            "field_type": field_definition["field_type"],
            "help_text": "",
            "placeholder": "",
            "required": field_definition["required"],
            "options": field_definition["options"],
            "display_order": field_definition["display_order"],
            "is_active": True,
        }

        field, created = (
            ServiceOperationalField.objects.update_or_create(
                tenant_id=tenant_id,
                service_id=service.id,
                key=field_definition["key"],
                defaults={
                    **business_defaults,
                    "updated_by": principal_id,
                },
                create_defaults={
                    **business_defaults,
                    "created_by": principal_id,
                    "updated_by": principal_id,
                },
            )
        )

        if created:
            field_created += 1
        else:
            field_existing += 1

    # Preserve historical rows but deactivate obsolete configured fields.
    obsolete_fields = ServiceOperationalField.objects.filter(
        tenant_id=tenant_id,
        service_id=service.id,
        is_active=True,
    ).exclude(
        key__in=expected_keys,
    )

    for field in obsolete_fields:
        field.is_active = False
        field.updated_by = principal_id
        field.save(
            update_fields=[
                "is_active",
                "updated_by",
                "updated_at",
            ]
        )

    # Mudra Phase 1: EXPLICITLY MANAGED CONFIGURATION contract.
    # ServiceProcessStep rows are synchronized ONLY for a service definition
    # that explicitly declares ownership via a "process_steps" key. A service
    # WITHOUT that key is UNMANAGED here: this seed must not query, create,
    # update, deactivate, or reorder its ServiceProcessStep rows in any way.
    # This guard makes cross-service process-step deactivation impossible
    # (an unmanaged service never reaches the reconciliation query, so an empty
    # expected-set can never deactivate another service's active steps).
    # Idempotent and service-scoped: keyed on (tenant_id, service_id, code).
    # No runtime WorkProcessState is created here.
    process_step_created = 0
    process_step_existing = 0
    process_step_managed = "process_steps" in definition

    if process_step_managed:
        expected_step_codes = set()

        for (
            step_code,
            step_name,
            step_display_order,
        ) in definition["process_steps"]:
            expected_step_codes.add(step_code)

            step_business_defaults = {
                "name": step_name,
                "description": "",
                "display_order": step_display_order,
                "is_active": True,
            }

            _step, step_created = (
                ServiceProcessStep.objects.update_or_create(
                    tenant_id=tenant_id,
                    service_id=service.id,
                    code=step_code,
                    defaults={
                        **step_business_defaults,
                        "updated_by": principal_id,
                    },
                    create_defaults={
                        **step_business_defaults,
                        "created_by": principal_id,
                        "updated_by": principal_id,
                    },
                )
            )

            if step_created:
                process_step_created += 1
            else:
                process_step_existing += 1

        # Preserve historical rows but deactivate obsolete MUDRA-OWNED steps.
        # Scoped to this service AND reached only for a managed service, so it
        # can never affect another service. Guarded against an empty expected
        # set as an extra safety net: with no expected codes we still only
        # reach here for a service that declared an (empty) process_steps
        # contract, and we intentionally skip mass-deactivation in that case.
        if expected_step_codes:
            obsolete_steps = ServiceProcessStep.objects.filter(
                tenant_id=tenant_id,
                service_id=service.id,
                is_active=True,
            ).exclude(
                code__in=expected_step_codes,
            )

            for step in obsolete_steps:
                step.is_active = False
                step.updated_by = principal_id
                step.save(
                    update_fields=[
                        "is_active",
                        "updated_by",
                        "updated_at",
                    ]
                )

    requirement_set, set_created = (
        ServiceDocumentRequirementSet.objects.get_or_create(
            tenant_id=tenant_id,
            service_id=service.id,
            version_number=1,
            defaults={
                "created_by": principal_id,
                "updated_by": principal_id,
                "name": (
                    f"{definition['name']} Document Checklist"
                ),
                "status": "ACTIVE",
                "description": (
                    f"Initial Vridhi {definition['name']} "
                    "document checklist."
                ),
            },
        )
    )

    _update_audited(
        requirement_set,
        {
            "name": (
                f"{definition['name']} Document Checklist"
            ),
            "status": "ACTIVE",
            "description": (
                f"Initial Vridhi {definition['name']} "
                "document checklist."
            ),
        },
        principal_id,
    )

    requirement_created = 0
    requirement_existing = 0
    expected_codes = set()

    for (
        req_code,
        name,
        description,
        category,
        mandatory,
        display_order,
    ) in definition["documents"]:

        expected_codes.add(req_code)

        business_defaults = {
            "service_id": service.id,
            "name": name,
            "description": description,
            "category": category,
            "mandatory": mandatory,
            "display_order": display_order,
            "is_active": True,
        }

        requirement, created = (
            ServiceDocumentRequirement.objects.update_or_create(
                tenant_id=tenant_id,
                requirement_set_id=requirement_set.id,
                code=req_code,
                defaults={
                    **business_defaults,
                    "updated_by": principal_id,
                },
                create_defaults={
                    **business_defaults,
                    "created_by": principal_id,
                    "updated_by": principal_id,
                },
            )
        )

        if created:
            requirement_created += 1
        else:
            requirement_existing += 1

    obsolete_requirements = (
        ServiceDocumentRequirement.objects.filter(
            tenant_id=tenant_id,
            requirement_set_id=requirement_set.id,
            is_active=True,
        ).exclude(
            code__in=expected_codes,
        )
    )

    for requirement in obsolete_requirements:
        requirement.is_active = False
        requirement.updated_by = principal_id
        requirement.save(
            update_fields=[
                "is_active",
                "updated_by",
                "updated_at",
            ]
        )

    return {
        "service": service,
        "service_created": service_created,
        "field_created": field_created,
        "field_existing": field_existing,
        "process_step_created": process_step_created,
        "process_step_existing": process_step_existing,
        "set_created": set_created,
        "requirement_created": requirement_created,
        "requirement_existing": requirement_existing,
    }


class Command(BaseCommand):
    help = (
        "Seed the company-approved Vridhi Loans catalogue "
        "with ten loan services and their document requirements."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            required=True,
            help="Tenant UUID for Vridhi Consultants.",
        )

        parser.add_argument(
            "--principal-id",
            required=True,
            help=(
                "Principal UUID recorded in catalogue "
                "audit ownership fields."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            tenant_id = UUID(options["tenant_id"])
        except (TypeError, ValueError) as exc:
            raise CommandError(
                "tenant-id must be a valid UUID."
            ) from exc

        try:
            principal_id = UUID(options["principal_id"])
        except (TypeError, ValueError) as exc:
            raise CommandError(
                "principal-id must be a valid UUID."
            ) from exc

        # Keep the already-certified Home Loan configuration canonical.
        call_command(
            "seed_vridhi_home_loan",
            tenant_id=str(tenant_id),
            principal_id=str(principal_id),
            verbosity=0,
        )

        loans = Vertical.objects.get(
            tenant_id=tenant_id,
            code="LOANS",
        )

        domain = Domain.objects.get(
            tenant_id=tenant_id,
            vertical_id=loans.id,
            code="LOAN_SERVICES",
        )

        results = {}

        for code, definition in SERVICES.items():
            results[code] = _seed_service(
                tenant_id=tenant_id,
                principal_id=principal_id,
                domain=domain,
                code=code,
                definition=definition,
            )

        # The company list is authoritative for this domain.
        # Preserve historical Service rows but stop exposing
        # obsolete loan services in new work creation.
        obsolete_services = (
            Service.objects.filter(
                tenant_id=tenant_id,
                domain_id=domain.id,
                status=CatalogueStatus.ACTIVE,
            )
            .exclude(code__in=APPROVED_SERVICE_CODES)
        )

        for obsolete in obsolete_services:
            obsolete.status = CatalogueStatus.INACTIVE
            obsolete.updated_by = principal_id
            obsolete.save(
                update_fields=[
                    "status",
                    "updated_by",
                    "updated_at",
                ]
            )

        active_codes = set(
            Service.objects.filter(
                tenant_id=tenant_id,
                domain_id=domain.id,
                status=CatalogueStatus.ACTIVE,
            ).values_list(
                "code",
                flat=True,
            )
        )

        if active_codes != set(APPROVED_SERVICE_CODES):
            raise CommandError(
                "Active Loans catalogue does not exactly match "
                "the company-approved service list. "
                f"Observed: {sorted(active_codes)}"
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "VRIDHI_LOANS_SEED=PASS"
            )
        )

        self.stdout.write(
            "Hierarchy: Loans -> Loan Services"
        )

        self.stdout.write(
            "Services: 10 company-approved loan services"
        )

        for code, result in results.items():
            self.stdout.write(
                (
                    f"{code}: "
                    f"service_created="
                    f"{result['service_created']}, "
                    f"fields_created="
                    f"{result['field_created']}, "
                    f"fields_existing="
                    f"{result['field_existing']}, "
                    f"requirements_created="
                    f"{result['requirement_created']}, "
                    f"requirements_existing="
                    f"{result['requirement_existing']}"
                )
            )
