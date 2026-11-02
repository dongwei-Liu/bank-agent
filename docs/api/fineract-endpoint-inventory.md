# Fineract 源码接口索引（生成快照）

> 生成日期：2026-10-09；源码提交：`b56917ebd5253e8b69e865b75387bf3e9a2e0f99`。
> 扫描 `*/src/main/java/**/*.java` 中具有类级 `@Path`（含人工核对常量） 的 JAX-RS 资源，共 169 个资源类、967 个 HTTP 方法声明。
> 本表是源码声明索引，不是运行镜像的 OpenAPI，也不代表全部已启用。排除测试模块、Swagger DTO、生成客户端；同一路径下不同 command 不逐个计数。
> 不包含 Spring/Actuator 自动端点；Spring `/login` 为登录页面；测试模块 `/test/dummy` 不属于业务接口。
> 路径包含 `/v1`、`/v2` 或内部前缀；常规完整地址为 `https://localhost:8443/fineract-provider/api` 加表中路径。内部端点不可公开代理。
> 封装优先级与命令细节见 [项目封装设计](fineract-python-api-design.md)。

## 资源目录

| 资源 | 路径 | HTTP 声明数 |
| --- | --- | --- |
| AccrualAccountingApiResource | `/v1/runaccruals` | 1 |
| GLClosuresApiResource | `/v1/glclosures` | 5 |
| FinancialActivityAccountsApiResource | `/v1/financialactivityaccounts` | 6 |
| GLAccountsApiResource | `/v1/glaccounts` | 8 |
| ProvisioningEntriesApiResource | `/v1/provisioningentries` | 5 |
| AccountingRuleApiResource | `/v1/accountingrules` | 6 |
| TellerApiResource | `/v1/tellers` | 16 |
| ChargesApiResource | `/v1/charges` | 6 |
| BatchApiResource | `/v1/batches` | 1 |
| BusinessDateApiResource | `/v1/businessdate` | 3 |
| CacheApiResource | `/v1/caches` | 2 |
| ExternalEventConfigurationApiResource | `/v1/externalevents/configuration` | 2 |
| InternalExternalEventsApiResource | `/v1/internal/externalevents` | 2 |
| CurrenciesApiResource | `/v1/currencies` | 2 |
| PaymentTypeApiResource | `/v1/paymenttypes` | 5 |
| DocumentApiResource | `/v1/{entityType}/{entityId}/documents` | 6 |
| ImagesApiResource | `/v1/{entityType}/{entityId}/images` | 6 |
| ExternalAssetOwnerLoanProductAttributesApiResource | `/v1/external-asset-owners/loan-product` | 5 |
| ExternalAssetOwnersApiResource | `/v1/external-asset-owners` | 11 |
| DelinquencyApiResource | `/v1/delinquency` | 11 |
| LoanInterestPauseApiResource | `/v1/loans` | 8 |
| LoanScheduleApiResource | `/v1/loans/{loanId}/schedule` | 1 |
| RescheduleLoansApiResource | `/v1/rescheduleloans` | 5 |
| LoanProductsDetailsApiResource | `/v1/loanproducts` | 1 |
| LoanOriginatorApiResource | `/v1/loan-originators` | 9 |
| LoanOriginatorsApiResource | `/v1/loans` | 10 |
| WorkingCapitalLoanOriginatorsApiResource | `/v1/working-capital-loans` | 10 |
| LoanBuyDownFeeApiResource | `/v1/loans` | 6 |
| LoanCapitalizedIncomeApiResource | `/v1/loans` | 8 |
| InternalProgressiveLoanApiResource | `v1/internal/loan/progressive` | 3 |
| JournalEntriesApiResource | `/v1/journalentries` | 8 |
| AdHocApiResource | `/v1/adhocquery` | 6 |
| ConfigureBusinessStepApiResource | `/v1/jobs` | 4 |
| InternalCOBApiResource | `/v1/internal/cob` | 3 |
| InternalLoanAccountLockApiResource | `/v1/internal/loans` | 1 |
| LoanAccountLockApiResource | `/v1/loans` | 1 |
| LoanCOBCatchUpApiResource | `/v1/loans` | 3 |
| WorkingCapitalLoanCOBCatchUpApiResource | `/v1/working-capital-loans` | 3 |
| AuditsApiResource | `/v1/audits` | 3 |
| MakercheckersApiResource | `/v1/makercheckers` | 4 |
| AuditsV2ApiResource | `/v2/audits` | 1 |
| AccountNumberFormatsApiResource | `/v1/accountnumberformats` | 6 |
| BulkImportApiResource | `/v1/imports` | 3 |
| EmailApiResource | `/v1/email` | 9 |
| EmailCampaignApiResource | `/v1/email/campaign` | 9 |
| EmailConfigurationApiResource | `/v1/email/configuration` | 2 |
| SmsCampaignApiResource | `/v1/smscampaigns` | 8 |
| CodeValuesApiResource | `/v1/codes` | 10 |
| CodesApiResource | `/v1/codes` | 6 |
| ExternalServicesConfigurationApiResource | `/v1/externalservice` | 2 |
| GlobalConfigurationApiResource | `/v1/configurations` | 5 |
| InternalConfigurationsApiResource | `/v1/internal/configurations` | 1 |
| CreditBureauConfigurationApiResource | `/v1/CreditBureauConfiguration` | 12 |
| CreditBureauIntegrationApiResource | `/v1/creditBureauIntegration` | 5 |
| DatatablesApiResource | `/v1/datatables` | 16 |
| EntityDatatableChecksApiResource | `/v1/entityDatatableChecks` | 4 |
| ReportsApiResource | `/v1/reports` | 6 |
| RunreportsApiResource | `/v1/runreports` | 2 |
| FineractEntityApiResource | `/v1/entitytoentitymapping` | 6 |
| HookApiResource | `/v1/hooks` | 6 |
| InstanceModeApiResource | `/v1/instance-mode` | 1 |
| InlineJobApiResource | `/v1/jobs` | 1 |
| SchedulerApiResource | `/v1/scheduler` | 2 |
| SchedulerJobApiResource | `/v1/jobs` | 9 |
| ReportMailingJobApiResource | `/v1/reportmailingjobs` | 6 |
| ReportMailingJobRunHistoryApiResource | `/v1/reportmailingjobrunhistory` | 1 |
| SmsApiResource | `/v1/sms` | 6 |
| LikelihoodApiResource | `/v1/likelihood` | 3 |
| PovertyLineApiResource | `/v1/povertyLine` | 2 |
| SurveyApiResource | `/v1/survey` | 7 |
| InteropApiResource | `/v1/interoperation` | 19 |
| NotificationApiResource | `/v1/notifications` | 2 |
| HolidaysApiResource | `/v1/holidays` | 7 |
| OfficeTransactionsApiResource | `/v1/officetransactions` | 4 |
| OfficesApiResource | `/v1/offices` | 9 |
| ProvisioningCategoryApiResource | `/v1/provisioningcategory` | 4 |
| ProvisioningCriteriaApiResource | `/v1/provisioningcriteria` | 6 |
| StaffApiResource | `/v1/staff` | 6 |
| WorkingDaysApiResource | `/v1/workingdays` | 3 |
| AccountTransfersApiResource | `/v1/accounttransfers` | 7 |
| StandingInstructionApiResource | `/v1/standinginstructions` | 5 |
| StandingInstructionHistoryApiResource | `/v1/standinginstructionrunhistory` | 1 |
| AccountsApiResource | `/v1/accounts/{type}` | 8 |
| EntityFieldConfigurationApiResource | `/v1/fieldconfiguration/{entity}` | 1 |
| CalendarsApiResource | `/v1/{entityType}/{entityId}/calendars` | 6 |
| ClientAddressApiResource | `/v1/client` | 4 |
| ClientChargesApiResource | `/v1/clients/{clientId}/charges` | 6 |
| ClientFamilyMembersApiResource | `/v1/clients/{clientId}/familymembers` | 6 |
| ClientIdentifiersApiResource | `/v1/clients/{clientId}/identifiers` | 6 |
| ClientTransactionsApiResource | `/v1/clients` | 10 |
| ClientsApiResource | `/v1/clients` | 19 |
| InternalClientInformationApiResource | `/v1/internal/client` | 1 |
| ClientSearchV2ApiResource | `/v2/clients` | 1 |
| CollateralsApiResource | `/v1/loans/{loanId}/collaterals` | 6 |
| ClientCollateralManagementApiResource | `/v1/clients/{clientId}/collaterals` | 6 |
| CollateralManagementApiResource | `/v1/collateral-management` | 6 |
| LoanCollateralManagementApiResource | `/v1/loan-collateral-management` | 2 |
| CollectionSheetApiResource | `/v1/collectionsheet` | 1 |
| FundsApiResource | `/v1/funds` | 4 |
| CentersApiResource | `/v1/centers` | 10 |
| GroupsApiResource | `/v1/groups` | 13 |
| GroupsLevelApiResource | `/v1/grouplevels` | 1 |
| CentersV2ApiResource | `/v2/centers` | 1 |
| GroupsV2ApiResource | `/v2/groups` | 1 |
| InterestRateChartSlabsApiResource | `/v1/interestratecharts/{chartId}/chartslabs` | 6 |
| InterestRateChartsApiResource | `/v1/interestratecharts` | 6 |
| BulkLoansApiResource | `/v1/loans/loanreassignment` | 2 |
| InternalLoanInformationApiResource | `/v1/internal/loan` | 5 |
| LoanChargesApiResource | `/v1/loans` | 22 |
| LoanDisbursementDetailApiResource | `/v1/loans/{loanId}/disbursements` | 3 |
| LoanTransactionsApiResource | `/v1/loans` | 22 |
| LoansApiResource | `/v1/loans` | 31 |
| LoansPointInTimeApiResource | `/v1/loans/at-date` | 4 |
| GuarantorsApiResource | `/v1/loans/{loanId}/guarantors` | 9 |
| LoanProductsApiResource | `/v1/loanproducts` | 7 |
| ProductMixApiResource | `/v1/loanproducts/{productId}/productmix` | 4 |
| MeetingsApiResource | `/v1/{entityType}/{entityId}/meetings` | 7 |
| NotesApiResource | `/v1/{resourceType:.+}/{resourceId}/notes` | 5 |
| ProductsApiResource | `/v1/products/{type}` | 6 |
| RateApiResource | `/v1/rates` | 4 |
| RepaymentWithPostDatedChecksApiResource | `/v1/loans/{loanId}/postdatedchecks` | 4 |
| DepositAccountOnHoldFundTransactionsApiResource | `/v1/savingsaccounts/{savingsId}/onholdtransactions` | 1 |
| FixedDepositAccountTransactionsApiResource | `/v1/fixeddepositaccounts/{fixedDepositAccountId}/transactions` | 5 |
| FixedDepositAccountsApiResource | `/v1/fixeddepositaccounts` | 13 |
| FixedDepositProductsApiResource | `/v1/fixeddepositproducts` | 6 |
| InternalSavingsAccountInformationApiResource | `/v1/internal/savingsaccounts` | 1 |
| RecurringDepositAccountTransactionsApiResource | `/v1/recurringdepositaccounts/{recurringDepositAccountId}/transactions` | 4 |
| RecurringDepositAccountsApiResource | `/v1/recurringdepositaccounts` | 12 |
| RecurringDepositProductsApiResource | `/v1/recurringdepositproducts` | 6 |
| SavingsAccountChargesApiResource | `/v1/savingsaccounts/{savingsAccountId}/charges` | 7 |
| SavingsAccountTransactionsApiResource | `/v1/savingsaccounts` | 16 |
| SavingsAccountsApiResource | `/v1/savingsaccounts` | 18 |
| SavingsProductsApiResource | `/v1/savingsproducts` | 6 |
| FixedDepositAccountsV2ApiResource | `/v2/fixeddepositaccounts` | 1 |
| RecurringDepositAccountsV2ApiResource | `/v2/recurringdepositaccounts` | 1 |
| SearchApiResource | `/v1/search` | 3 |
| ShareDividendApiResource | `/v1/shareproduct/{productId}/dividend` | 5 |
| LookupTableApiResource | `/v1/surveys/{surveyId}/lookuptables` | 3 |
| ScorecardApiResource | `/v1/surveys/scorecards` | 4 |
| SpmApiResource | `/v1/surveys` | 5 |
| TemplatesApiResource | `/v1/templates` | 8 |
| ForgotPasswordApiResource | `/v1/password` | 1 |
| PasswordPreferencesApiResource | `/v1/passwordpreferences` | 3 |
| PermissionsApiResource | `/v1/permissions` | 2 |
| RolesApiResource | `/v1/roles` | 8 |
| UsersApiResource | `/v1/users` | 9 |
| FloatingRatesApiResource | `/v1/floatingrates` | 4 |
| AuthenticationApiResource | `/v1/authentication` | 1 |
| TenantOidcConfigApiResource | `/v1/tenants/{tenantId}/oidc-config` | 4 |
| TwoFactorApiResource | `/v1/twofactor` | 4 |
| TwoFactorConfigurationApiResource | `/v1/twofactor/configure` | 2 |
| UserDetailsApiResource | `/v1/userdetails` | 1 |
| TaxComponentApiResource | `/v1/taxes/component` | 5 |
| TaxGroupApiResource | `/v1/taxes/group` | 5 |
| InternalWorkingCapitalAccountLockApiResource | `/v1/internal/working-capital-loans` | 1 |
| InternalWorkingCapitalLoanCOBApiResource | `/v1/internal/working-capital-loans` | 2 |
| InternalWorkingCapitalLoanApiResource | `v1/internal/working-capital-loans` | 3 |
| WorkingCapitalLoanAmortizationScheduleApiResource | `/v1/working-capital-loans` | 1 |
| WorkingCapitalLoanApiResource | `/v1/working-capital-loans` | 21 |
| WorkingCapitalLoanBreachActionApiResource | `/v1/working-capital-loans` | 4 |
| WorkingCapitalLoanBreachScheduleApiResource | `/v1/working-capital-loans/{loanId}/breach-schedule` | 1 |
| WorkingCapitalLoanChargesApiResource | `/v1/working-capital-loans` | 14 |
| WorkingCapitalLoanDelinquencyActionApiResource | `/v1/working-capital-loans` | 4 |
| WorkingCapitalLoanDelinquencyRangeScheduleApiResource | `/v1/working-capital-loans/{loanId}/delinquency-range-schedule` | 1 |
| WorkingCapitalLoanNearBreachActionApiResource | `/v1/working-capital-loans` | 4 |
| WorkingCapitalLoanTransactionsApiResource | `/v1/working-capital-loans` | 15 |
| WorkingCapitalBreachApiResource | `/v1/working-capital/breach` | 6 |
| WorkingCapitalNearBreachApiResource | `/v1/working-capital/near-breach` | 5 |
| WorkingCapitalLoanProductApiResource | `/v1/working-capital-loan-products` | 9 |

## AccrualAccountingApiResource

源码：[platform/fineract/fineract-accounting/src/main/java/org/apache/fineract/accounting/accrual/api/AccrualAccountingApiResource.java](../../platform/fineract/fineract-accounting/src/main/java/org/apache/fineract/accounting/accrual/api/AccrualAccountingApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/runaccruals` | `executePeriodicAccrualAccounting` | Executes Periodic Accrual Accounting |

## GLClosuresApiResource

源码：[platform/fineract/fineract-accounting/src/main/java/org/apache/fineract/accounting/closure/api/GLClosuresApiResource.java](../../platform/fineract/fineract-accounting/src/main/java/org/apache/fineract/accounting/closure/api/GLClosuresApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/glclosures` | `retrieveAllGLClosures` | List Accounting closures |
| GET | `/v1/glclosures/{glClosureId}` | `retrieveOneGLClosure` | Retrieve an Accounting Closure |
| POST | `/v1/glclosures` | `createGLClosure` | Create an Accounting Closure |
| PUT | `/v1/glclosures/{glClosureId}` | `updateGLClosure` | Update an Accounting closure |
| DELETE | `/v1/glclosures/{glClosureId}` | `deleteGLClosure` | Delete an accounting closure |

## FinancialActivityAccountsApiResource

源码：[platform/fineract/fineract-accounting/src/main/java/org/apache/fineract/accounting/financialactivityaccount/api/FinancialActivityAccountsApiResource.java](../../platform/fineract/fineract-accounting/src/main/java/org/apache/fineract/accounting/financialactivityaccount/api/FinancialActivityAccountsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/financialactivityaccounts/template` | `retrieveTemplate` |  |
| GET | `/v1/financialactivityaccounts` | `retrieveAll` | List Financial Activities to Accounts Mappings |
| GET | `/v1/financialactivityaccounts/{mappingId}` | `retreive` | Retrieve a Financial Activity to Account Mapping  |
| POST | `/v1/financialactivityaccounts` | `createGLAccountMappingFinancialActivityAccount` | Create a new Financial Activity to Accounts Mapping |
| PUT | `/v1/financialactivityaccounts/{mappingId}` | `updateGLAccountMappingFinancialActivityAccount` | Update a Financial Activity to Account Mapping |
| DELETE | `/v1/financialactivityaccounts/{mappingId}` | `deleteGLAccountMappingFinancialActivityAccount` | Delete a Financial Activity to Account Mapping |

## GLAccountsApiResource

源码：[platform/fineract/fineract-accounting/src/main/java/org/apache/fineract/accounting/glaccount/api/GLAccountsApiResource.java](../../platform/fineract/fineract-accounting/src/main/java/org/apache/fineract/accounting/glaccount/api/GLAccountsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/glaccounts/template` | `retrieveNewAccountDetails` |  |
| GET | `/v1/glaccounts` | `retrieveAllAccounts` |  |
| GET | `/v1/glaccounts/{glAccountId}` | `retreiveAccount` |  |
| POST | `/v1/glaccounts` | `createGLAccount` |  |
| PUT | `/v1/glaccounts/{glAccountId}` | `updateGLAccount` |  |
| DELETE | `/v1/glaccounts/{glAccountId}` | `deleteGLAccount` |  |
| GET | `/v1/glaccounts/downloadtemplate` | `getGlAccountsTemplate` |  |
| POST | `/v1/glaccounts/uploadtemplate` | `postGlAccountsTemplate` |  |

## ProvisioningEntriesApiResource

源码：[platform/fineract/fineract-accounting/src/main/java/org/apache/fineract/accounting/provisioning/api/ProvisioningEntriesApiResource.java](../../platform/fineract/fineract-accounting/src/main/java/org/apache/fineract/accounting/provisioning/api/ProvisioningEntriesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/provisioningentries` | `createProvisioningEntries` | Create new Provisioning Entries |
| POST | `/v1/provisioningentries/{entryId}` | `modifyProvisioningEntry` | Recreates Provisioning Entry |
| GET | `/v1/provisioningentries/{entryId}` | `retrieveOneProvisioningEntry` | Retrieves a Provisioning Entry Metadata |
| GET | `/v1/provisioningentries/entries` | `retrieveProvisioningEntriesLoanProducts` | Retrieve Provisioning Entries Loan Products Given a Query |
| GET | `/v1/provisioningentries` | `retrieveAllProvisioningEntries` | List all Provisioning Entries Metadata |

## AccountingRuleApiResource

源码：[platform/fineract/fineract-accounting/src/main/java/org/apache/fineract/accounting/rule/api/AccountingRuleApiResource.java](../../platform/fineract/fineract-accounting/src/main/java/org/apache/fineract/accounting/rule/api/AccountingRuleApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/accountingrules/template` | `retrieveTemplateAccountingRule` | Retrieve Accounting Rule Details Template |
| GET | `/v1/accountingrules` | `retrieveAllAccountingRules` | Retrieve Accounting Rules |
| GET | `/v1/accountingrules/{accountingRuleId}` | `retrieveOneAccountingRule` | Retrieve a Accounting rule |
| POST | `/v1/accountingrules` | `createAccountingRule` | Create/Define a Accounting rule |
| PUT | `/v1/accountingrules/{accountingRuleId}` | `updateAccountingRule` | Update a Accounting Rule |
| DELETE | `/v1/accountingrules/{accountingRuleId}` | `deleteAccountingRule` | Delete a Accounting Rule |

## TellerApiResource

源码：[platform/fineract/fineract-branch/src/main/java/org/apache/fineract/organisation/teller/api/TellerApiResource.java](../../platform/fineract/fineract-branch/src/main/java/org/apache/fineract/organisation/teller/api/TellerApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/tellers` | `retrieveAllTellers` | List all tellers |
| GET | `/v1/tellers/{tellerId}` | `retrieveOneTeller` | Retrieve tellers |
| POST | `/v1/tellers` | `createTeller` | Create teller |
| PUT | `/v1/tellers/{tellerId}` | `updateTeller` | Update teller |
| DELETE | `/v1/tellers/{tellerId}` | `deleteTeller` | Delete teller |
| GET | `/v1/tellers/{tellerId}/cashiers` | `retrieveAllCashiersForTeller` | List Cashiers |
| GET | `/v1/tellers/{tellerId}/cashiers/{cashierId}` | `retrieveOneCashierForTeller` | Retrieve a cashier |
| GET | `/v1/tellers/{tellerId}/cashiers/template` | `retrieveCashierTemplateForTeller` | Find Cashiers |
| POST | `/v1/tellers/{tellerId}/cashiers` | `createCashierForTeller` | Create Cashiers |
| PUT | `/v1/tellers/{tellerId}/cashiers/{cashierId}` | `updateCashierForTeller` | Update Cashier |
| DELETE | `/v1/tellers/{tellerId}/cashiers/{cashierId}` | `deleteCashierForTeller` | Delete Cashier |
| POST | `/v1/tellers/{tellerId}/cashiers/{cashierId}/allocate` | `allocateCashToCashier` | Allocate Cash To Cashier |
| POST | `/v1/tellers/{tellerId}/cashiers/{cashierId}/settle` | `settleCashFromCashier` | Settle Cash From Cashier |
| GET | `/v1/tellers/{tellerId}/cashiers/{cashierId}/transactions` | `retrieveCashierTransactions` | Retrieve Cashier Transactions |
| GET | `/v1/tellers/{tellerId}/cashiers/{cashierId}/summaryandtransactions` | `retrieveCashierTransactionsWithSummary` | Retrieve Transactions With Summary For Cashier |
| GET | `/v1/tellers/{tellerId}/cashiers/{cashierId}/transactions/template` | `retrieveTemplateCashierTransaction` | Retrieve Cashier Transaction Template |

## ChargesApiResource

源码：[platform/fineract/fineract-charge/src/main/java/org/apache/fineract/portfolio/charge/api/ChargesApiResource.java](../../platform/fineract/fineract-charge/src/main/java/org/apache/fineract/portfolio/charge/api/ChargesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/charges` | `retrieveAllCharges` | Retrieve Charges |
| GET | `/v1/charges/{chargeId}` | `retrieveOneCharge` | Retrieve a Charge |
| GET | `/v1/charges/template` | `retrieveTemplateCharge` | Retrieve Charge Template |
| POST | `/v1/charges` | `createCharge` | Create/Define a Charge |
| PUT | `/v1/charges/{chargeId}` | `updateCharge` | Update a Charge |
| DELETE | `/v1/charges/{chargeId}` | `deleteCharge` | Delete a Charge |

## BatchApiResource

源码：[platform/fineract/fineract-core/src/main/java/org/apache/fineract/batch/api/BatchApiResource.java](../../platform/fineract/fineract-core/src/main/java/org/apache/fineract/batch/api/BatchApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/batches` | `handleBatchRequests` | Batch requests in a single transaction |

## BusinessDateApiResource

源码：[platform/fineract/fineract-core/src/main/java/org/apache/fineract/infrastructure/businessdate/api/BusinessDateApiResource.java](../../platform/fineract/fineract-core/src/main/java/org/apache/fineract/infrastructure/businessdate/api/BusinessDateApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/businessdate` | `getBusinessDates` | List all business dates |
| GET | `/v1/businessdate/{type}` | `getBusinessDate` | Retrieve a specific Business date |
| POST | `/v1/businessdate` | `updateBusinessDate` | Update Business Date |

## CacheApiResource

源码：[platform/fineract/fineract-core/src/main/java/org/apache/fineract/infrastructure/cache/api/CacheApiResource.java](../../platform/fineract/fineract-core/src/main/java/org/apache/fineract/infrastructure/cache/api/CacheApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/caches` | `retrieveAll_2` |  |
| PUT | `/v1/caches` | `switchCache` | Switch Cache |

## ExternalEventConfigurationApiResource

源码：[platform/fineract/fineract-core/src/main/java/org/apache/fineract/infrastructure/event/external/api/ExternalEventConfigurationApiResource.java](../../platform/fineract/fineract-core/src/main/java/org/apache/fineract/infrastructure/event/external/api/ExternalEventConfigurationApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/externalevents/configuration` | `getExternalEventConfigurations` | List all external event configurations |
| PUT | `/v1/externalevents/configuration` | `updateExternalEventConfigurations` | Enable/Disable external events posting |

## InternalExternalEventsApiResource

源码：[platform/fineract/fineract-core/src/main/java/org/apache/fineract/infrastructure/event/external/api/InternalExternalEventsApiResource.java](../../platform/fineract/fineract-core/src/main/java/org/apache/fineract/infrastructure/event/external/api/InternalExternalEventsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/internal/externalevents` | `getAllExternalEvents` |  |
| DELETE | `/v1/internal/externalevents` | `deleteAllExternalEvents` |  |

## CurrenciesApiResource

源码：[platform/fineract/fineract-core/src/main/java/org/apache/fineract/organisation/monetary/api/CurrenciesApiResource.java](../../platform/fineract/fineract-core/src/main/java/org/apache/fineract/organisation/monetary/api/CurrenciesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/currencies` | `retrieveCurrencies` | Retrieve Currency Configuration |
| PUT | `/v1/currencies` | `updateCurrencies` | Update Currency Configuration |

## PaymentTypeApiResource

源码：[platform/fineract/fineract-core/src/main/java/org/apache/fineract/portfolio/paymenttype/api/PaymentTypeApiResource.java](../../platform/fineract/fineract-core/src/main/java/org/apache/fineract/portfolio/paymenttype/api/PaymentTypeApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/paymenttypes` | `getAllPaymentTypes` | Retrieve all Payment Types |
| GET | `/v1/paymenttypes/{paymentTypeId}` | `retrieveOnePaymentType` | Retrieve a Payment Type |
| POST | `/v1/paymenttypes` | `createPaymentType` | Create a Payment Type |
| PUT | `/v1/paymenttypes/{paymentTypeId}` | `updatePaymentType` | Update a Payment Type |
| DELETE | `/v1/paymenttypes/{paymentTypeId}` | `deleteCodePaymentType` | Delete a Payment Type |

## DocumentApiResource

源码：[platform/fineract/fineract-document/src/main/java/org/apache/fineract/infrastructure/documentmanagement/api/DocumentApiResource.java](../../platform/fineract/fineract-document/src/main/java/org/apache/fineract/infrastructure/documentmanagement/api/DocumentApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/{entityType}/{entityId}/documents` | `retrieveAllDocuments` | List documents |
| GET | `/v1/{entityType}/{entityId}/documents/{documentId}` | `getDocument` | Retrieve a Document |
| GET | `/v1/{entityType}/{entityId}/documents/{documentId}/attachment` | `downloadFile` | Retrieve Binary File associated with Document |
| POST | `/v1/{entityType}/{entityId}/documents` | `createDocument` | Create a Document |
| PUT | `/v1/{entityType}/{entityId}/documents/{documentId}` | `updateDocument` | Update a Document |
| DELETE | `/v1/{entityType}/{entityId}/documents/{documentId}` | `deleteDocument` | Remove a Document |

## ImagesApiResource

源码：[platform/fineract/fineract-document/src/main/java/org/apache/fineract/infrastructure/documentmanagement/api/ImagesApiResource.java](../../platform/fineract/fineract-document/src/main/java/org/apache/fineract/infrastructure/documentmanagement/api/ImagesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/{entityType}/{entityId}/images` | `retrieveImage` |  |
| POST | `/v1/{entityType}/{entityId}/images` | `createImage` |  |
| POST | `/v1/{entityType}/{entityId}/images` | `createImage` |  |
| PUT | `/v1/{entityType}/{entityId}/images` | `updateImage` |  |
| PUT | `/v1/{entityType}/{entityId}/images` | `updateImage` |  |
| DELETE | `/v1/{entityType}/{entityId}/images` | `deleteImage` |  |

## ExternalAssetOwnerLoanProductAttributesApiResource

源码：[platform/fineract/fineract-investor/src/main/java/org/apache/fineract/investor/api/ExternalAssetOwnerLoanProductAttributesApiResource.java](../../platform/fineract/fineract-investor/src/main/java/org/apache/fineract/investor/api/ExternalAssetOwnerLoanProductAttributesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/external-asset-owners/loan-product/template` | `retrieveTemplateExternalAssetOwnerLoanProductAttributes` | Retrieve External Asset Owner Loan Product Attributes Template |
| POST | `/v1/external-asset-owners/loan-product/{loanProductId}/attributes` | `createExternalAssetOwnerLoanProductAttribute` | Create External Asset Owner Loan Product Attribute |
| GET | `/v1/external-asset-owners/loan-product/{loanProductId}/attributes` | `retrieveAllExternalAssetOwnerLoanProductAttributes` |  |
| PUT | `/v1/external-asset-owners/loan-product/{loanProductId}/attributes/{id}` | `updateExternalAssetOwnerLoanProductAttribute` |  |
| DELETE | `/v1/external-asset-owners/loan-product/{loanProductId}/attributes/{id}` | `deleteExternalAssetOwnerLoanProductAttribute` |  |

## ExternalAssetOwnersApiResource

源码：[platform/fineract/fineract-investor/src/main/java/org/apache/fineract/investor/api/ExternalAssetOwnersApiResource.java](../../platform/fineract/fineract-investor/src/main/java/org/apache/fineract/investor/api/ExternalAssetOwnersApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/external-asset-owners/transfers/loans/{loanId}` | `transferRequestWithLoanId` |  |
| POST | `/v1/external-asset-owners/transfers/loans/external-id/{loanExternalId}` | `transferRequestWithLoanExternalId` |  |
| POST | `/v1/external-asset-owners/transfers/{id}` | `transferRequestWithId` | Transfer external asset |
| POST | `/v1/external-asset-owners/transfers/external-id/{externalId}` | `transferRequestWithIdByExternalId` | Transfer external asset by external ID |
| GET | `/v1/external-asset-owners/transfers` | `getTransfers` |  |
| GET | `/v1/external-asset-owners/transfers/active-transfer` | `getActiveTransfer` |  |
| GET | `/v1/external-asset-owners/transfers/{transferId}/journal-entries` | `getJournalEntriesOfTransfer` |  |
| GET | `/v1/external-asset-owners/owners/external-id/{ownerExternalId}/journal-entries` | `getJournalEntriesOfOwner` |  |
| POST | `/v1/external-asset-owners/search` | `searchInvestorData` | Search External Asset Owner Transfers by text or date ranges to settlement or effective dates |
| POST | `/v1/external-asset-owners` | `createExternalAssetOwner` | Create an External Asset Owner using the External Id |
| GET | `/v1/external-asset-owners` | `retrieveExternalAssetOwners` | Get all External Asset Owner with details |

## DelinquencyApiResource

源码：[platform/fineract/fineract-loan/src/main/java/org/apache/fineract/portfolio/delinquency/api/DelinquencyApiResource.java](../../platform/fineract/fineract-loan/src/main/java/org/apache/fineract/portfolio/delinquency/api/DelinquencyApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/delinquency/ranges` | `getRanges` | List all Delinquency Ranges |
| GET | `/v1/delinquency/ranges/{delinquencyRangeId}` | `getRange` | Retrieve a specific Delinquency Range based on the Id |
| POST | `/v1/delinquency/ranges` | `createRange` | Create Delinquency Range |
| PUT | `/v1/delinquency/ranges/{delinquencyRangeId}` | `updateRange` | Update Delinquency Range based on the Id |
| DELETE | `/v1/delinquency/ranges/{delinquencyRangeId}` | `deleteRange` | Update Delinquency Range based on the Id |
| GET | `/v1/delinquency/buckets/template` | `getBucketTemplate` | Template for Delinquency Buckets |
| GET | `/v1/delinquency/buckets` | `getBuckets` | List all Delinquency Buckets |
| GET | `/v1/delinquency/buckets/{delinquencyBucketId}` | `getBucket` | Retrieve a specific Delinquency Bucket based on the Id |
| POST | `/v1/delinquency/buckets` | `createBucket` | Create Delinquency Bucket |
| PUT | `/v1/delinquency/buckets/{delinquencyBucketId}` | `updateBucket` | Update Delinquency Bucket based on the Id |
| DELETE | `/v1/delinquency/buckets/{delinquencyBucketId}` | `deleteBucket` | Delete Delinquency Bucket based on the Id |

## LoanInterestPauseApiResource

源码：[platform/fineract/fineract-loan/src/main/java/org/apache/fineract/portfolio/interestpauses/api/LoanInterestPauseApiResource.java](../../platform/fineract/fineract-loan/src/main/java/org/apache/fineract/portfolio/interestpauses/api/LoanInterestPauseApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/loans/{loanId}/interest-pauses` | `createLoanInterestPause` | Create a new interest pause period for a loan |
| POST | `/v1/loans/external-id/{loanExternalId}/interest-pauses` | `createLoanInterestPauseByExternalId` | Create a new interest pause for a loan using external ID |
| GET | `/v1/loans/{loanId}/interest-pauses` | `retrieveAllLoanInterestPauses` | Retrieve all interest pause periods for a loan |
| GET | `/v1/loans/external-id/{loanExternalId}/interest-pauses` | `retrieveAllLoanInterestPausesByExternalId` | Retrieve all interest pause periods for a loan using external ID |
| DELETE | `/v1/loans/{loanId}/interest-pauses/{variationId}` | `deleteLoanInterestPause` | Delete an interest pause period |
| DELETE | `/v1/loans/external-id/{loanExternalId}/interest-pauses/{variationId}` | `deleteLoanInterestPauseByExternalId` | Delete an interest pause period by external id |
| PUT | `/v1/loans/{loanId}/interest-pauses/{variationId}` | `updateLoanInterestPause` | Update an interest pause period |
| PUT | `/v1/loans/external-id/{loanExternalId}/interest-pauses/{variationId}` | `updateLoanInterestPauseByExternalId` | Update an interest pause period by external id |

## LoanScheduleApiResource

源码：[platform/fineract/fineract-loan/src/main/java/org/apache/fineract/portfolio/loanaccount/api/LoanScheduleApiResource.java](../../platform/fineract/fineract-loan/src/main/java/org/apache/fineract/portfolio/loanaccount/api/LoanScheduleApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/loans/{loanId}/schedule` | `handleCommandsLoanSchedule` | Calculate loan repayment schedule based on Loan term variations  /  Updates loan repayment schedule based on Loan term variations  /  Updates loan repayment schedule by removing Loan term variations |

## RescheduleLoansApiResource

源码：[platform/fineract/fineract-loan/src/main/java/org/apache/fineract/portfolio/loanaccount/rescheduleloan/api/RescheduleLoansApiResource.java](../../platform/fineract/fineract-loan/src/main/java/org/apache/fineract/portfolio/loanaccount/rescheduleloan/api/RescheduleLoansApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/rescheduleloans/template` | `retrieveAllRescheduleLoanReasons` | Retrieve all reschedule loan reasons |
| GET | `/v1/rescheduleloans/{scheduleId}` | `retrieveOneRescheduleLoan` | Retrieve loan reschedule request by schedule id |
| POST | `/v1/rescheduleloans` | `createRescheduleLoan` | Create loan reschedule request |
| POST | `/v1/rescheduleloans/{scheduleId}` | `updateRescheduleLoan` | Update loan reschedule request |
| GET | `/v1/rescheduleloans` | `retrieveAllRescheduleLoans` | Retrieve all reschedule requests |

## LoanProductsDetailsApiResource

源码：[platform/fineract/fineract-loan/src/main/java/org/apache/fineract/portfolio/loanproduct/api/LoanProductsDetailsApiResource.java](../../platform/fineract/fineract-loan/src/main/java/org/apache/fineract/portfolio/loanproduct/api/LoanProductsDetailsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loanproducts/basic-details` | `retrieveAllLoanProductsDetails` | List Loan Products with basic details |

## LoanOriginatorApiResource

源码：[platform/fineract/fineract-loan-origination/src/main/java/org/apache/fineract/portfolio/loanorigination/api/LoanOriginatorApiResource.java](../../platform/fineract/fineract-loan-origination/src/main/java/org/apache/fineract/portfolio/loanorigination/api/LoanOriginatorApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/loan-originators` | `createLoanOriginator` | Create a new loan originator |
| GET | `/v1/loan-originators` | `retrieveAllLoanOriginators` | List all loan originators |
| GET | `/v1/loan-originators/template` | `retrieveLoanOriginatorTemplate` | Get loan originator template data |
| GET | `/v1/loan-originators/{originatorId}` | `retrieveOneLoanOriginator` | Retrieve a loan originator by ID |
| GET | `/v1/loan-originators/external-id/{externalId}` | `retrieveByExternalId` | Retrieve a loan originator by external ID |
| PUT | `/v1/loan-originators/{originatorId}` | `updateLoanOriginator` | Update a loan originator by ID |
| PUT | `/v1/loan-originators/external-id/{externalId}` | `updateByExternalId` | Update a loan originator by external ID |
| DELETE | `/v1/loan-originators/{originatorId}` | `deleteLoanOriginator` | Delete a loan originator by ID |
| DELETE | `/v1/loan-originators/external-id/{externalId}` | `deleteByExternalId` | Delete a loan originator by external ID |

## LoanOriginatorsApiResource

源码：[platform/fineract/fineract-loan-origination/src/main/java/org/apache/fineract/portfolio/loanorigination/api/LoanOriginatorsApiResource.java](../../platform/fineract/fineract-loan-origination/src/main/java/org/apache/fineract/portfolio/loanorigination/api/LoanOriginatorsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loans/{loanId}/originators` | `retrieveOriginatorsByLoanId` | Retrieve originators for a loan by loan ID |
| GET | `/v1/loans/external-id/{loanExternalId}/originators` | `retrieveOriginatorsByLoanExternalId` | Retrieve originators for a loan by loan external ID |
| POST | `/v1/loans/{loanId}/originators/{originatorId}` | `attachOriginatorToLoan` | Attach originator to loan by IDs |
| POST | `/v1/loans/{loanId}/originators/external-id/{originatorExternalId}` | `attachOriginatorToLoanByOriginatorExternalId` | Attach originator to loan by loan ID and originator external ID |
| POST | `/v1/loans/external-id/{loanExternalId}/originators/{originatorId}` | `attachOriginatorToLoanByLoanExternalId` | Attach originator to loan by loan external ID and originator ID |
| POST | `/v1/loans/external-id/{loanExternalId}/originators/external-id/{originatorExternalId}` | `attachOriginatorToLoanByExternalIds` | Attach originator to loan by external IDs |
| DELETE | `/v1/loans/{loanId}/originators/{originatorId}` | `detachOriginatorFromLoan` | Detach originator from loan by IDs |
| DELETE | `/v1/loans/{loanId}/originators/external-id/{originatorExternalId}` | `detachOriginatorFromLoanByOriginatorExternalId` | Detach originator from loan by loan ID and originator external ID |
| DELETE | `/v1/loans/external-id/{loanExternalId}/originators/{originatorId}` | `detachOriginatorFromLoanByLoanExternalId` | Detach originator from loan by loan external ID and originator ID |
| DELETE | `/v1/loans/external-id/{loanExternalId}/originators/external-id/{originatorExternalId}` | `detachOriginatorFromLoanByExternalIds` | Detach originator from loan by external IDs |

## WorkingCapitalLoanOriginatorsApiResource

源码：[platform/fineract/fineract-loan-origination/src/main/java/org/apache/fineract/portfolio/loanorigination/api/WorkingCapitalLoanOriginatorsApiResource.java](../../platform/fineract/fineract-loan-origination/src/main/java/org/apache/fineract/portfolio/loanorigination/api/WorkingCapitalLoanOriginatorsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/working-capital-loans/{loanId}/originators` | `retrieveOriginatorsByWorkingCapitalLoanId` | Retrieve originators for a working capital loan by loan ID |
| GET | `/v1/working-capital-loans/external-id/{loanExternalId}/originators` | `retrieveOriginatorsByWorkingCapitalLoanExternalId` | Retrieve originators for a working capital loan by loan external ID |
| POST | `/v1/working-capital-loans/{loanId}/originators/{originatorId}` | `attachOriginatorToWorkingCapitalLoan` | Attach originator to working capital loan by IDs |
| POST | `/v1/working-capital-loans/{loanId}/originators/external-id/{originatorExternalId}` | `attachOriginatorToWorkingCapitalLoanByOriginatorExternalId` | Attach originator to working capital loan by loan ID and originator external ID |
| POST | `/v1/working-capital-loans/external-id/{loanExternalId}/originators/{originatorId}` | `attachOriginatorToWorkingCapitalLoanByLoanExternalId` | Attach originator to working capital loan by loan external ID and originator ID |
| POST | `/v1/working-capital-loans/external-id/{loanExternalId}/originators/external-id/{originatorExternalId}` | `attachOriginatorToWorkingCapitalLoanByBothExternalIds` | Attach originator to working capital loan by loan external ID and originator external ID |
| DELETE | `/v1/working-capital-loans/{loanId}/originators/{originatorId}` | `detachOriginatorFromWorkingCapitalLoan` | Detach originator from working capital loan by IDs |
| DELETE | `/v1/working-capital-loans/{loanId}/originators/external-id/{originatorExternalId}` | `detachOriginatorFromWorkingCapitalLoanByOriginatorExternalId` | Detach originator from working capital loan by loan ID and originator external ID |
| DELETE | `/v1/working-capital-loans/external-id/{loanExternalId}/originators/{originatorId}` | `detachOriginatorFromWorkingCapitalLoanByLoanExternalId` | Detach originator from working capital loan by loan external ID and originator ID |
| DELETE | `/v1/working-capital-loans/external-id/{loanExternalId}/originators/external-id/{originatorExternalId}` | `detachOriginatorFromWorkingCapitalLoanByBothExternalIds` | Detach originator from working capital loan by loan external ID and originator external ID |

## LoanBuyDownFeeApiResource

源码：[platform/fineract/fineract-progressive-loan/src/main/java/org/apache/fineract/portfolio/loanaccount/api/LoanBuyDownFeeApiResource.java](../../platform/fineract/fineract-progressive-loan/src/main/java/org/apache/fineract/portfolio/loanaccount/api/LoanBuyDownFeeApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loans/{loanId}/buydown-fees` | `retrieveLoanBuyDownFeeAmortizationDetails` | Get the amortization details of Buy Down fees for a loan |
| GET | `/v1/loans/external-id/{loanExternalId}/buydown-fees` | `retrieveLoanBuyDownFeeAmortizationDetailsByExternalId` | Get the amortization details of Buy Down fees for a loan by external ID |
| GET | `/v1/loans/{loanId}/buydown-fees/{loanTransactionId}` | `retrieveBuyDownFeesAllocationData` | Retrieve a BuyDown Fees allocation data |
| GET | `/v1/loans/external-id/{loanExternalId}/buydown-fees/{loanTransactionId}` | `getBuyDownFeesAllocationDataByLoanExternalId` | Retrieve a BuyDown Fees allocation data |
| GET | `/v1/loans/{loanId}/buydown-fees/external-id/{loanTransactionExternalId}` | `getBuyDownFeesAllocationDataByTransactionExternalId` | Retrieve a BuyDown Fees allocation data |
| GET | `/v1/loans/external-id/{loanExternalId}/buydown-fees/external-id/{loanTransactionExternalId}` | `getBuyDownFeesAllocationDataByExternalIds` | Retrieve a BuyDown Fees allocation data |

## LoanCapitalizedIncomeApiResource

源码：[platform/fineract/fineract-progressive-loan/src/main/java/org/apache/fineract/portfolio/loanaccount/api/LoanCapitalizedIncomeApiResource.java](../../platform/fineract/fineract-progressive-loan/src/main/java/org/apache/fineract/portfolio/loanaccount/api/LoanCapitalizedIncomeApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loans/{loanId}/deferredincome` | `fetchLoanCapitalizedIncomeData` |  |
| GET | `/v1/loans/external-id/{loanExternalId}/deferredincome` | `fetchLoanCapitalizedIncomeDataByExternalId` |  |
| GET | `/v1/loans/{loanId}/capitalized-incomes` | `fetchCapitalizedIncomeDetails` | Fetch the Capitalized Income related informations |
| GET | `/v1/loans/external-id/{loanExternalId}/capitalized-incomes` | `fetchCapitalizedIncomeDetailsByExternalId` | Get the amortization details of Capitalized Income for a loan by external ID |
| GET | `/v1/loans/{loanId}/capitalized-incomes/{loanTransactionId}` | `retrieveCapitalizedIncomeAllocationData` | Retrieve a capitalized income allocation data |
| GET | `/v1/loans/external-id/{loanExternalId}/capitalized-incomes/{loanTransactionId}` | `getCapitalizedIncomeAllocationDataByLoanExternalId` | Retrieve a capitalized income allocation data |
| GET | `/v1/loans/{loanId}/capitalized-incomes/external-id/{loanTransactionExternalId}` | `getCapitalizedIncomeAllocationDataByTransactionExternalId` | Retrieve a capitalized income allocation data |
| GET | `/v1/loans/external-id/{loanExternalId}/capitalized-incomes/external-id/{loanTransactionExternalId}` | `getCapitalizedIncomeAllocationDataByExternalIds` | Retrieve a capitalized income allocation data |

## InternalProgressiveLoanApiResource

源码：[platform/fineract/fineract-progressive-loan/src/main/java/org/apache/fineract/portfolio/loanaccount/service/InternalProgressiveLoanApiResource.java](../../platform/fineract/fineract-progressive-loan/src/main/java/org/apache/fineract/portfolio/loanaccount/service/InternalProgressiveLoanApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/internal/loan/progressive/{loanId}/model` | `retrieveOneInternalProgressiveLoan` | Fetch ProgressiveLoanInterestScheduleModel |
| POST | `/v1/internal/loan/progressive/{loanId}/model` | `updateInternalProgressiveLoan` | Update and Save ProgressiveLoanInterestScheduleModel |
| DELETE | `/v1/internal/loan/progressive/{loanId}/model` | `deleteInternalProgressiveLoan` | Delete ProgressiveLoanInterestScheduleModel By Loan ID |

## JournalEntriesApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/accounting/journalentry/api/JournalEntriesApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/accounting/journalentry/api/JournalEntriesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/journalentries` | `retrieveAllJournalEntries` | List Journal Entries |
| GET | `/v1/journalentries/{journalEntryId}` | `retrieveJournalEntryById` | Retrieve a single Entry |
| POST | `/v1/journalentries` | `createGLJournalEntry` | Create \"Balanced\" Journal Entries |
| POST | `/v1/journalentries/{transactionId}` | `createReversalJournalEntry` | Update Running balances for Journal Entries |
| GET | `/v1/journalentries/provisioning` | `retrieveJournalEntries` | Retrieve Journal Entries for Provisioning |
| GET | `/v1/journalentries/openingbalance` | `retrieveOpeningBalance` | Retrieve Opening Balance |
| GET | `/v1/journalentries/downloadtemplate` | `getJournalEntriesTemplate` | Download journal entries template |
| POST | `/v1/journalentries/uploadtemplate` | `postJournalEntriesTemplate` | Upload journal entries template |

## AdHocApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/adhocquery/api/AdHocApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/adhocquery/api/AdHocApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/adhocquery` | `retrieveAll_1` |  |
| GET | `/v1/adhocquery/template` | `template` |  |
| POST | `/v1/adhocquery` | `createAdHocQuery` |  |
| GET | `/v1/adhocquery/{adHocId}` | `retrieveAdHocQuery` |  |
| PUT | `/v1/adhocquery/{adHocId}` | `update` |  |
| DELETE | `/v1/adhocquery/{adHocId}` | `deleteAdHocQuery` |  |

## ConfigureBusinessStepApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/cob/api/ConfigureBusinessStepApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/cob/api/ConfigureBusinessStepApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/jobs/names` | `retrieveAllConfiguredBusinessJobs` | List Business Jobs |
| GET | `/v1/jobs/{jobName}/steps` | `retrieveAllConfiguredBusinessStep` | List Business Step Configurations for a Job |
| PUT | `/v1/jobs/{jobName}/steps` | `updateJobBusinessStepConfig` | List Business Step Configurations for a Job |
| GET | `/v1/jobs/{jobName}/available-steps` | `retrieveAllAvailableBusinessStep` | List Business Step Configurations for a Job |

## InternalCOBApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/cob/api/InternalCOBApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/cob/api/InternalCOBApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/internal/cob/partitions/{partitionSize}` | `getCobPartitions` |  |
| POST | `/v1/internal/cob/fast-forward-cob-date-of-loan/{loanId}` | `updateLoanCobLastDate` |  |
| POST | `/v1/internal/cob/loan-reprocess/{loanId}` | `loanReprocess` |  |

## InternalLoanAccountLockApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/cob/api/InternalLoanAccountLockApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/cob/api/InternalLoanAccountLockApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/internal/loans/{loanId}/place-lock/{lockOwner}` | `placeLockOnLoanAccount` |  |

## LoanAccountLockApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/cob/api/LoanAccountLockApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/cob/api/LoanAccountLockApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loans/locked` | `retrieveLockedAccounts` | List locked loan accounts |

## LoanCOBCatchUpApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/cob/api/LoanCOBCatchUpApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/cob/api/LoanCOBCatchUpApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loans/oldest-cob-closed` | `getOldestCOBProcessedLoan` | Retrieves the oldest COB processed loan |
| POST | `/v1/loans/catch-up` | `executeLoanCOBCatchUp` | Executes Loan COB Catch Up |
| GET | `/v1/loans/is-catch-up-running` | `isCatchUpRunning` | Retrieves whether Loan COB catch up is running |

## WorkingCapitalLoanCOBCatchUpApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/cob/api/WorkingCapitalLoanCOBCatchUpApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/cob/api/WorkingCapitalLoanCOBCatchUpApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/working-capital-loans/oldest-cob-closed` | `getOldestCOBProcessedLoan` | Retrieves the oldest COB processed Working Capital Loan |
| POST | `/v1/working-capital-loans/catch-up` | `executeLoanCOBCatchUp` | Executes Working Capital Loan COB Catch Up |
| GET | `/v1/working-capital-loans/is-catch-up-running` | `isCatchUpRunning` | Retrieves whether Working Capital Loan COB catch up is running |

## AuditsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/commands/api/AuditsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/commands/api/AuditsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/audits` | `retrieveAuditEntries` | List Audits |
| GET | `/v1/audits/{auditId}` | `retrieveAuditEntry` | Retrieve an Audit Entry |
| GET | `/v1/audits/searchtemplate` | `retrieveAuditSearchTemplate` | Audit Search Template |

## MakercheckersApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/commands/api/MakercheckersApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/commands/api/MakercheckersApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/makercheckers` | `retrieveCommands` | List Maker Checker Entries |
| GET | `/v1/makercheckers/searchtemplate` | `retrieveAuditSearchTemplate` | Maker Checker Search Template |
| POST | `/v1/makercheckers/{auditId}` | `approveMakerCheckerEntry` | Approve Maker Checker Entry  /  Reject Maker Checker Entry |
| DELETE | `/v1/makercheckers/{auditId}` | `deleteMakerCheckerEntry` | Delete Maker Checker Entry |

## AuditsV2ApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/commands/api/v2/AuditsV2ApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/commands/api/v2/AuditsV2ApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v2/audits` | `retrieveAllAuditsV2` | List Audits |

## AccountNumberFormatsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/accountnumberformat/api/AccountNumberFormatsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/accountnumberformat/api/AccountNumberFormatsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/accountnumberformats/template` | `retrieveTemplateAccountNumberFormat` | Retrieve Account number format Template |
| GET | `/v1/accountnumberformats` | `retrieveAllAccountNumberFormats` | List Account number formats |
| GET | `/v1/accountnumberformats/{accountNumberFormatId}` | `retrieveOneAccountNumberFormat` | Retrieve an Account number format |
| POST | `/v1/accountnumberformats` | `createAccountNumberFormat` | Create an Account number format |
| PUT | `/v1/accountnumberformats/{accountNumberFormatId}` | `updateAccountNumberFormat` | Update an Account number format |
| DELETE | `/v1/accountnumberformats/{accountNumberFormatId}` | `deleteAccountNumberFormat` | Delete an Account number format |

## BulkImportApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/bulkimport/api/BulkImportApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/bulkimport/api/BulkImportApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/imports` | `retrieveImportDocuments` |  |
| GET | `/v1/imports/getOutputTemplateLocation` | `retriveOutputTemplateLocation` |  |
| GET | `/v1/imports/downloadOutputTemplate` | `getOutputTemplate` |  |

## EmailApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/campaigns/email/api/EmailApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/campaigns/email/api/EmailApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/email` | `retrieveAllEmails` | List all email messages |
| GET | `/v1/email/pendingEmail` | `retrievePendingEmail` | Retrieve pending email messages |
| GET | `/v1/email/sentEmail` | `retrieveSentEmail` | Retrieve sent email messages |
| GET | `/v1/email/messageByStatus` | `retrieveAllEmailByStatus` | Retrieve email messages by status |
| GET | `/v1/email/failedEmail` | `retrieveFailedEmail` | Retrieve failed email messages |
| POST | `/v1/email` | `createEmail` | Create an email message |
| GET | `/v1/email/{resourceId}` | `retrieveOneEmail` | Retrieve an email message |
| PUT | `/v1/email/{resourceId}` | `updateEmail` | Update an email message |
| DELETE | `/v1/email/{resourceId}` | `deleteEmail` | Delete an email message |

## EmailCampaignApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/campaigns/email/api/EmailCampaignApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/campaigns/email/api/EmailCampaignApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/email/campaign/{resourceId}` | `retrieveOneEmailCampaign` | Retrieve an email campaign |
| GET | `/v1/email/campaign` | `retrieveAllEmailCampaigns` | List all email campaigns |
| POST | `/v1/email/campaign` | `createEmailCampaign` | Create an email campaign |
| PUT | `/v1/email/campaign/{resourceId}` | `updateEmailCampaign` | Update an email campaign |
| POST | `/v1/email/campaign/{resourceId}` | `handleCommandsEmailCampaign` | Activate, close, or reactivate an email campaign |
| POST | `/v1/email/campaign/preview` | `previewEmailCampaign` | Preview email campaign message |
| GET | `/v1/email/campaign/template` | `retrieveAllTemplatesEmailCampaign` | Retrieve email campaign template |
| GET | `/v1/email/campaign/template/{resourceId}` | `retrieveOneTemplateEmailCampaign` | Retrieve an email campaign template detail by ID |
| DELETE | `/v1/email/campaign/{resourceId}` | `deleteEmailCampaign` | Delete an email campaign |

## EmailConfigurationApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/campaigns/email/api/EmailConfigurationApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/campaigns/email/api/EmailConfigurationApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/email/configuration` | `retrieveAllEmailConfigurations` | List all email configurations |
| PUT | `/v1/email/configuration` | `updateEmailConfiguration` | Update email configuration |

## SmsCampaignApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/campaigns/sms/api/SmsCampaignApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/campaigns/sms/api/SmsCampaignApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/smscampaigns/template` | `retrieveTemplateSmsCampaign` | Retrieve a SMS Campaign |
| POST | `/v1/smscampaigns` | `createSmsCampaign` | Create a SMS Campaign |
| GET | `/v1/smscampaigns/{resourceId}` | `retrieveOneSmsCampaign` | Retrieve a SMS Campaign |
| GET | `/v1/smscampaigns` | `retrieveAllSmsCampaigns` | List SMS Campaigns |
| PUT | `/v1/smscampaigns/{campaignId}` | `updateSmsCampaign` | Update a Campaign |
| POST | `/v1/smscampaigns/{campaignId}` | `handleCommandsSmsCampaign` | SMS Campaign |
| POST | `/v1/smscampaigns/preview` | `previewSmsCampaign` | Preview SMS Campaign message |
| DELETE | `/v1/smscampaigns/{campaignId}` | `deleteSmsCampaign` | Delete a SMS Campaign |

## CodeValuesApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/codes/api/CodeValuesApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/codes/api/CodeValuesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/codes/{codeId}/codevalues` | `retrieveAllCodeValues` | List Code Values |
| GET | `/v1/codes/{codeId}/codevalues/{codeValueId}` | `retrieveCodeValue` | Retrieve a Code description |
| POST | `/v1/codes/{codeId}/codevalues` | `createCodeValue` | Create a Code description |
| PUT | `/v1/codes/{codeId}/codevalues/{codeValueId}` | `updateCodeValue` | Update a Code description |
| DELETE | `/v1/codes/{codeId}/codevalues/{codeValueId}` | `deleteCodeValue` | Delete a Code description |
| GET | `/v1/codes/name/{codeName}/codevalues` | `retrieveAllCodeValuesByCodeName` | List Code Values |
| GET | `/v1/codes/name/{codeName}/codevalues/{codeValueId}` | `retrieveCodeValue` | Retrieve a Code description |
| POST | `/v1/codes/name/{codeName}/codevalues` | `createCodeValueByCodeName` | Create a Code description |
| PUT | `/v1/codes/name/{codeName}/codevalues/{codeValueId}` | `updateCodeValueByCodeName` | Update a Code description |
| DELETE | `/v1/codes/name/{codeName}/codevalues/{codeValueId}` | `deleteCodeValue` | Delete a Code description |

## CodesApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/codes/api/CodesApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/codes/api/CodesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/codes` | `retrieveAllCodes` | Retrieve Codes |
| POST | `/v1/codes` | `createCode` | Create a Code |
| GET | `/v1/codes/{codeId}` | `retrieveOneCode` | Retrieve a Code |
| GET | `/v1/codes/name/{codeName}` | `retrieveOneCodeByName` | Retrieve a Code |
| PUT | `/v1/codes/{codeId}` | `updateCode` | Update a Code |
| DELETE | `/v1/codes/{codeId}` | `deleteCode` | Delete a Code |

## ExternalServicesConfigurationApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/configuration/api/ExternalServicesConfigurationApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/configuration/api/ExternalServicesConfigurationApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/externalservice/{servicename}` | `retrieveExternalServicesConfiguration` | Retrieve External Services Configuration |
| PUT | `/v1/externalservice/{servicename}` | `updateExternalServicesConfiguration` | Update External Service |

## GlobalConfigurationApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/configuration/api/GlobalConfigurationApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/configuration/api/GlobalConfigurationApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/configurations` | `retrieveConfiguration` | Retrieve Global Configuration  /  Retrieve Global Configuration for surveys |
| GET | `/v1/configurations/{configId}` | `retrieveOneGlobalConfiguration` | Retrieve Global Configuration |
| GET | `/v1/configurations/name/{name}` | `retrieveOneByName` | Retrieve Global Configuration |
| PUT | `/v1/configurations/{configId}` | `updateGlobalConfiguration` | Update Global Configuration |
| PUT | `/v1/configurations/name/{configName}` | `updateConfigurationByName` | Update Global Configuration by name |

## InternalConfigurationsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/configuration/api/InternalConfigurationsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/configuration/api/InternalConfigurationsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| PUT | `/v1/internal/configurations/name/{configName}/value/{configValue}` | `updateInternalGlobalConfiguration` | Update internal global configuration |

## CreditBureauConfigurationApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/creditbureau/api/CreditBureauConfigurationApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/creditbureau/api/CreditBureauConfigurationApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/CreditBureauConfiguration` | `getCreditBureau` |  |
| GET | `/v1/CreditBureauConfiguration/mappings` | `getCreditBureauLoanProductMapping` |  |
| GET | `/v1/CreditBureauConfiguration/organisationCreditBureau` | `getOrganisationCreditBureau` |  |
| GET | `/v1/CreditBureauConfiguration/config/{organisationCreditBureauId}` | `getConfiguration` |  |
| GET | `/v1/CreditBureauConfiguration/loanProduct` | `fetchLoanProducts` |  |
| GET | `/v1/CreditBureauConfiguration/loanProduct/{loanProductId}` | `fetchMappingByLoanProductId` |  |
| PUT | `/v1/CreditBureauConfiguration/organisationCreditBureau` | `updateCreditBureau` |  |
| PUT | `/v1/CreditBureauConfiguration/mappings` | `updateCreditBureauLoanProductMapping` |  |
| POST | `/v1/CreditBureauConfiguration/organisationCreditBureau/{organisationCreditBureauId}` | `addOrganisationCreditBureau` |  |
| POST | `/v1/CreditBureauConfiguration/mappings/{organisationCreditBureauId}` | `createCreditBureauLoanProductMapping` |  |
| POST | `/v1/CreditBureauConfiguration/configuration/{creditBureauId}` | `createCreditBureauConfiguration` |  |
| PUT | `/v1/CreditBureauConfiguration/configuration/{configurationId}` | `updateCreditBureauConfiguration` |  |

## CreditBureauIntegrationApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/creditbureau/api/CreditBureauIntegrationApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/creditbureau/api/CreditBureauIntegrationApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/creditBureauIntegration/creditReport` | `fetchCreditReport` |  |
| POST | `/v1/creditBureauIntegration/addCreditReport` | `addCreditReport` |  |
| POST | `/v1/creditBureauIntegration/saveCreditReport` | `saveCreditReport` |  |
| GET | `/v1/creditBureauIntegration/creditReport/{creditBureauId}` | `getSavedCreditReport` |  |
| DELETE | `/v1/creditBureauIntegration/deleteCreditReport/{creditBureauId}` | `deleteCreditReport` |  |

## DatatablesApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/dataqueries/api/DatatablesApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/dataqueries/api/DatatablesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/datatables` | `getDatatables` | List Data Tables |
| POST | `/v1/datatables` | `createDatatable` | Create Data Table |
| PUT | `/v1/datatables/{datatableName}` | `updateDatatable` | Update Data Table |
| DELETE | `/v1/datatables/{datatableName}` | `deleteDatatable` | Delete Data Table |
| POST | `/v1/datatables/register/{datatable}/{apptable}` | `registerDatatable` | Register Data Table |
| POST | `/v1/datatables/deregister/{datatable}` | `deregisterDatatable` | Deregister Data Table |
| GET | `/v1/datatables/{datatable}` | `getDatatable` | Retrieve Data Table Details |
| GET | `/v1/datatables/{datatable}/query` | `queryValues` | Query Data Table values |
| POST | `/v1/datatables/{datatable}/query` | `advancedQuery` | Query Data Table values |
| GET | `/v1/datatables/{datatable}/{apptableId}` | `getDatatableEntries` |  |
| GET | `/v1/datatables/{datatable}/{apptableId}/{datatableId}` | `getDatatableManyEntry` | Retrieve Entry from Data Table (One to Many) |
| POST | `/v1/datatables/{datatable}/{apptableId}` | `createDatatableEntry` | Create Entry in Data Table |
| PUT | `/v1/datatables/{datatable}/{apptableId}` | `updateDatatableEntryOnetoOne` | Update Entry in Data Table (One to One) |
| PUT | `/v1/datatables/{datatable}/{apptableId}/{datatableId}` | `updateDatatableEntryOneToMany` | Update Entry in Data Table (One to Many) |
| DELETE | `/v1/datatables/{datatable}/{apptableId}` | `deleteDatatableEntries` | Delete Entry(s) in Data Table |
| DELETE | `/v1/datatables/{datatable}/{apptableId}/{datatableId}` | `deleteDatatableEntry` | Delete Entry in Datatable (One to Many) |

## EntityDatatableChecksApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/dataqueries/api/EntityDatatableChecksApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/dataqueries/api/EntityDatatableChecksApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/entityDatatableChecks` | `retrieveAllEntityDatatableChecks` | List Entity-Datatable Checks |
| GET | `/v1/entityDatatableChecks/template` | `retrieveTemplateEntityDatatableChecks` | Retrieve Entity-Datatable Checks Template |
| POST | `/v1/entityDatatableChecks` | `createEntityDatatableCheck` | Create Entity-Datatable Checks |
| DELETE | `/v1/entityDatatableChecks/{entityDatatableCheckId}` | `deleteEntityDatatableCheck` | Delete Entity-Datatable Checks |

## ReportsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/dataqueries/api/ReportsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/dataqueries/api/ReportsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/reports` | `retrieveAllReports` | List Reports |
| GET | `/v1/reports/{id}` | `retrieveOneReport` | Retrieve a Report  |
| GET | `/v1/reports/template` | `retrieveTemplateReport` | Retrieve Report Template |
| POST | `/v1/reports` | `createReport` | Create a Report |
| PUT | `/v1/reports/{id}` | `updateReport` | Update a Report |
| DELETE | `/v1/reports/{id}` | `deleteReport` | Delete a Report |

## RunreportsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/dataqueries/api/RunreportsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/dataqueries/api/RunreportsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/runreports/availableExports/{reportName}` | `retrieveAllAvailableExports` | Return all available export types for the specific report |
| GET | `/v1/runreports/{reportName}` | `runReport` | Run a predefined report |

## FineractEntityApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/entityaccess/api/FineractEntityApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/entityaccess/api/FineractEntityApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/entitytoentitymapping` | `retrieveAll_3` |  |
| GET | `/v1/entitytoentitymapping/{mapId}` | `retrieveOne` |  |
| GET | `/v1/entitytoentitymapping/{mapId}/{fromId}/{toId}` | `getEntityToEntityMappings` |  |
| POST | `/v1/entitytoentitymapping/{relId}` | `createMap` |  |
| PUT | `/v1/entitytoentitymapping/{mapId}` | `updateMap` |  |
| DELETE | `/v1/entitytoentitymapping/{mapId}` | `delete` |  |

## HookApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/hooks/api/HookApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/hooks/api/HookApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/hooks` | `retrieveAllHooks` | Retrieve Hooks |
| GET | `/v1/hooks/{hookId}` | `retrieveOneHook` | Retrieve a Hook |
| GET | `/v1/hooks/template` | `retrieveTemplateHook` | Retrieve Hooks Template |
| POST | `/v1/hooks` | `createHook` | Create a Hook |
| PUT | `/v1/hooks/{hookId}` | `updateHook` | Update a Hook |
| DELETE | `/v1/hooks/{hookId}` | `deleteHook` | Delete a Hook |

## InstanceModeApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/instancemode/api/InstanceModeApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/instancemode/api/InstanceModeApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| PUT | `/v1/instance-mode` | `updateInstanceMode` | Changes the Fineract instance mode |

## InlineJobApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/jobs/api/InlineJobApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/jobs/api/InlineJobApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/jobs/{jobName}/inline` | `executeInlineJob` | Starts an inline Job |

## SchedulerApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/jobs/api/SchedulerApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/jobs/api/SchedulerApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/scheduler` | `retrieveSchedulerStatus` | Retrieve Scheduler Status |
| POST | `/v1/scheduler` | `handleCommandsScheduler` | Activate Scheduler Jobs  /  Suspend Scheduler Jobs |

## SchedulerJobApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/jobs/api/SchedulerJobApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/jobs/api/SchedulerJobApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/jobs` | `retrieveAllSchedulerJobs` | Retrieve Scheduler Jobs |
| GET | `/v1/jobs/{jobId}` | `retrieveOneSchedulerJob` | Retrieve a Job |
| GET | `/v1/jobs/short-name/{shortName}` | `retrieveByShortName` | Retrieve a Job |
| GET | `/v1/jobs/{jobId}/runhistory` | `retrieveHistory` | Retrieve Job Run History |
| GET | `/v1/jobs/short-name/{shortName}/runhistory` | `retrieveHistoryByShortName` | Retrieve Job Run History |
| POST | `/v1/jobs/{jobId}` | `executeJob` | Run a Job |
| POST | `/v1/jobs/short-name/{shortName}` | `executeJobByShortName` | Run a Job |
| PUT | `/v1/jobs/{jobId}` | `updateJobDetail` | Update a Job |
| PUT | `/v1/jobs/short-name/{shortName}` | `updateJobDetailByShortName` | Update a Job |

## ReportMailingJobApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/reportmailingjob/api/ReportMailingJobApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/reportmailingjob/api/ReportMailingJobApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/reportmailingjobs` | `createReportMailingJob` | Create a Report Mailing Job |
| PUT | `/v1/reportmailingjobs/{entityId}` | `updateReportMailingJob` | Update a Report Mailing Job  |
| DELETE | `/v1/reportmailingjobs/{entityId}` | `deleteReportMailingJob` | Delete a Report Mailing Job |
| GET | `/v1/reportmailingjobs/{entityId}` | `retrieveOneReportMailingJob` | Retrieve a Report Mailing Job |
| GET | `/v1/reportmailingjobs/template` | `retrieveTemplateReportMailingJob` | Retrieve Report Mailing Job Details Template |
| GET | `/v1/reportmailingjobs` | `retrieveAllReportMailingJobs` | List Report Mailing Jobs |

## ReportMailingJobRunHistoryApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/reportmailingjob/api/ReportMailingJobRunHistoryApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/reportmailingjob/api/ReportMailingJobRunHistoryApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/reportmailingjobrunhistory` | `retrieveAllReportMailingJobRunHistory` | List Report Mailing Job History |

## SmsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/sms/api/SmsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/sms/api/SmsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/sms` | `retrieveAllSms` | List all SMS messages |
| POST | `/v1/sms` | `createSms` | Create a SMS message |
| GET | `/v1/sms/{resourceId}` | `retrieveOneSms` | Retrieve a SMS message |
| GET | `/v1/sms/{campaignId}/messageByStatus` | `retrieveAllSmsByStatus` | Retrieve SMS messages by status |
| PUT | `/v1/sms/{resourceId}` | `updateSms` | Update a SMS message |
| DELETE | `/v1/sms/{resourceId}` | `deleteSms` | Delete a SMS message |

## LikelihoodApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/survey/api/LikelihoodApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/survey/api/LikelihoodApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/likelihood/{ppiName}` | `retrieveAll_5` |  |
| GET | `/v1/likelihood/{ppiName}/{likelihoodId}` | `retrieve_1` |  |
| PUT | `/v1/likelihood/{ppiName}/{likelihoodId}` | `update_2` |  |

## PovertyLineApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/survey/api/PovertyLineApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/survey/api/PovertyLineApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/povertyLine/{ppiName}` | `retrieveAll_6` |  |
| GET | `/v1/povertyLine/{ppiName}/{likelihoodId}` | `retrieveAll_7` |  |

## SurveyApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/survey/api/SurveyApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/infrastructure/survey/api/SurveyApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/survey` | `retrieveAllSurveys` | Retrieve surveys |
| GET | `/v1/survey/{surveyName}` | `retrieveOneSurvey` | Retrieve survey |
| POST | `/v1/survey/{surveyName}/{apptableId}` | `createSurveyEntry` | Create an entry in the survey table |
| GET | `/v1/survey/{surveyName}/{clientId}` | `getClientSurveyOverview` |  |
| GET | `/v1/survey/{surveyName}/{clientId}/{entryId}` | `getSurveyEntry` |  |
| PUT | `/v1/survey/register/{surveyName}/{apptable}` | `register` |  |
| DELETE | `/v1/survey/{surveyName}/{clientId}/{fulfilledId}` | `deleteDatatableEntries` |  |

## InteropApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/interoperation/api/InteropApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/interoperation/api/InteropApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/interoperation/health` | `health` | Query Interoperation Health Request |
| GET | `/v1/interoperation/accounts/{accountId}` | `getAccountDetails` | Query Interoperation Account details |
| GET | `/v1/interoperation/accounts/{accountId}/transactions` | `getAccountTransactions` | Query transactions by Account Id |
| GET | `/v1/interoperation/accounts/{accountId}/identifiers` | `getAccountIdentifiers` | Query Interoperation secondary identifiers by Account Id |
| GET | `/v1/interoperation/parties/{idType}/{idValue}` | `getAccountByIdentifier` | Query Interoperation Account by secondary identifier |
| GET | `/v1/interoperation/parties/{idType}/{idValue}/{subIdOrType}` | `getAccountByIdentifier` | Query Interoperation Account by secondary identifier |
| POST | `/v1/interoperation/parties/{idType}/{idValue}` | `registerAccountIdentifier` | Interoperation Identifier registration |
| POST | `/v1/interoperation/parties/{idType}/{idValue}/{subIdOrType}` | `registerAccountIdentifier` | Interoperation Identifier registration |
| DELETE | `/v1/interoperation/parties/{idType}/{idValue}` | `deleteAccountIdentifier` | Allow Interoperation Identifier registration |
| DELETE | `/v1/interoperation/parties/{idType}/{idValue}/{subIdOrType}` | `deleteAccountIdentifier` | Allow Interoperation Identifier registration |
| GET | `/v1/interoperation/transactions/{transactionCode}/requests/{requestCode}` | `getTransactionRequest` | Query Interoperation Transaction Request |
| POST | `/v1/interoperation/requests` | `createTransactionRequest` | Allow Interoperation Transaction Request |
| GET | `/v1/interoperation/transactions/{transactionCode}/quotes/{quoteCode}` | `getQuote` | Query Interoperation Quote |
| POST | `/v1/interoperation/quotes` | `createQuote` | Calculate Interoperation Quote |
| GET | `/v1/interoperation/transactions/{transactionCode}/transfers/{transferCode}` | `getTransfer` | Query Interoperation Transfer |
| POST | `/v1/interoperation/transfers` | `performTransfer` | Prepare Interoperation Transfer |
| GET | `/v1/interoperation/accounts/{accountId}/kyc` | `getClientKyc` | Query KYC by Account Id |
| POST | `/v1/interoperation/transactions/{accountId}/disburse` | `disburseLoan` | Disburse Loan by Account Id |
| POST | `/v1/interoperation/transactions/{accountId}/loanrepayment` | `loanRepayment` | Loan Repayment by Account Id |

## NotificationApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/notification/api/NotificationApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/notification/api/NotificationApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/notifications` | `getAllNotifications` | Retrieve all Notifications |
| PUT | `/v1/notifications` | `updateNotificationReadStatus` | Update Notification Read Status |

## HolidaysApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/organisation/holiday/api/HolidaysApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/organisation/holiday/api/HolidaysApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/holidays` | `createHoliday` | Create a Holiday |
| POST | `/v1/holidays/{holidayId}` | `handleCommandsHoliday` | Activate a Holiday |
| GET | `/v1/holidays/{holidayId}` | `retrieveOneHoliday` | Retrieve a Holiday |
| PUT | `/v1/holidays/{holidayId}` | `updateHoliday` | Update a Holiday |
| DELETE | `/v1/holidays/{holidayId}` | `deleteHoliday` | Delete a Holiday |
| GET | `/v1/holidays` | `retrieveAllHolidays` | List Holidays |
| GET | `/v1/holidays/template` | `retrieveRepaymentScheduleUpdationTyeOptions` |  |

## OfficeTransactionsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/organisation/office/api/OfficeTransactionsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/organisation/office/api/OfficeTransactionsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/officetransactions` | `retrieveOfficeTransactions` |  |
| GET | `/v1/officetransactions/template` | `newOfficeTransactionDetails` |  |
| POST | `/v1/officetransactions` | `transferMoneyFrom` |  |
| DELETE | `/v1/officetransactions/{transactionId}` | `delete_2` |  |

## OfficesApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/organisation/office/api/OfficesApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/organisation/office/api/OfficesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/offices` | `retrieveAllOffices` | List Offices |
| GET | `/v1/offices/template` | `retrieveTemplateOffice` | Retrieve Office Details Template |
| POST | `/v1/offices` | `createOffice` | Create an Office |
| GET | `/v1/offices/{officeId}` | `retrieveOneOffice` | Retrieve an Office |
| GET | `/v1/offices/external-id/{externalId}` | `retrieveOneOfficeByExternalId` | Retrieve an Office using external id |
| PUT | `/v1/offices/{officeId}` | `updateOffice` | Update Office |
| PUT | `/v1/offices/external-id/{externalId}` | `updateOfficeByExternalId` | Update Office |
| GET | `/v1/offices/downloadtemplate` | `getOfficeTemplate` |  |
| POST | `/v1/offices/uploadtemplate` | `postOfficeTemplate` |  |

## ProvisioningCategoryApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/organisation/provisioning/api/ProvisioningCategoryApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/organisation/provisioning/api/ProvisioningCategoryApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/provisioningcategory` | `retrieveAll_8` |  |
| POST | `/v1/provisioningcategory` | `createProvisioningCategory` |  |
| PUT | `/v1/provisioningcategory/{categoryId}` | `updateProvisioningCategory` |  |
| DELETE | `/v1/provisioningcategory/{categoryId}` | `deleteProvisioningCategory` |  |

## ProvisioningCriteriaApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/organisation/provisioning/api/ProvisioningCriteriaApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/organisation/provisioning/api/ProvisioningCriteriaApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/provisioningcriteria/template` | `retrieveTemplate_1` |  |
| GET | `/v1/provisioningcriteria/{criteriaId}` | `retrieveOneProvisioningCriteria` | Retrieves a Provisioning Criteria |
| GET | `/v1/provisioningcriteria` | `retrieveAllProvisioningCriteria` | Retrieves all created Provisioning Criterias |
| POST | `/v1/provisioningcriteria` | `createProvisioningCriteria` | Create a new Provisioning Criteria |
| PUT | `/v1/provisioningcriteria/{criteriaId}` | `updateProvisioningCriteria` | Updates a new Provisioning Criteria |
| DELETE | `/v1/provisioningcriteria/{criteriaId}` | `deleteProvisioningCriteria` | Deletes Provisioning Criteria |

## StaffApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/organisation/staff/api/StaffApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/organisation/staff/api/StaffApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/staff` | `retrieveAllStaff` | Retrieve Staff |
| GET | `/v1/staff/{staffId}` | `retrieveOneStaff` | Retrieve a Staff Member |
| GET | `/v1/staff/downloadtemplate` | `getBulkTemplateStaff` | Download bulk import template |
| POST | `/v1/staff` | `createStaff` | Create a staff member |
| PUT | `/v1/staff/{staffId}` | `updateStaff` | Update a Staff Member |
| POST | `/v1/staff/uploadtemplate` | `postTemplate` |  |

## WorkingDaysApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/organisation/workingdays/api/WorkingDaysApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/organisation/workingdays/api/WorkingDaysApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/workingdays` | `retrieveAllWorkingDays` | List Working days |
| PUT | `/v1/workingdays` | `updateWorkingDay` | Update a Working Day |
| GET | `/v1/workingdays/template` | `retrieveTemplateWorkingDays` | Working Days Template |

## AccountTransfersApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/account/api/AccountTransfersApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/account/api/AccountTransfersApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/accounttransfers/template` | `retrieveTemplateAccountTransfer` | Retrieve Account Transfer Template |
| POST | `/v1/accounttransfers` | `createAccountTransfer` | Create new Transfer |
| GET | `/v1/accounttransfers` | `retrieveAllAccountTransfers` | List account transfers |
| GET | `/v1/accounttransfers/{transferId}` | `retrieveOneAccountTransfer` | Retrieve account transfer |
| GET | `/v1/accounttransfers/templateRefundByTransfer` | `retrieveTemplateRefundByTransfer` | Retrieve Refund of an Active Loan by Transfer Template |
| POST | `/v1/accounttransfers/refundByTransfer` | `refundByTransfer` | Refund of an Active Loan by Transfer |
| POST | `/v1/accounttransfers/{accountTransferId}` | `accountTransferOperation` | Operation on active account transfer |

## StandingInstructionApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/account/api/StandingInstructionApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/account/api/StandingInstructionApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/standinginstructions/template` | `retrieveTemplateStandingInstruction` | Retrieve Standing Instruction Template |
| POST | `/v1/standinginstructions` | `createStandingInstruction` | Create new Standing Instruction |
| PUT | `/v1/standinginstructions/{standingInstructionId}` | `updateStandingInstruction` | Update Standing Instruction  /  Delete Standing Instruction |
| GET | `/v1/standinginstructions` | `retrieveAllStandingInstructions` | List Standing Instructions |
| GET | `/v1/standinginstructions/{standingInstructionId}` | `retrieveOneStandingInstruction` | Retrieve Standing Instruction |

## StandingInstructionHistoryApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/account/api/StandingInstructionHistoryApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/account/api/StandingInstructionHistoryApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/standinginstructionrunhistory` | `retrieveAllStandingInstructionHistory` | Standing Instructions Logged History |

## AccountsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/accounts/api/AccountsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/accounts/api/AccountsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/accounts/{type}/template` | `retrieveTemplateShareAccount` | Retrieve Share Account Template |
| GET | `/v1/accounts/{type}/{accountId}` | `retrieveOneShareAccount` | Retrieve a share application/account |
| GET | `/v1/accounts/{type}` | `retrieveAllShareAccounts` | List share applications/accounts |
| POST | `/v1/accounts/{type}` | `createShareAccount` | Submit new share application |
| POST | `/v1/accounts/{type}/{accountId}` | `handleCommandsShareAccount` | Approve share application  /  Undo approval share application  /  Reject share application  /  Activate a share account  /  Close a share account  /  Apply additional shares on a share account  /  Approve additional shares request on a share account  /  Reject additional shares request on a share account  /  Redeem shares on a share account |
| PUT | `/v1/accounts/{type}/{accountId}` | `updateShareAccount` | Modify a share application |
| GET | `/v1/accounts/{type}/downloadtemplate` | `getShareAccountTemplate` | Download share accounts bulk imports template |
| POST | `/v1/accounts/{type}/uploadtemplate` | `postShareAccountTemplate` | Upload share accounts bulk imports data |

## EntityFieldConfigurationApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/address/api/EntityFieldConfigurationApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/address/api/EntityFieldConfigurationApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/fieldconfiguration/{entity}` | `getAddresses` | Retrieves the Entity Field Configuration |

## CalendarsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/calendar/api/CalendarsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/calendar/api/CalendarsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/{entityType}/{entityId}/calendars/{calendarId}` | `retrieveCalendar` | Retrieve a Calendar |
| GET | `/v1/{entityType}/{entityId}/calendars` | `retrieveCalendarsByEntityId` | Retrieve Calendars by Entity |
| GET | `/v1/{entityType}/{entityId}/calendars/template` | `retrieveTemplateCalendar` | Retrieve Calendar Template |
| POST | `/v1/{entityType}/{entityId}/calendars` | `createCalendar` | Create a Calendar |
| PUT | `/v1/{entityType}/{entityId}/calendars/{calendarId}` | `updateCalendar` | Update a Calendar |
| DELETE | `/v1/{entityType}/{entityId}/calendars/{calendarId}` | `deleteCalendar` | Delete a Calendar |

## ClientAddressApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/ClientAddressApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/ClientAddressApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/client/addresses/template` | `retrieveTemplateClientAddress` | Retrieve client address template |
| POST | `/v1/client/{clientid}/addresses` | `createClientAddress` | Create an address for a Client |
| GET | `/v1/client/{clientid}/addresses` | `retrieveAllClientAddresses` | List all addresses for a Client |
| PUT | `/v1/client/{clientid}/addresses` | `updateClientAddress` | Update an address for a Client |

## ClientChargesApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/ClientChargesApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/ClientChargesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/clients/{clientId}/charges` | `retrieveAllClientCharges` | List Client Charges |
| GET | `/v1/clients/{clientId}/charges/template` | `retrieveTemplateClientCharge` | Retrieve client charge template |
| GET | `/v1/clients/{clientId}/charges/{chargeId}` | `retrieveOneClientCharge` | Retrieve a Client Charge |
| POST | `/v1/clients/{clientId}/charges` | `createClientCharge` | Add Client Charge |
| POST | `/v1/clients/{clientId}/charges/{chargeId}` | `payOrWaiveClientCharge` | Pay a Client Charge  /  Waive a Client Charge |
| DELETE | `/v1/clients/{clientId}/charges/{chargeId}` | `deleteClientCharge` | Delete a Client Charge |

## ClientFamilyMembersApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/ClientFamilyMembersApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/ClientFamilyMembersApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/clients/{clientId}/familymembers/{familyMemberId}` | `retrieveOneClientFamilyMember` | Retrieve a client family member |
| GET | `/v1/clients/{clientId}/familymembers` | `retrieveAllClientFamilyMembers` | List all client family members |
| GET | `/v1/clients/{clientId}/familymembers/template` | `retrieveTemplateClientFamilyMember` | Retrieve client family member template |
| PUT | `/v1/clients/{clientId}/familymembers/{familyMemberId}` | `updateClientFamilyMember` | Update a client family member |
| POST | `/v1/clients/{clientId}/familymembers` | `createClientFamilyMember` | Add a client family member |
| DELETE | `/v1/clients/{clientId}/familymembers/{familyMemberId}` | `deleteClientFamilyMember` | Delete a client family member |

## ClientIdentifiersApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/ClientIdentifiersApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/ClientIdentifiersApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/clients/{clientId}/identifiers` | `retrieveAllClientIdentifiers` | List all Identifiers for a Client |
| GET | `/v1/clients/{clientId}/identifiers/template` | `retrieveTemplateClientIdentifier` | Retrieve Client Identifier Details Template |
| POST | `/v1/clients/{clientId}/identifiers` | `createClientIdentifier` | Create an Identifier for a Client |
| GET | `/v1/clients/{clientId}/identifiers/{identifierId}` | `retrieveOneClientIdentifier` | Retrieve a Client Identifier |
| PUT | `/v1/clients/{clientId}/identifiers/{identifierId}` | `updateClientIdentifier` | Update a Client Identifier |
| DELETE | `/v1/clients/{clientId}/identifiers/{identifierId}` | `deleteClientIdentifier` | Delete a Client Identifier |

## ClientTransactionsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/ClientTransactionsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/ClientTransactionsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/clients/{clientId}/transactions` | `retrieveAllClientTransactions` | List Client Transactions |
| GET | `/v1/clients/{clientId}/transactions/{transactionId}` | `retrieveClientTransaction` | Retrieve a Client Transaction |
| POST | `/v1/clients/{clientId}/transactions/{transactionId}` | `undoClientTransaction` | Undo a Client Transaction |
| GET | `/v1/clients/external-id/{clientExternalId}/transactions` | `retrieveAllClientTransactionsByClientExternalId` | List Client Transactions |
| GET | `/v1/clients/external-id/{clientExternalId}/transactions/{transactionId}` | `retrieveClientTransactionByClientExternalId` | Retrieve a Client Transaction |
| POST | `/v1/clients/external-id/{clientExternalId}/transactions/{transactionId}` | `undoClientTransactionByClientExternalId` | Undo a Client Transaction |
| GET | `/v1/clients/{clientId}/transactions/external-id/{transactionExternalId}` | `retrieveClientTransactionByTransactionExternalId` | Retrieve a Client Transaction |
| GET | `/v1/clients/external-id/{clientExternalId}/transactions/external-id/{transactionExternalId}` | `retrieveClientTransactionByClientAndTransactionExternalId` | Retrieve a Client Transaction |
| POST | `/v1/clients/{clientId}/transactions/external-id/{transactionExternalId}` | `undoClientTransactionByTransactionExternalId` | Undo a Client Transaction |
| POST | `/v1/clients/external-id/{clientExternalId}/transactions/external-id/{transactionExternalId}` | `undoClientTransactionByClientAndTransactionExternalId` | Undo a Client Transaction |

## ClientsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/ClientsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/ClientsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/clients/template` | `retrieveTemplateClient` | Retrieve Client Details Template |
| GET | `/v1/clients` | `retrieveAllClients` | List Clients |
| GET | `/v1/clients/{clientId}` | `retrieveOneClient` | Retrieve a Client |
| POST | `/v1/clients` | `createClient` | Create a Client |
| PUT | `/v1/clients/{clientId}` | `updateClient` | Update a Client |
| DELETE | `/v1/clients/{clientId}` | `deleteClient` | Delete a Client |
| POST | `/v1/clients/{clientId}` | `handleCommandClient` | Activate a Client  /  Close a Client  /  Reject a Client  /  Withdraw a Client  /  Reactivate a Client  /  UndoReject a Client  /  UndoWithdraw a Client  /  Assign a Staff  /  Unassign a Staff  /  Update Default Savings Account  /  Propose a Client Transfer  /  Withdraw a Client Transfer  /  Reject a Client Transfer  /  Accept a Client Transfer  /  Propose and Accept a Client Transfer |
| GET | `/v1/clients/{clientId}/accounts` | `retrieveAllClientAccounts` | Retrieve client accounts overview |
| GET | `/v1/clients/downloadtemplate` | `getClientTemplate` | Download client template for bulk import |
| POST | `/v1/clients/uploadtemplate` | `postClientTemplate` | Upload client template for bulk import |
| GET | `/v1/clients/{clientId}/obligeedetails` | `retrieveClientObligeeDetails` | Retrieve client obligee details |
| GET | `/v1/clients/{clientId}/transferproposaldate` | `retrieveClientTransferTemplate` | Retrieve client transfer template |
| GET | `/v1/clients/external-id/{externalId}` | `retrieveOneClientByExternalId` | Retrieve a Client by External Id |
| GET | `/v1/clients/external-id/{externalId}/accounts` | `retrieveAllClientAccountsByExternalId` | Retrieve client accounts overview |
| PUT | `/v1/clients/external-id/{externalId}` | `updateClientByExternalId` | Update a Client using the External Id |
| POST | `/v1/clients/external-id/{externalId}` | `handleCommandClientByExternalId` | Activate a Client  /  Close a Client  /  Reject a Client  /  Withdraw a Client  /  Reactivate a Client  /  UndoReject a Client  /  UndoWithdraw a Client  /  Assign a Staff  /  Unassign a Staff  /  Update Default Savings Account  /  Propose a Client Transfer  /  Withdraw a Client Transfer  /  Reject a Client Transfer  /  Accept a Client Transfer  /  Propose and Accept a Client Transfer |
| DELETE | `/v1/clients/external-id/{externalId}` | `deleteClientByExternalId` | Delete a Client |
| GET | `/v1/clients/external-id/{externalId}/obligeedetails` | `retrieveClientObligeeDetailsByExternalId` | Retrieve client obligee details |
| GET | `/v1/clients/external-id/{externalId}/transferproposaldate` | `retrieveClientTransferTemplateByExternalId` | Retrieve client transfer template |

## InternalClientInformationApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/InternalClientInformationApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/InternalClientInformationApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/internal/client/{clientId}/audit` | `getInternalClientAuditFields` | Get internal client audit fields |

## ClientSearchV2ApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/v2/search/ClientSearchV2ApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/client/api/v2/search/ClientSearchV2ApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v2/clients/search` | `searchClientsByText` | Search Clients by text |

## CollateralsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/collateral/api/CollateralsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/collateral/api/CollateralsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loans/{loanId}/collaterals/template` | `newCollateralTemplate` | Retrieve Collateral Details Template |
| GET | `/v1/loans/{loanId}/collaterals` | `retrieveCollateralDetails` | List Loan Collaterals |
| GET | `/v1/loans/{loanId}/collaterals/{collateralId}` | `retrieveCollateralDetails` | Retrieve a Collateral |
| POST | `/v1/loans/{loanId}/collaterals` | `createCollateral` | Create a Collateral |
| PUT | `/v1/loans/{loanId}/collaterals/{collateralId}` | `updateCollateral` | Update a Collateral |
| DELETE | `/v1/loans/{loanId}/collaterals/{collateralId}` | `deleteCollateral` | Remove a Collateral |

## ClientCollateralManagementApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/collateralmanagement/api/ClientCollateralManagementApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/collateralmanagement/api/ClientCollateralManagementApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/clients/{clientId}/collaterals` | `getClientCollateralProducts` | Get Clients Collateral Products |
| GET | `/v1/clients/{clientId}/collaterals/{clientCollateralId}` | `getClientCollateralData` | Get Client Collateral Data |
| GET | `/v1/clients/{clientId}/collaterals/template` | `getClientCollateralTemplate` | Get Client Collateral Template |
| POST | `/v1/clients/{clientId}/collaterals` | `addClientCollateral` | Add New Collateral For a Client |
| PUT | `/v1/clients/{clientId}/collaterals/{collateralId}` | `updateClientCollateral` | Update New Collateral of a Client |
| DELETE | `/v1/clients/{clientId}/collaterals/{collateralId}` | `deleteClientCollateral` | Delete Client Collateral |

## CollateralManagementApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/collateralmanagement/api/CollateralManagementApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/collateralmanagement/api/CollateralManagementApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/collateral-management` | `createCollateral` | Create a new collateral |
| GET | `/v1/collateral-management/{collateralId}` | `getCollateral` | Get Collateral |
| GET | `/v1/collateral-management` | `getAllCollaterals` | Get All Collaterals |
| GET | `/v1/collateral-management/template` | `getCollateralTemplate` | Get Collateral Template |
| PUT | `/v1/collateral-management/{collateralId}` | `updateCollateral_1` |  |
| DELETE | `/v1/collateral-management/{collateralId}` | `deleteCollateral_1` |  |

## LoanCollateralManagementApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/collateralmanagement/api/LoanCollateralManagementApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/collateralmanagement/api/LoanCollateralManagementApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| DELETE | `/v1/loan-collateral-management/{id}` | `deleteLoanCollateral` |  |
| GET | `/v1/loan-collateral-management/{collateralId}` | `getLoanCollateral` |  |

## CollectionSheetApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/collectionsheet/api/CollectionSheetApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/collectionsheet/api/CollectionSheetApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/collectionsheet` | `generateCollectionSheet` | Generate Individual Collection Sheet  /  Save Collection Sheet |

## FundsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/fund/api/FundsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/fund/api/FundsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/funds` | `retrieveFunds` | Retrieve Funds |
| POST | `/v1/funds` | `createFund` | Create a Fund |
| GET | `/v1/funds/{fundId}` | `retrieveFund` | Retrieve a Fund |
| PUT | `/v1/funds/{fundId}` | `updateFund` | Update a Fund |

## CentersApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/group/api/CentersApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/group/api/CentersApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/centers/template` | `retrieveTemplateCenter` | Retrieve a Center Template |
| GET | `/v1/centers` | `retrieveAllCenters` | List Centers |
| GET | `/v1/centers/{centerId}` | `retrieveOneCenter` | Retrieve a Center |
| POST | `/v1/centers` | `createCenter` | Create a Center |
| PUT | `/v1/centers/{centerId}` | `updateCenter` | Update a Center |
| DELETE | `/v1/centers/{centerId}` | `deleteCenter` | Delete a Center |
| POST | `/v1/centers/{centerId}` | `handleCommandsCenter` | Activate a Center  /  Generate Collection Sheet  /  Save Collection Sheet  /  Close a Center  /  Associate Groups  /  Disassociate Groups |
| GET | `/v1/centers/{centerId}/accounts` | `retrieveGroupAccountsCenter` | Retrieve Center accounts overview |
| GET | `/v1/centers/downloadtemplate` | `getBulkTemplateCenter` | Download Centers Bulk Template |
| POST | `/v1/centers/uploadtemplate` | `postBulkTemplateCenter` | Upload Centers Bulk Template |

## GroupsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/group/api/GroupsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/group/api/GroupsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/groups/template` | `retrieveTemplateGroup` | Retrieve Group Template |
| GET | `/v1/groups` | `retrieveAllGroups` | List Groups |
| GET | `/v1/groups/{groupId}` | `retrieveOneGroup` | Retrieve a Group |
| POST | `/v1/groups` | `createGroup` | Create a Group |
| POST | `/v1/groups/{groupId}/command/unassign_staff` | `unassignLoanOfficerGroup` | Unassign a Staff |
| PUT | `/v1/groups/{groupId}` | `updateGroup` | Update a Group |
| DELETE | `/v1/groups/{groupId}` | `deleteGroup` | Delete a Group |
| POST | `/v1/groups/{groupId}` | `handleCommandsGroup` | Activate a Group  /  Associate Clients  /  Disassociate Clients  /  Transfer Clients across groups  /  Generate Collection Sheet  /  Save Collection Sheet  /  Unassign a Staff  /  Assign a Staff  /  Close a Group  /  Unassign a Role  /  Update a Role |
| GET | `/v1/groups/{groupId}/accounts` | `retrieveAccountsGroup` | Retrieve Group accounts overview |
| GET | `/v1/groups/downloadtemplate` | `getBulkTemplateGroup` | Download Groups Bulk Template |
| POST | `/v1/groups/uploadtemplate` | `postBulkTemplateGroup` | Upload Groups Bulk Template |
| GET | `/v1/groups/{groupId}/glimaccounts` | `retrieveGlimAccountsGroup` | Retrieve GLIM Accounts for Group |
| GET | `/v1/groups/{groupId}/gsimaccounts` | `retrieveGsimAccountsGroup` | Retrieve GSIM Accounts for Group |

## GroupsLevelApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/group/api/GroupsLevelApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/group/api/GroupsLevelApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/grouplevels` | `retrieveAllGroupLevels` | Retrieve All Group Levels |

## CentersV2ApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/group/api/v2/CentersV2ApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/group/api/v2/CentersV2ApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v2/centers` | `retrieveAllCentersV2` | List Centers |

## GroupsV2ApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/group/api/v2/GroupsV2ApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/group/api/v2/GroupsV2ApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v2/groups` | `retrieveAllGroupsV2` | List Groups |

## InterestRateChartSlabsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/interestratechart/api/InterestRateChartSlabsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/interestratechart/api/InterestRateChartSlabsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/interestratecharts/{chartId}/chartslabs/template` | `retrieveTemplateInterestRateChartSlab` | Retrieve Chart Slab Template |
| GET | `/v1/interestratecharts/{chartId}/chartslabs` | `retrieveAllInterestRateChartSlabs` | Retrieve all Slabs |
| GET | `/v1/interestratecharts/{chartId}/chartslabs/{chartSlabId}` | `retrieveOneInterestRateChartSlab` | Retrieve a Slab |
| POST | `/v1/interestratecharts/{chartId}/chartslabs` | `createInterestRateChartSlab` | Create a Slab |
| PUT | `/v1/interestratecharts/{chartId}/chartslabs/{chartSlabId}` | `updateInterestRateChartSlab` | Update a Slab |
| DELETE | `/v1/interestratecharts/{chartId}/chartslabs/{chartSlabId}` | `deleteInterestRateChartSlab` | Delete a Slab |

## InterestRateChartsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/interestratechart/api/InterestRateChartsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/interestratechart/api/InterestRateChartsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/interestratecharts/template` | `retrieveTemplateInterestRateChart` | Retrieve Chart Details Template |
| GET | `/v1/interestratecharts` | `retrieveAllInterestRateCharts` | Retrieve all Charts |
| GET | `/v1/interestratecharts/{chartId}` | `retrieveOneInterestRateChart` | Retrieve a Chart |
| POST | `/v1/interestratecharts` | `createInterestRateChart` | Create a Chart |
| PUT | `/v1/interestratecharts/{chartId}` | `updateInterestRateChart` | Update a Chart |
| DELETE | `/v1/interestratecharts/{chartId}` | `deleteInterestRateChart` | Delete a Chart |

## BulkLoansApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/BulkLoansApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/BulkLoansApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loans/loanreassignment/template` | `loanReassignmentTemplate` |  |
| POST | `/v1/loans/loanreassignment` | `loanReassignment` |  |

## InternalLoanInformationApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/InternalLoanInformationApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/InternalLoanInformationApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/internal/loan/{loanId}/audit` | `getLoanAuditFields` |  |
| GET | `/v1/internal/loan/{loanId}/transaction/{transactionId}/audit` | `getLoanTransactionAuditFields` |  |
| GET | `/v1/internal/loan/status/{statusId}` | `getLoansByStatus` |  |
| GET | `/v1/internal/loan/{loanId}/advanced-payment-allocation-rules` | `getAdvancedPaymentAllocationRulesOfLoan` |  |
| GET | `/v1/internal/loan/maxTransactionDateOfActiveLoan` | `getMaxTransactionDateOfActiveLoans` |  |

## LoanChargesApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/LoanChargesApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/LoanChargesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loans/{loanId}/charges` | `retrieveAllLoanCharges` | List Loan Charges |
| GET | `/v1/loans/external-id/{loanExternalId}/charges` | `retrieveAllLoanChargesByLoanExternalId` | List Loan Charges |
| GET | `/v1/loans/{loanId}/charges/template` | `retrieveTemplateLoanCharge` | Retrieve Loan Charges Template |
| GET | `/v1/loans/external-id/{loanExternalId}/charges/template` | `retrieveTemplateLoanChargeByLoanExternalId` | Retrieve Loan Charges Template |
| GET | `/v1/loans/{loanId}/charges/{loanChargeId}` | `retrieveOneLoanCharge` | Retrieve a Loan Charge |
| GET | `/v1/loans/{loanId}/charges/external-id/{loanChargeExternalId}` | `retrieveOneLoanChargeByChargeExternalId` | Retrieve a Loan Charge |
| GET | `/v1/loans/external-id/{loanExternalId}/charges/{loanChargeId}` | `retrieveOneLoanChargeByLoanExternalId` | Retrieve a Loan Charge |
| GET | `/v1/loans/external-id/{loanExternalId}/charges/external-id/{loanChargeExternalId}` | `retrieveOneLoanChargeByLoanAndChargeExternalId` | Retrieve a Loan Charge |
| POST | `/v1/loans/{loanId}/charges` | `createOrPayLoanCharge` | Create a Loan Charge (no command provided) or Pay a charge (command=pay) |
| POST | `/v1/loans/external-id/{loanExternalId}/charges` | `executeLoanChargeByLoanExternalId` | Create a Loan Charge (no command provided) or Pay a charge (command=pay) |
| POST | `/v1/loans/{loanId}/charges/{loanChargeId}` | `executeLoanChargeOnExistingCharge` | Pay / Waive / Adjustment for Loan Charge |
| POST | `/v1/loans/{loanId}/charges/external-id/{loanChargeExternalId}` | `executeLoanChargeByChargeExternalId` | Pay / Waive / Adjustment for Loan Charge |
| POST | `/v1/loans/external-id/{loanExternalId}/charges/{loanChargeId}` | `executeLoanChargeByLoanExternalIdOnExistingCharge` | Pay / Waive / Adjustment for Loan Charge |
| POST | `/v1/loans/external-id/{loanExternalId}/charges/external-id/{loanChargeExternalId}` | `executeLoanChargeByLoanAndChargeExternalId` | Pay / Waive / Adjustment for Loan Charge |
| PUT | `/v1/loans/{loanId}/charges/{loanChargeId}` | `updateLoanCharge` | Update a Loan Charge |
| PUT | `/v1/loans/{loanId}/charges/external-id/{loanChargeExternalId}` | `updateLoanChargeByChargeExternalId` | Update a Loan Charge |
| PUT | `/v1/loans/external-id/{loanExternalId}/charges/{loanChargeId}` | `updateLoanChargeByLoanExternalId` | Update a Loan Charge |
| PUT | `/v1/loans/external-id/{loanExternalId}/charges/external-id/{loanChargeExternalId}` | `updateLoanChargeByLoanAndChargeExternalId` | Update a Loan Charge |
| DELETE | `/v1/loans/{loanId}/charges/{loanChargeId}` | `deleteLoanCharge` | Delete a Loan Charge |
| DELETE | `/v1/loans/{loanId}/charges/external-id/{loanChargeExternalId}` | `deleteLoanChargeByChargeExternalId` | Delete a Loan Charge |
| DELETE | `/v1/loans/external-id/{loanExternalId}/charges/{loanChargeId}` | `deleteLoanChargeByLoanExternalId` | Delete a Loan Charge |
| DELETE | `/v1/loans/external-id/{loanExternalId}/charges/external-id/{loanChargeExternalId}` | `deleteLoanChargeByLoanAndChargeExternalId` | Delete a Loan Charge |

## LoanDisbursementDetailApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/LoanDisbursementDetailApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/LoanDisbursementDetailApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| PUT | `/v1/loans/{loanId}/disbursements/{disbursementId}` | `updateDisbursementDate` |  |
| PUT | `/v1/loans/{loanId}/disbursements/editDisbursements` | `addAndDeleteDisbursementDetail` |  |
| GET | `/v1/loans/{loanId}/disbursements/{disbursementId}` | `retriveDetail` |  |

## LoanTransactionsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/LoanTransactionsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/LoanTransactionsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loans/{loanId}/transactions/template` | `retrieveTemplateLoanTransaction` | Retrieve Loan Transaction Template |
| GET | `/v1/loans/external-id/{loanExternalId}/transactions/template` | `retrieveTemplateLoanTransactionByLoanExternalId` | Retrieve Loan Transaction Template |
| GET | `/v1/loans/{loanId}/transactions/{transactionId}` | `retrieveOneLoanTransaction` | Retrieve a Transaction Details |
| GET | `/v1/loans/{loanId}/transactions/external-id/{externalTransactionId}` | `retrieveOneLoanTransactionByExternalId` | Retrieve a Transaction Details |
| GET | `/v1/loans/external-id/{loanExternalId}/transactions/{transactionId}` | `retrieveOneLoanTransactionByLoanExternalId` | Retrieve a Transaction Details |
| GET | `/v1/loans/external-id/{loanExternalId}/transactions/external-id/{externalTransactionId}` | `retrieveOneLoanTransactionByLoanExternalIdAndTransactionExternalId` | Retrieve a Transaction Details |
| GET | `/v1/loans/{loanId}/transactions` | `retrieveAllLoanTransactions` | Retrieve Transactions |
| GET | `/v1/loans/external-id/{loanExternalId}/transactions` | `retrieveAllLoanTransactionsByExternalId` | Retrieve Transactions |
| POST | `/v1/loans/{loanId}/transactions` | `handleCommandsLoanTransaction` | Significant Loan Transactions |
| POST | `/v1/loans/external-id/{loanExternalId}/transactions` | `handleCommandsLoanTransactionByLoanExternalId` | Significant Loan Transactions |
| POST | `/v1/loans/{loanId}/transactions/{transactionId}` | `adjustLoanTransaction` | Adjust a Transaction |
| POST | `/v1/loans/external-id/{loanExternalId}/transactions/{transactionId}` | `adjustLoanTransactionByLoanExternalId` | Adjust a Transaction |
| POST | `/v1/loans/{loanId}/transactions/external-id/{externalTransactionId}` | `adjustLoanTransactionByTransactionExternalId` | Adjust a Transaction |
| POST | `/v1/loans/external-id/{loanExternalId}/transactions/external-id/{externalTransactionId}` | `adjustLoanTransactionByLoanAndTransactionExternalId` | Adjust a Transaction |
| PUT | `/v1/loans/{loanId}/transactions/{transactionId}` | `undoWaiveChargeLoanTransaction` | Undo a Waive Charge Transaction |
| PUT | `/v1/loans/external-id/{loanExternalId}/transactions/{transactionId}` | `undoWaiveChargeLoanTransactionByLoanExternalId` | Undo a Waive Charge Transaction |
| PUT | `/v1/loans/{loanId}/transactions/external-id/{transactionExternalId}` | `undoWaiveChargeLoanTransactionByTransactionExternalId` | Undo a Waive Charge Transaction |
| PUT | `/v1/loans/external-id/{loanExternalId}/transactions/external-id/{transactionExternalId}` | `undoWaiveChargeLoanTransactionByLoanAndTransactionExternalId` | Undo a Waive Charge Transaction |
| GET | `/v1/loans/{loanId}/transactions/reage-preview` | `previewReAgeLoanSchedule` | Preview Re-Age Schedule |
| GET | `/v1/loans/external-id/{loanExternalId}/transactions/reage-preview` | `previewReAgeLoanScheduleByLoanExternalId` | Preview Re-Age Schedule |
| GET | `/v1/loans/{loanId}/transactions/reamortization-preview` | `previewReAmortizeLoanSchedule` | Preview Re-Amortized Schedule |
| GET | `/v1/loans/external-id/{loanExternalId}/transactions/reamortization-preview` | `previewReAmortizeLoanScheduleByLoanExternalId` | Preview Re-amortized Schedule |

## LoansApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/LoansApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/LoansApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loans/{loanId}/template` | `retrieveApprovalTemplate` | Retrieve Loan Approval Template |
| GET | `/v1/loans/template` | `retrieveTemplateLoan` | Retrieve Loan Details Template |
| GET | `/v1/loans/{loanId}` | `retrieveOneLoan` | Retrieve a Loan |
| GET | `/v1/loans` | `retrieveAllLoans` | List Loans |
| POST | `/v1/loans` | `calculateOrSubmitLoanApplication` | Calculate loan repayment schedule  /  Submit a new Loan Application |
| PUT | `/v1/loans/{loanId}` | `updateLoanApplication` | Modify a loan application |
| DELETE | `/v1/loans/{loanId}` | `deleteLoanApplication` | Delete a Loan Application |
| POST | `/v1/loans/{loanId}` | `handleCommandsLoan` | Approve Loan Application  /  Recover Loan Guarantee  /  Undo Loan Application Approval  /  Assign a Loan Officer  /  Unassign a Loan Officer  /  Reject Loan Application  /  Applicant Withdraws from Loan Application  /  Disburse Loan Disburse Loan To Savings Account  /  Undo Loan Disbursal |
| GET | `/v1/loans/downloadtemplate` | `getLoansTemplate` |  |
| GET | `/v1/loans/glimAccount/{glimId}` | `getGlimRepaymentTemplate` |  |
| POST | `/v1/loans/glimAccount/{glimId}` | `handleCommandsGlimLoan` | Approve GLIM Application  /  Undo GLIM Application Approval  /  Reject GLIM Application  /  Disburse Loan Disburse Loan To Savings Account  /  Undo Loan Disbursal |
| GET | `/v1/loans/repayments/downloadtemplate` | `getLoanRepaymentTemplate` |  |
| POST | `/v1/loans/uploadtemplate` | `postLoanTemplate` |  |
| POST | `/v1/loans/repayments/uploadtemplate` | `postLoanRepaymentTemplate` |  |
| GET | `/v1/loans/{loanId}/delinquencytags` | `retrieveDelinquencyTagHistoryLoan` | Retrieve the Loan Delinquency Tag history using the Loan Id |
| GET | `/v1/loans/external-id/{loanExternalId}/template` | `retrieveApprovalTemplateByExternalId` | Retrieve Loan Approval Template |
| GET | `/v1/loans/external-id/{loanExternalId}` | `retrieveOneLoanByExternalId` | Retrieve a Loan |
| PUT | `/v1/loans/external-id/{loanExternalId}` | `updateLoanApplicationByExternalId` | Modify a loan application |
| DELETE | `/v1/loans/external-id/{loanExternalId}` | `deleteLoanApplicationByExternalId` | Delete a Loan Application |
| POST | `/v1/loans/external-id/{loanExternalId}` | `handleCommandsLoanByExternalId` | Approve Loan Application  /  Recover Loan Guarantee  /  Undo Loan Application Approval  /  Assign a Loan Officer  /  Unassign a Loan Officer  /  Reject Loan Application  /  Applicant Withdraws from Loan Application  /  Disburse Loan Disburse Loan To Savings Account  /  Undo Loan Disbursal |
| GET | `/v1/loans/external-id/{loanExternalId}/delinquencytags` | `retrieveDelinquencyTagHistoryLoanByExternalId` | Retrieve the Loan Delinquency Tag history using the Loan Id |
| GET | `/v1/loans/{loanId}/delinquency-actions` | `retrieveDelinquencyActionsLoan` | Retrieve delinquency actions related to the loan |
| GET | `/v1/loans/external-id/{loanExternalId}/delinquency-actions` | `retrieveDelinquencyActionsLoanByExternalId` | Retrieve delinquency actions related to the loan |
| POST | `/v1/loans/{loanId}/delinquency-actions` | `createDelinquencyActionLoan` | Adds a new delinquency action for a loan |
| POST | `/v1/loans/external-id/{loanExternalId}/delinquency-actions` | `createDelinquencyActionLoanByExternalId` | Adds a new delinquency action for a loan |
| PUT | `/v1/loans/{loanId}/approved-amount` | `updateApprovedAmountLoan` | Modifies the approved amount of the loan |
| PUT | `/v1/loans/external-id/{loanExternalId}/approved-amount` | `updateApprovedAmountLoanByExternalId` | Modifies the approved amount of the loan |
| GET | `/v1/loans/{loanId}/approved-amount` | `retrieveApprovedAmountHistoryLoan` | Collects and returns the approved amount modification history for a given loan |
| GET | `/v1/loans/external-id/{loanExternalId}/approved-amount` | `retrieveApprovedAmountHistoryLoanByExternalId` | Collects and returns the approved amount modification history for a given loan |
| PUT | `/v1/loans/{loanId}/available-disbursement-amount` | `updateAvailableDisbursementAmountLoan` | Modifies the available disbursement amount of the loan |
| PUT | `/v1/loans/external-id/{loanExternalId}/available-disbursement-amount` | `updateAvailableDisbursementAmountLoanByExternalId` | Modifies the available disbursement amount of the loan |

## LoansPointInTimeApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/pointintime/LoansPointInTimeApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/api/pointintime/LoansPointInTimeApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loans/at-date/{loanId}` | `retrieveLoanPointInTime` |  |
| GET | `/v1/loans/at-date/external-id/{loanExternalId}` | `retrieveLoanPointInTimeByExternalId` |  |
| POST | `/v1/loans/at-date/search` | `retrieveLoansPointInTime` |  |
| POST | `/v1/loans/at-date/search/external-id` | `retrieveLoansPointInTimeByExternalIds` |  |

## GuarantorsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/guarantor/api/GuarantorsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanaccount/guarantor/api/GuarantorsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loans/{loanId}/guarantors/template` | `newGuarantorTemplate` |  |
| GET | `/v1/loans/{loanId}/guarantors` | `retrieveGuarantorDetails` |  |
| GET | `/v1/loans/{loanId}/guarantors/{guarantorId}` | `retrieveGuarantorDetails` |  |
| POST | `/v1/loans/{loanId}/guarantors` | `createGuarantor` |  |
| PUT | `/v1/loans/{loanId}/guarantors/{guarantorId}` | `updateGuarantor` |  |
| DELETE | `/v1/loans/{loanId}/guarantors/{guarantorId}` | `deleteGuarantor` |  |
| GET | `/v1/loans/{loanId}/guarantors/accounts/template` | `accountsTemplate` |  |
| GET | `/v1/loans/{loanId}/guarantors/downloadtemplate` | `getGuarantorTemplate` |  |
| POST | `/v1/loans/{loanId}/guarantors/uploadtemplate` | `postGuarantorTemplate` |  |

## LoanProductsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanproduct/api/LoanProductsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanproduct/api/LoanProductsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/loanproducts` | `createLoanProduct` | Create a Loan Product |
| GET | `/v1/loanproducts` | `retrieveAllLoanProducts` | List Loan Products |
| GET | `/v1/loanproducts/template` | `retrieveTemplateLoanProduct` |  |
| GET | `/v1/loanproducts/{productId}` | `retrieveOneLoanProduct` | Retrieve a Loan Product |
| PUT | `/v1/loanproducts/{productId}` | `updateLoanProduct` | Update a Loan Product |
| GET | `/v1/loanproducts/external-id/{externalProductId}` | `retrieveLoanProductDetailsByExternalId` |  |
| PUT | `/v1/loanproducts/external-id/{externalProductId}` | `updateLoanProductByExternalId` |  |

## ProductMixApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanproduct/productmix/api/ProductMixApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/loanproduct/productmix/api/ProductMixApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loanproducts/{productId}/productmix` | `retrieveTemplateProductMix` | Retrieve Product Mix Template |
| POST | `/v1/loanproducts/{productId}/productmix` | `createProductMix` | Create Product Mix |
| PUT | `/v1/loanproducts/{productId}/productmix` | `updateProductMix` | Update Product Mix |
| DELETE | `/v1/loanproducts/{productId}/productmix` | `deleteProductMix` | Delete Product Mix |

## MeetingsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/meeting/api/MeetingsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/meeting/api/MeetingsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/{entityType}/{entityId}/meetings/template` | `retrieveTemplateMeeting` | Retrieve Meeting Template |
| GET | `/v1/{entityType}/{entityId}/meetings` | `retrieveAllMeetings` | List Meetings |
| GET | `/v1/{entityType}/{entityId}/meetings/{meetingId}` | `retrieveOneMeeting` | Retrieve a Meeting |
| POST | `/v1/{entityType}/{entityId}/meetings` | `createMeeting` | Create a Meeting |
| PUT | `/v1/{entityType}/{entityId}/meetings/{meetingId}` | `updateMeeting` | Update a Meeting |
| DELETE | `/v1/{entityType}/{entityId}/meetings/{meetingId}` | `deleteMeeting` | Delete a Meeting |
| POST | `/v1/{entityType}/{entityId}/meetings/{meetingId}` | `updateMeetingAttendance` | Update Meeting Attendance |

## NotesApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/note/api/NotesApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/note/api/NotesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/{resourceType:.+}/{resourceId}/notes` | `retrieveNotesByResource` | Retrieve a Resource's description |
| GET | `/v1/{resourceType:.+}/{resourceId}/notes/{noteId}` | `retrieveNote` | Retrieve a Resource Note |
| POST | `/v1/{resourceType:.+}/{resourceId}/notes` | `addNewNote` | Add a Resource Note |
| PUT | `/v1/{resourceType:.+}/{resourceId}/notes/{noteId}` | `updateNote` | Update a Resource Note |
| DELETE | `/v1/{resourceType:.+}/{resourceId}/notes/{noteId}` | `deleteNote` | Delete a Resource Note |

## ProductsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/products/api/ProductsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/products/api/ProductsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/products/{type}/template` | `retrieveTemplateShareProduct` | Retrieve Share Product Template |
| GET | `/v1/products/{type}/{productId}` | `retrieveOneShareProduct` | Retrieve a Share Product |
| GET | `/v1/products/{type}` | `retrieveAllShareProducts` | List Share Products |
| POST | `/v1/products/{type}` | `createShareProduct` | Create a Share Product |
| POST | `/v1/products/{type}/{productId}` | `handleCommandsShareProduct` | Handle Share Product commands |
| PUT | `/v1/products/{type}/{productId}` | `updateShareProduct` | Update a Share Product |

## RateApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/rate/api/RateApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/rate/api/RateApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/rates/{rateId}` | `retrieveOneRate` | Retrieve a rate |
| POST | `/v1/rates` | `createRate` | Create a rate |
| GET | `/v1/rates` | `retrieveAllRates` | List all rates |
| PUT | `/v1/rates/{rateId}` | `updateRate` | Update a rate |

## RepaymentWithPostDatedChecksApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/repaymentwithpostdatedchecks/api/RepaymentWithPostDatedChecksApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/repaymentwithpostdatedchecks/api/RepaymentWithPostDatedChecksApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/loans/{loanId}/postdatedchecks` | `getPostDatedChecks` | Get All Post Dated Checks |
| GET | `/v1/loans/{loanId}/postdatedchecks/{installmentId}` | `getPostDatedCheck` | Get Post Dated Check |
| PUT | `/v1/loans/{loanId}/postdatedchecks/{postDatedCheckId}` | `updatePostDatedChecks` | Update Post Dated Check, Bounced Check |
| DELETE | `/v1/loans/{loanId}/postdatedchecks/{postDatedCheckId}` | `deletePostDatedCheck` | Delete Post Dated Check |

## DepositAccountOnHoldFundTransactionsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/DepositAccountOnHoldFundTransactionsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/DepositAccountOnHoldFundTransactionsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/savingsaccounts/{savingsId}/onholdtransactions` | `retrieveAllDepositAccountOnHoldFundTransactions` | Retrieve deposit account on hold fund transactions |

## FixedDepositAccountTransactionsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/FixedDepositAccountTransactionsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/FixedDepositAccountTransactionsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/fixeddepositaccounts/{fixedDepositAccountId}/transactions/template` | `retrieveTemplateFixedDepositAccountTransaction` | Retrieve Fixed Deposit Account Transaction Template |
| GET | `/v1/fixeddepositaccounts/{fixedDepositAccountId}/transactions` | `retrieveAllFixedDepositAccountTransactions` | List fixed deposit account transactions |
| GET | `/v1/fixeddepositaccounts/{fixedDepositAccountId}/transactions/{transactionId}` | `retrieveOneFixedDepositAccountTransaction` | Retrieve a fixed deposit account transaction |
| POST | `/v1/fixeddepositaccounts/{fixedDepositAccountId}/transactions` | `transaction` |  |
| POST | `/v1/fixeddepositaccounts/{fixedDepositAccountId}/transactions/{transactionId}` | `handleCommandsFixedDepositAccountTransaction` | Adjust Transaction  /  Undo transaction |

## FixedDepositAccountsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/FixedDepositAccountsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/FixedDepositAccountsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/fixeddepositaccounts/template` | `retrieveTemplateFixedDepositAccount` | Retrieve Fixed Deposit Account Template |
| GET | `/v1/fixeddepositaccounts` | `retrieveAllFixedDepositAccounts` | List Fixed deposit applications/accounts |
| POST | `/v1/fixeddepositaccounts` | `createFixedDepositAccount` | Submit new fixed deposit application |
| GET | `/v1/fixeddepositaccounts/{accountId}` | `retrieveOneFixedDepositAccount` | Retrieve a fixed deposit application/account |
| GET | `/v1/fixeddepositaccounts/calculate-fd-interest` | `calculateFixedDepositInterest` |  |
| PUT | `/v1/fixeddepositaccounts/{accountId}` | `updateFixedDepositAccount` | Modify a fixed deposit application |
| POST | `/v1/fixeddepositaccounts/{accountId}` | `handleCommandsFixedDepositAccount` | Approve fixed deposit application  /  Undo approval fixed deposit application  /  Reject fixed deposit application  /  Withdraw fixed deposit application  /  Activate a fixed deposit account  /  Close a fixed deposit account  /  Premature Close a fixed deposit account  /  Calculate Premature amount on Fixed deposit account  /  Calculate Interest on Fixed Deposit Account  /  Post Interest on Fixed Deposit Account |
| DELETE | `/v1/fixeddepositaccounts/{accountId}` | `deleteFixedDepositAccount` | Delete a fixed deposit application |
| GET | `/v1/fixeddepositaccounts/{accountId}/template` | `accountClosureTemplate` |  |
| GET | `/v1/fixeddepositaccounts/downloadtemplate` | `getFixedDepositTemplate` |  |
| POST | `/v1/fixeddepositaccounts/uploadtemplate` | `postFixedDepositTemplate` |  |
| GET | `/v1/fixeddepositaccounts/transaction/downloadtemplate` | `getFixedDepositTransactionTemplate` |  |
| POST | `/v1/fixeddepositaccounts/transaction/uploadtemplate` | `postFixedDepositTransactionTemplate` |  |

## FixedDepositProductsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/FixedDepositProductsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/FixedDepositProductsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/fixeddepositproducts` | `createFixedDepositProduct` | Create a Fixed Deposit Product |
| PUT | `/v1/fixeddepositproducts/{productId}` | `updateFixedDepositProduct` | Update a Fixed Deposit Product |
| GET | `/v1/fixeddepositproducts` | `retrieveAllFixedDepositProducts` | List Fixed Deposit Products |
| GET | `/v1/fixeddepositproducts/{productId}` | `retrieveOneFixedDepositProduct` | Retrieve a Fixed Deposit Product |
| GET | `/v1/fixeddepositproducts/template` | `retrieveTemplateFixedDepositProduct` | Retrieve Fixed Deposit Product Template |
| DELETE | `/v1/fixeddepositproducts/{productId}` | `deleteFixedDepositProduct` | Delete a Fixed Deposit Product |

## InternalSavingsAccountInformationApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/InternalSavingsAccountInformationApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/InternalSavingsAccountInformationApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/internal/savingsaccounts/status/{statusId}` | `getSavingsAccountsByStatus` |  |

## RecurringDepositAccountTransactionsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/RecurringDepositAccountTransactionsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/RecurringDepositAccountTransactionsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/recurringdepositaccounts/{recurringDepositAccountId}/transactions/template` | `retrieveTemplateRecurringDepositAccountTransaction` | Retrieve Recurring Deposit Account Transaction Template |
| GET | `/v1/recurringdepositaccounts/{recurringDepositAccountId}/transactions/{transactionId}` | `retrieveOneRecurringDepositAccountTransaction` | Retrieve Recurring Deposit Account Transaction |
| POST | `/v1/recurringdepositaccounts/{recurringDepositAccountId}/transactions` | `transactionRecurringDepositAccountTransaction` | Deposit Transaction  /  Withdrawal Transaction |
| POST | `/v1/recurringdepositaccounts/{recurringDepositAccountId}/transactions/{transactionId}` | `handleCommandsRecurringDepositAccountTransaction` | Adjust Transaction  /  Undo transaction |

## RecurringDepositAccountsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/RecurringDepositAccountsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/RecurringDepositAccountsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/recurringdepositaccounts/template` | `retrieveTemplateRecurringDepositAccount` | Retrieve recurring Deposit Account Template |
| GET | `/v1/recurringdepositaccounts` | `retrieveAllRecurringDepositAccounts` | List Recurring deposit applications/accounts |
| POST | `/v1/recurringdepositaccounts` | `submitApplicationRecurringDepositAccount` | Submit new recurring deposit application |
| GET | `/v1/recurringdepositaccounts/{accountId}` | `retrieveOneRecurringDepositAccount` | Retrieve a recurring deposit application/account |
| PUT | `/v1/recurringdepositaccounts/{accountId}` | `updateRecurringDepositAccount` | Modify a recurring deposit application |
| POST | `/v1/recurringdepositaccounts/{accountId}` | `handleCommandsRecurringDepositAccount` | Approve recurring deposit application  /  Undo approval recurring deposit application  /  Reject recurring deposit application  /  Withdraw recurring deposit application  /  Activate a recurring deposit account  /  Update the recommended deposit amount for a recurring deposit account  /  Close a recurring deposit account  /  Premature Close a recurring deposit account  /  Calculate Premature amount on Recurring deposit account  /  Calculate Interest on recurring Deposit Account  /  Post Interest on recurring Deposit Account |
| DELETE | `/v1/recurringdepositaccounts/{accountId}` | `deleteRecurringDepositAccount` | Delete a recurring deposit application |
| GET | `/v1/recurringdepositaccounts/{accountId}/template` | `accountClosureTemplateRecurringDepositAccount` | Retrieve recurring deposit account closure template |
| GET | `/v1/recurringdepositaccounts/downloadtemplate` | `getRecurringDepositTemplate` |  |
| POST | `/v1/recurringdepositaccounts/uploadtemplate` | `postRecurringDepositTemplate` |  |
| GET | `/v1/recurringdepositaccounts/transactions/downloadtemplate` | `getRecurringDepositTransactionTemplate` |  |
| POST | `/v1/recurringdepositaccounts/transactions/uploadtemplate` | `postRecurringDepositTransactionsTemplate` |  |

## RecurringDepositProductsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/RecurringDepositProductsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/RecurringDepositProductsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/recurringdepositproducts` | `createRecurringDepositProduct` | Create a Recurring Deposit Product |
| PUT | `/v1/recurringdepositproducts/{productId}` | `updateRecurringDepositProduct` | Update a Recurring Deposit Product |
| GET | `/v1/recurringdepositproducts` | `retrieveAllRecurringDepositProducts` | List Recuring Deposit Products |
| GET | `/v1/recurringdepositproducts/{productId}` | `retrieveOneRecurringDepositProduct` | Retrieve a Recurring Deposit Product |
| GET | `/v1/recurringdepositproducts/template` | `retrieveTemplateRecurringDepositProduct` | Retrieve Recurring Deposit Product Template |
| DELETE | `/v1/recurringdepositproducts/{productId}` | `deleteRecurringDepositProduct` | Delete a Recurring Deposit Product |

## SavingsAccountChargesApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/SavingsAccountChargesApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/SavingsAccountChargesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/savingsaccounts/{savingsAccountId}/charges` | `retrieveAllSavingsAccountCharges` | List Savings Charges |
| GET | `/v1/savingsaccounts/{savingsAccountId}/charges/template` | `retrieveTemplateSavingsAccountCharge` | Retrieve Savings Charges Template |
| GET | `/v1/savingsaccounts/{savingsAccountId}/charges/{savingsAccountChargeId}` | `retrieveOneSavingsAccountCharge` | Retrieve a Savings account Charge |
| POST | `/v1/savingsaccounts/{savingsAccountId}/charges` | `createSavingsAccountCharge` | Create a Savings account Charge |
| PUT | `/v1/savingsaccounts/{savingsAccountId}/charges/{savingsAccountChargeId}` | `updateSavingsAccountCharge` | Update a Savings account Charge |
| POST | `/v1/savingsaccounts/{savingsAccountId}/charges/{savingsAccountChargeId}` | `handleCommandsSavingsAccountCharge` | Pay a Savings account Charge  /  Waive off a Savings account Charge  /  Inactivate a Savings account Charge |
| DELETE | `/v1/savingsaccounts/{savingsAccountId}/charges/{savingsAccountChargeId}` | `deleteSavingsAccountCharge` | Delete a Savings account Charge |

## SavingsAccountTransactionsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/SavingsAccountTransactionsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/SavingsAccountTransactionsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/savingsaccounts/{savingsId}/transactions/template` | `retrieveTemplateSavingsAccountTransaction` | Retrieve a savings account transaction template |
| GET | `/v1/savingsaccounts/external-id/{savingsExternalId}/transactions/template` | `retrieveTemplateSavingsAccountTransactionBySavingsExternalId` | Retrieve a savings account transaction template |
| GET | `/v1/savingsaccounts/{savingsId}/transactions/{transactionId}` | `retrieveOneSavingsAccountTransaction` | Retrieve a savings account transaction |
| GET | `/v1/savingsaccounts/external-id/{savingsExternalId}/transactions/{transactionId}` | `retrieveOneSavingsAccountTransactionBySavingsExternalId` | Retrieve a savings account transaction |
| GET | `/v1/savingsaccounts/{savingsId}/transactions/external-id/{transactionExternalId}` | `retrieveOneSavingsAccountTransactionByExternalId` | Retrieve a savings account transaction by external ID |
| GET | `/v1/savingsaccounts/external-id/{savingsExternalId}/transactions/external-id/{transactionExternalId}` | `retrieveOneSavingsAccountTransactionBySavingsAndTransactionExternalId` | Retrieve a savings account transaction by external ID |
| GET | `/v1/savingsaccounts/{savingsId}/transactions/search` | `searchSavingsAccountTransactions` | Search Savings Account Transactions |
| GET | `/v1/savingsaccounts/external-id/{savingsExternalId}/transactions/search` | `searchSavingsAccountTransactionsBySavingsExternalId` | Search Savings Account Transactions |
| POST | `/v1/savingsaccounts/{savingsId}/transactions/query` | `advancedQuerySavingsAccountTransactions` | Advanced search Savings Account Transactions |
| POST | `/v1/savingsaccounts/external-id/{savingsExternalId}/transactions/query` | `advancedQuerySavingsAccountTransactionsBySavingsExternalId` | Advanced search Savings Account Transactions |
| POST | `/v1/savingsaccounts/{savingsId}/transactions` | `createSavingsAccountTransaction` | Create a savings account transaction |
| POST | `/v1/savingsaccounts/external-id/{savingsExternalId}/transactions` | `createSavingsAccountTransactionBySavingsExternalId` | Create a savings account transaction |
| POST | `/v1/savingsaccounts/{savingsId}/transactions/{transactionId}` | `adjustSavingsAccountTransaction` | Undo/Reverse/Modify/Release Amount transaction API |
| POST | `/v1/savingsaccounts/external-id/{savingsExternalId}/transactions/{transactionId}` | `adjustSavingsAccountTransactionBySavingsExternalId` | Undo/Reverse/Modify/Release Amount transaction API |
| POST | `/v1/savingsaccounts/{savingsId}/transactions/external-id/{transactionExternalId}` | `adjustSavingsAccountTransactionByExternalId` | Undo/Reverse/Modify/Release Amount transaction API by external ID |
| POST | `/v1/savingsaccounts/external-id/{savingsExternalId}/transactions/external-id/{transactionExternalId}` | `adjustSavingsAccountTransactionBySavingsAndTransactionExternalId` | Undo/Reverse/Modify/Release Amount transaction API by external ID |

## SavingsAccountsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/SavingsAccountsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/SavingsAccountsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/savingsaccounts/template` | `retrieveSavingsAccountTemplate` | Retrieve Savings Account Template |
| GET | `/v1/savingsaccounts` | `retrieveAllSavingsAccounts` | List savings applications/accounts |
| POST | `/v1/savingsaccounts` | `submitSavingsApplication` | Submit new savings application |
| POST | `/v1/savingsaccounts/gsim` | `submitGSIMApplication` | Submit a group savings (GSIM) application |
| GET | `/v1/savingsaccounts/{accountId}` | `retrieveSavingsAccount` | Retrieve a savings account |
| GET | `/v1/savingsaccounts/external-id/{externalId}` | `retrieveSavingsAccountByExternalId` | Retrieve a savings account by external ID |
| PUT | `/v1/savingsaccounts/{accountId}` | `updateSavingsAccount` | Modify a savings application  /  Modify savings account withhold tax applicability |
| PUT | `/v1/savingsaccounts/external-id/{externalId}` | `updateSavingsAccountByExternalId` | Modify a savings application  /  Modify savings account withhold tax applicability by externalId |
| PUT | `/v1/savingsaccounts/gsim/{parentAccountId}` | `updateGsim` | Update a group savings (GSIM) application |
| POST | `/v1/savingsaccounts/gsimcommands/{parentAccountId}` | `handleGSIMCommands` | Act on a group savings (GSIM) application |
| POST | `/v1/savingsaccounts/{accountId}` | `handleCommandsSavingsAccount` | Approve savings application  /  Undo approval savings application  /  Assign Savings Officer  /  Unassign Savings Officer  /  Reject savings application  /  Withdraw savings application  /  Activate a savings account  /  Close a savings account  /  Calculate Interest on Savings Account  /  Post Interest on Savings Account  /  Block Savings Account  /  Unblock Savings Account  /  Block Savings Account Credit transactions  /  Unblock Savings Account Credit transactions  /  Block Savings Account Debit transactions  /  Unblock Savings Account debit transactions |
| POST | `/v1/savingsaccounts/external-id/{externalId}` | `handleCommandsSavingsAccountByExternalId` | Approve savings application  /  Undo approval savings application  /  Assign Savings Officer  /  Unassign Savings Officer  /  Reject savings application  /  Withdraw savings application  /  Activate a savings account  /  Close a savings account  /  Calculate Interest on Savings Account  /  Post Interest on Savings Account  /  Block Savings Account  /  Unblock Savings Account  /  Block Savings Account Credit transactions  /  Unblock Savings Account Credit transactions  /  Block Savings Account Debit transactions  /  Unblock Savings Account debit transactions |
| DELETE | `/v1/savingsaccounts/{accountId}` | `deleteSavingsAccount` | Delete a savings application |
| DELETE | `/v1/savingsaccounts/external-id/{externalId}` | `deleteSavingsAccountByExternalId` | Delete a savings application by externalId |
| GET | `/v1/savingsaccounts/downloadtemplate` | `getSavingsTemplate` |  |
| POST | `/v1/savingsaccounts/uploadtemplate` | `postSavingsTemplate` |  |
| GET | `/v1/savingsaccounts/transactions/downloadtemplate` | `getSavingsTransactionTemplate` |  |
| POST | `/v1/savingsaccounts/transactions/uploadtemplate` | `postSavingsTransactionTemplate` |  |

## SavingsProductsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/SavingsProductsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/SavingsProductsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/savingsproducts` | `createSavingsProduct` | Create a Savings Product |
| PUT | `/v1/savingsproducts/{productId}` | `updateSavingsProduct` | Update a Savings Product |
| GET | `/v1/savingsproducts` | `retrieveAllSavingsProducts` | List Savings Products |
| GET | `/v1/savingsproducts/{productId}` | `retrieveOneSavingsProduct` | Retrieve a Savings Product |
| GET | `/v1/savingsproducts/template` | `retrieveTemplateSavingsProduct` | Retrieve Savings Product Template |
| DELETE | `/v1/savingsproducts/{productId}` | `deleteSavingsProduct` | Delete a Savings Product |

## FixedDepositAccountsV2ApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/v2/FixedDepositAccountsV2ApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/v2/FixedDepositAccountsV2ApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v2/fixeddepositaccounts` | `retrieveAllFixedDepositAccountsV2` | List Fixed deposit applications/accounts |

## RecurringDepositAccountsV2ApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/v2/RecurringDepositAccountsV2ApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/savings/api/v2/RecurringDepositAccountsV2ApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v2/recurringdepositaccounts` | `retrieveAllRecurringDepositAccountsV2` | List Recurring deposit applications/accounts |

## SearchApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/search/api/SearchApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/search/api/SearchApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/search/template` | `retrieveAdHocSearchQueryTemplate` | Retrive Adhoc Search query template |
| GET | `/v1/search` | `searchData` | Search Resources |
| POST | `/v1/search/advance` | `advancedSearch` | Adhoc query search |

## ShareDividendApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/shareproducts/api/ShareDividendApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/portfolio/shareproducts/api/ShareDividendApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/shareproduct/{productId}/dividend` | `retrieveAllShareDividends` | List all share dividends |
| GET | `/v1/shareproduct/{productId}/dividend/{dividendId}` | `retrieveOneShareDividend` | Retrieve a share dividend |
| POST | `/v1/shareproduct/{productId}/dividend` | `createShareDividend` | Create a share dividend |
| PUT | `/v1/shareproduct/{productId}/dividend/{dividendId}` | `updateShareDividend` | Update a share dividend |
| DELETE | `/v1/shareproduct/{productId}/dividend/{dividendId}` | `deleteShareDividend` | Delete a share dividend |

## LookupTableApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/spm/api/LookupTableApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/spm/api/LookupTableApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/surveys/{surveyId}/lookuptables` | `fetchLookupTables` | List all Lookup Table entries |
| GET | `/v1/surveys/{surveyId}/lookuptables/{key}` | `findLookupTable` | Retrieve a Lookup Table entry |
| POST | `/v1/surveys/{surveyId}/lookuptables` | `createLookupTable` | Create a Lookup Table entry |

## ScorecardApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/spm/api/ScorecardApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/spm/api/ScorecardApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/surveys/scorecards/{surveyId}` | `findBySurvey` | List all Scorecard entries |
| POST | `/v1/surveys/scorecards/{surveyId}` | `createScorecard` |  |
| GET | `/v1/surveys/scorecards/{surveyId}/clients/{clientId}` | `findBySurveyAndClient` |  |
| GET | `/v1/surveys/scorecards/clients/{clientId}` | `findByClient` |  |

## SpmApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/spm/api/SpmApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/spm/api/SpmApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/surveys` | `fetchAllSurveys` | List all Surveys |
| GET | `/v1/surveys/{id}` | `findSurvey` | Retrieve a Survey |
| POST | `/v1/surveys` | `createSurvey` | Create a Survey |
| PUT | `/v1/surveys/{id}` | `editSurvey` |  |
| POST | `/v1/surveys/{id}` | `activateOrDeactivateSurvey` | Deactivate Survey |

## TemplatesApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/template/api/TemplatesApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/template/api/TemplatesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/templates` | `retrieveAllTemplates` |  |
| GET | `/v1/templates/template` | `retrieveTemplateDetails` |  |
| GET | `/v1/templates/{templateId}` | `retrieveOneTemplate` |  |
| GET | `/v1/templates/{templateId}/template` | `retrieveTemplateById` |  |
| POST | `/v1/templates` | `createTemplate` | Add a UGD |
| PUT | `/v1/templates/{templateId}` | `saveTemplate` | Update a UGD |
| DELETE | `/v1/templates/{templateId}` | `deleteTemplate` | Delete a UGD |
| POST | `/v1/templates/{templateId}` | `mergeTemplate` |  |

## ForgotPasswordApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/useradministration/api/ForgotPasswordApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/useradministration/api/ForgotPasswordApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/password/forgot` | `forgotPassword` | Request password reset |

## PasswordPreferencesApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/useradministration/api/PasswordPreferencesApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/useradministration/api/PasswordPreferencesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/passwordpreferences` | `retrieveAllPasswordPreferences` | List Password Preferences |
| PUT | `/v1/passwordpreferences` | `updatePasswordPreferences` | Update password preferences |
| GET | `/v1/passwordpreferences/template` | `retrieveTemplatePasswordPreferences` | List Application Password validation policies |

## PermissionsApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/useradministration/api/PermissionsApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/useradministration/api/PermissionsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/permissions` | `retrieveAllPermissions` | List Application Permissions |
| PUT | `/v1/permissions` | `updatePermissions` | Enable/Disable Permissions for Maker Checker |

## RolesApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/useradministration/api/RolesApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/useradministration/api/RolesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/roles` | `retrieveAllRoles` | List Roles |
| POST | `/v1/roles` | `createRole` | Create a New Role |
| GET | `/v1/roles/{roleId}` | `retrieveOneRole` | Retrieve a Role |
| POST | `/v1/roles/{roleId}` | `handleCommandsRole` | Enable Role  /  Disable Role |
| PUT | `/v1/roles/{roleId}` | `updateRole` | Update a Role |
| GET | `/v1/roles/{roleId}/permissions` | `retrieveRolePermissions` | Retrieve a Role's Permissions |
| PUT | `/v1/roles/{roleId}/permissions` | `updateRolePermissions` | Update a Role's Permissions |
| DELETE | `/v1/roles/{roleId}` | `deleteRole` | Delete a Role |

## UsersApiResource

源码：[platform/fineract/fineract-provider/src/main/java/org/apache/fineract/useradministration/api/UsersApiResource.java](../../platform/fineract/fineract-provider/src/main/java/org/apache/fineract/useradministration/api/UsersApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/users` | `retrieveAllUsers` | Retrieve list of users |
| GET | `/v1/users/{userId}` | `retrieveOneUser` | Retrieve a User |
| GET | `/v1/users/template` | `retrieveTemplateUser` | Retrieve User Details Template |
| POST | `/v1/users` | `createUser` | Create a User |
| PUT | `/v1/users/{userId}` | `updateUser` | Update a User |
| POST | `/v1/users/{userId}/pwd` | `changePasswordUser` | Change the password of a User |
| DELETE | `/v1/users/{userId}` | `deleteUser` | Delete a User |
| GET | `/v1/users/downloadtemplate` | `getBulkTemplateUser` | Download users template |
| POST | `/v1/users/uploadtemplate` | `postBulkTemplateUser` | Upload users template |

## FloatingRatesApiResource

源码：[platform/fineract/fineract-rates/src/main/java/org/apache/fineract/portfolio/floatingrates/api/FloatingRatesApiResource.java](../../platform/fineract/fineract-rates/src/main/java/org/apache/fineract/portfolio/floatingrates/api/FloatingRatesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/floatingrates` | `createFloatingRate` | Create a new Floating Rate |
| GET | `/v1/floatingrates` | `retrieveAllFloatingRates` | List Floating Rates |
| GET | `/v1/floatingrates/{floatingRateId}` | `retrieveOneFloatingRate` | Retrieve Floating Rate |
| PUT | `/v1/floatingrates/{floatingRateId}` | `updateFloatingRate` | Update Floating Rate |

## AuthenticationApiResource

源码：[platform/fineract/fineract-security/src/main/java/org/apache/fineract/infrastructure/security/api/AuthenticationApiResource.java](../../platform/fineract/fineract-security/src/main/java/org/apache/fineract/infrastructure/security/api/AuthenticationApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/authentication` | `authenticate` | Verify authentication |

## TenantOidcConfigApiResource

源码：[platform/fineract/fineract-security/src/main/java/org/apache/fineract/infrastructure/security/api/TenantOidcConfigApiResource.java](../../platform/fineract/fineract-security/src/main/java/org/apache/fineract/infrastructure/security/api/TenantOidcConfigApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/tenants/{tenantId}/oidc-config` | `retrieve` | Retrieve OIDC configuration for a tenant |
| POST | `/v1/tenants/{tenantId}/oidc-config` | `create` | Create OIDC configuration for a tenant |
| PUT | `/v1/tenants/{tenantId}/oidc-config` | `update` | Update OIDC configuration for a tenant |
| DELETE | `/v1/tenants/{tenantId}/oidc-config` | `delete` | Delete OIDC configuration for a tenant |

## TwoFactorApiResource

源码：[platform/fineract/fineract-security/src/main/java/org/apache/fineract/infrastructure/security/api/TwoFactorApiResource.java](../../platform/fineract/fineract-security/src/main/java/org/apache/fineract/infrastructure/security/api/TwoFactorApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/twofactor` | `getOTPDeliveryMethods` |  |
| POST | `/v1/twofactor` | `requestToken` |  |
| POST | `/v1/twofactor/validate` | `validate` |  |
| POST | `/v1/twofactor/invalidate` | `updateConfiguration` |  |

## TwoFactorConfigurationApiResource

源码：[platform/fineract/fineract-security/src/main/java/org/apache/fineract/infrastructure/security/api/TwoFactorConfigurationApiResource.java](../../platform/fineract/fineract-security/src/main/java/org/apache/fineract/infrastructure/security/api/TwoFactorConfigurationApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/twofactor/configure` | `retrieveAll_4` |  |
| PUT | `/v1/twofactor/configure` | `updateConfiguration_1` |  |

## UserDetailsApiResource

源码：[platform/fineract/fineract-security/src/main/java/org/apache/fineract/infrastructure/security/api/UserDetailsApiResource.java](../../platform/fineract/fineract-security/src/main/java/org/apache/fineract/infrastructure/security/api/UserDetailsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/userdetails` | `fetchAuthenticatedUserData` | Fetch authenticated user details  |

## TaxComponentApiResource

源码：[platform/fineract/fineract-tax/src/main/java/org/apache/fineract/portfolio/tax/api/TaxComponentApiResource.java](../../platform/fineract/fineract-tax/src/main/java/org/apache/fineract/portfolio/tax/api/TaxComponentApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/taxes/component` | `retrieveAllTaxComponents` | List Tax Components |
| GET | `/v1/taxes/component/{taxComponentId}` | `retrieveOneTaxComponent` | Retrieve Tax Component |
| GET | `/v1/taxes/component/template` | `retrieveTemplateTaxComponent` | Retrieve Tax Component Template |
| POST | `/v1/taxes/component` | `createTaxComponent` | Create a new Tax Component |
| PUT | `/v1/taxes/component/{taxComponentId}` | `updateTaxComponent` | Update Tax Component |

## TaxGroupApiResource

源码：[platform/fineract/fineract-tax/src/main/java/org/apache/fineract/portfolio/tax/api/TaxGroupApiResource.java](../../platform/fineract/fineract-tax/src/main/java/org/apache/fineract/portfolio/tax/api/TaxGroupApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/taxes/group` | `retrieveAllTaxGroups` | List Tax Group |
| GET | `/v1/taxes/group/{taxGroupId}` | `retrieveOneTaxGroup` | Retrieve Tax Group |
| GET | `/v1/taxes/group/template` | `retrieveTemplateTaxGroup` | Retrieve Tax Group Template |
| POST | `/v1/taxes/group` | `createTaxGroup` | Create a new Tax Group |
| PUT | `/v1/taxes/group/{taxGroupId}` | `updateTaxGroup` | Update Tax Group |

## InternalWorkingCapitalAccountLockApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/cob/api/InternalWorkingCapitalAccountLockApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/cob/api/InternalWorkingCapitalAccountLockApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/internal/working-capital-loans/{loanId}/place-lock/{lockOwner}` | `placeLockOnWorkingCapitalLoanAccount` |  |

## InternalWorkingCapitalLoanCOBApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/cob/api/InternalWorkingCapitalLoanCOBApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/cob/api/InternalWorkingCapitalLoanCOBApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/internal/working-capital-loans/internal/lastCobRun` | `getLastCobRun` |  |
| DELETE | `/v1/internal/working-capital-loans/internal/lastCobRun` | `deleteLastCobRun` |  |

## InternalWorkingCapitalLoanApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/InternalWorkingCapitalLoanApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/InternalWorkingCapitalLoanApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/internal/working-capital-loans/{loanId}/amortization-schedule` | `generateAmortizationSchedule` | Generate and save Projected Amortization Schedule (testing) |
| POST | `/v1/internal/working-capital-loans/{loanId}/activate` | `activateLoan` | Activate a Working Capital Loan (testing only) |
| POST | `/v1/internal/working-capital-loans/{loanId}/generate-next-delinquency-period` | `generateNextDelinquencyPeriod` | Generate next delinquency range schedule period (testing only) |

## WorkingCapitalLoanAmortizationScheduleApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanAmortizationScheduleApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanAmortizationScheduleApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/working-capital-loans/{loanId}/amortization-schedule` | `retrieveAmortizationSchedule` | Retrieve Projected Amortization Schedule |

## WorkingCapitalLoanApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/working-capital-loans/template` | `retrieveWorkingCapitalLoanTemplate` |  |
| GET | `/v1/working-capital-loans` | `retrieveAllWorkingCapitalLoans` |  |
| GET | `/v1/working-capital-loans/{loanId}` | `retrieveWorkingCapitalLoanById` |  |
| GET | `/v1/working-capital-loans/external-id/{loanExternalId}` | `retrieveWorkingCapitalLoanByExternalId` |  |
| POST | `/v1/working-capital-loans` | `submitWorkingCapitalLoanApplication` |  |
| PUT | `/v1/working-capital-loans/{loanId}` | `modifyWorkingCapitalLoanApplicationById` |  |
| PUT | `/v1/working-capital-loans/{loanId}/mark-as-fraud` | `markWorkingCapitalLoanAsFraudById` |  |
| PUT | `/v1/working-capital-loans/external-id/{loanExternalId}/mark-as-fraud` | `markWorkingCapitalLoanAsFraudByExternalId` |  |
| DELETE | `/v1/working-capital-loans/{loanId}` | `deleteWorkingCapitalLoanApplication` |  |
| PUT | `/v1/working-capital-loans/external-id/{loanExternalId}` | `modifyWorkingCapitalLoanApplicationByExternalId` |  |
| DELETE | `/v1/working-capital-loans/external-id/{loanExternalId}` | `deleteWorkingCapitalLoanApplicationByExternalId` |  |
| GET | `/v1/working-capital-loans/{loanId}/delinquencyrangetags` | `getDelinquencyRangeScheduleTagHistoryById` | Retrieve the Loan Delinquency Tag history using the Loan Id |
| GET | `/v1/working-capital-loans/external-id/{externalId}/delinquencyrangetags` | `getDelinquencyRangeScheduleTagHistoryByExternalId` | Retrieve the Loan Delinquency Tag history using the Loan External Id |
| POST | `/v1/working-capital-loans/{loanId}` | `stateTransitionWorkingCapitalLoanById` |  |
| POST | `/v1/working-capital-loans/external-id/{loanExternalId}` | `stateTransitionWorkingCapitalLoanByExternalId` |  |
| PUT | `/v1/working-capital-loans/{loanId}/discount` | `updateWorkingCapitalLoanDiscountById` |  |
| PUT | `/v1/working-capital-loans/external-id/{loanExternalId}/discount` | `updateWorkingCapitalLoanDiscountByExternalId` |  |
| PUT | `/v1/working-capital-loans/{loanId}/payment-rate` | `updateWorkingCapitalLoanRateById` |  |
| PUT | `/v1/working-capital-loans/external-id/{loanExternalId}/payment-rate` | `updateWorkingCapitalLoanRateByExternalId` |  |
| GET | `/v1/working-capital-loans/{loanId}/rate-changes` | `getWorkingCapitalLoanRateChangeHistoryById` |  |
| GET | `/v1/working-capital-loans/external-id/{loanExternalId}/rate-changes` | `getWorkingCapitalLoanRateChangeHistoryByExternalId` |  |

## WorkingCapitalLoanBreachActionApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanBreachActionApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanBreachActionApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/working-capital-loans/{loanId}/breach-actions` | `createBreachAction` | Create Breach Action |
| POST | `/v1/working-capital-loans/external-id/{loanExternalId}/breach-actions` | `createBreachActionByExternalId` |  |
| GET | `/v1/working-capital-loans/{loanId}/breach-actions` | `retrieveBreachActions` | Retrieve Breach Actions |
| GET | `/v1/working-capital-loans/external-id/{loanExternalId}/breach-actions` | `retrieveBreachActionsByExternalId` |  |

## WorkingCapitalLoanBreachScheduleApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanBreachScheduleApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanBreachScheduleApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/working-capital-loans/{loanId}/breach-schedule` | `retrieveBreachSchedule` | Retrieve Breach Schedule |

## WorkingCapitalLoanChargesApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanChargesApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanChargesApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/working-capital-loans/{loanId}/charges/template` | `retrieveTemplateWorkingCapitalLoanCharge` | Retrieve Working Capital Loan Charges Template |
| GET | `/v1/working-capital-loans/external-id/{loanExternalId}/charges/template` | `retrieveTemplateWorkingCapitalLoanChargeByLoanExternalId` | Retrieve Working Capital Loan Charges Template |
| POST | `/v1/working-capital-loans/{loanId}/charges` | `createLoanCharge` | Create a Loan Charge  |
| POST | `/v1/working-capital-loans/external-id/{loanExternalId}/charges` | `executeWorkingCapitalLoanChargeByLoanExternalId` | Create a Loan Charge (no command provided) |
| POST | `/v1/working-capital-loans/{loanId}/charges/{loanChargeId}` | `adjustLoanCharge` | Adjust or Waive a Working Capital Loan Charge |
| POST | `/v1/working-capital-loans/{loanId}/charges/external-id/{loanChargeExternalId}` | `adjustLoanChargeByChargeExternalId` | Adjust or Waive a Working Capital Loan Charge by Charge External Id |
| POST | `/v1/working-capital-loans/external-id/{loanExternalId}/charges/{loanChargeId}` | `adjustLoanChargeByLoanExternalId` | Adjust or Waive a Working Capital Loan Charge by Loan External Id |
| POST | `/v1/working-capital-loans/external-id/{loanExternalId}/charges/external-id/{loanChargeExternalId}` | `adjustLoanChargeByLoanAndChargeExternalId` | Adjust or Waive a Working Capital Loan Charge by Loan and Charge External Ids |
| GET | `/v1/working-capital-loans/{loanId}/charges` | `retrieveAllWorkingCapitalLoanChargesByLoanId` | List Loan Charges |
| GET | `/v1/working-capital-loans/external-id/{loanExternalId}/charges` | `retrieveAllWorkingCapitalLoanChargesByLoanExternalId` | List Loan Charges |
| GET | `/v1/working-capital-loans/{loanId}/charges/{loanChargeId}` | `retrieveWorkingCapitalLoanCharge` | Retrieve a Loan Charge |
| GET | `/v1/working-capital-loans/{loanId}/charges/external-id/{loanChargeExternalId}` | `retrieveWorkingCapitalLoanChargeByChargeExternalId` | Retrieve a Loan Charge |
| GET | `/v1/working-capital-loans/external-id/{loanExternalId}/charges/{loanChargeId}` | `retrieveWorkingCapitalLoanChargeByLoanExternalId` | Retrieve a Loan Charge |
| GET | `/v1/working-capital-loans/external-id/{loanExternalId}/charges/external-id/{loanChargeExternalId}` | `retrieveWorkingCapitalLoanChargeByLoanAndChargeExternalId` | Retrieve a Loan Charge |

## WorkingCapitalLoanDelinquencyActionApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanDelinquencyActionApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanDelinquencyActionApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/working-capital-loans/{loanId}/delinquency-actions` | `createDelinquencyAction` | Create Delinquency Action |
| POST | `/v1/working-capital-loans/external-id/{loanExternalId}/delinquency-actions` | `createDelinquencyActionByExternalId` |  |
| GET | `/v1/working-capital-loans/{loanId}/delinquency-actions` | `retrieveDelinquencyActions` | Retrieve Delinquency Actions |
| GET | `/v1/working-capital-loans/external-id/{loanExternalId}/delinquency-actions` | `retrieveDelinquencyActionsByExternalId` |  |

## WorkingCapitalLoanDelinquencyRangeScheduleApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanDelinquencyRangeScheduleApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanDelinquencyRangeScheduleApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/working-capital-loans/{loanId}/delinquency-range-schedule` | `retrieveDelinquencyRangeSchedule` | Retrieve Delinquency Range Schedule |

## WorkingCapitalLoanNearBreachActionApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanNearBreachActionApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanNearBreachActionApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/working-capital-loans/{loanId}/near-breach-actions` | `createWorkingCapitalLoanNearBreachActionById` |  |
| POST | `/v1/working-capital-loans/external-id/{loanExternalId}/near-breach-actions` | `createWorkingCapitalLoanNearBreachActionByExternalId` |  |
| GET | `/v1/working-capital-loans/{loanId}/near-breach-actions` | `getWorkingCapitalLoanNearBreachActionsById` |  |
| GET | `/v1/working-capital-loans/external-id/{loanExternalId}/near-breach-actions` | `getWorkingCapitalLoanNearBreachActionsByExternalId` |  |

## WorkingCapitalLoanTransactionsApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanTransactionsApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloan/api/WorkingCapitalLoanTransactionsApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/working-capital-loans/{loanId}/transactions` | `retrieveWorkingCapitalLoanTransactionsById` |  |
| GET | `/v1/working-capital-loans/external-id/{loanExternalId}/transactions` | `retrieveWorkingCapitalLoanTransactionsByExternalId` |  |
| GET | `/v1/working-capital-loans/{loanId}/transactions/{transactionId}` | `retrieveWorkingCapitalLoanTransactionById` |  |
| GET | `/v1/working-capital-loans/{loanId}/transactions/external-id/{externalTransactionId}` | `retrieveWorkingCapitalLoanTransactionByExternalTransactionId` |  |
| GET | `/v1/working-capital-loans/external-id/{loanExternalId}/transactions/{transactionId}` | `retrieveWorkingCapitalLoanTransactionByExternalLoanIdAndTransactionId` |  |
| GET | `/v1/working-capital-loans/external-id/{loanExternalId}/transactions/external-id/{externalTransactionId}` | `retrieveWorkingCapitalLoanTransactionByExternalLoanIdAndExternalTransactionId` |  |
| GET | `/v1/working-capital-loans/{loanId}/template` | `retrieveWorkingCapitalLoanActionTemplate` |  |
| POST | `/v1/working-capital-loans/{loanId}/transactions` | `executeWorkingCapitalLoanTransactionById` |  |
| POST | `/v1/working-capital-loans/external-id/{loanExternalId}/transactions` | `executeWorkingCapitalLoanTransactionByExternalId` |  |
| POST | `/v1/working-capital-loans/{loanId}/transactions/{transactionId}` | `executeWorkingCapitalLoanTransactionCommandByLoanIdTransactionId` |  |
| POST | `/v1/working-capital-loans/{loanId}/transactions/external-id/{transactionExternalId}` | `executeWorkingCapitalLoanTransactionCommandByLoanIdTransactionExternalId` |  |
| GET | `/v1/working-capital-loans/{loanId}/transactions/template` | `getWorkingCapitalLoanTransactionTemplateById` |  |
| GET | `/v1/working-capital-loans/external-id/{loanExternalId}/transactions/template` | `getWorkingCapitalLoanTransactionTemplateByExternalId` |  |
| POST | `/v1/working-capital-loans/external-id/{loanExternalId}/transactions/{transactionId}` | `executeWorkingCapitalLoanTransactionCommandByLoanExternalIdTransactionId` |  |
| POST | `/v1/working-capital-loans/external-id/{loanExternalId}/transactions/external-id/{transactionExternalId}` | `executeWorkingCapitalLoanTransactionCommandByLoanExternalIdTransactionExternalId` |  |

## WorkingCapitalBreachApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloanbreach/api/WorkingCapitalBreachApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloanbreach/api/WorkingCapitalBreachApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/working-capital/breach/template` | `retrieveWorkingCapitalBreachTemplate` |  |
| GET | `/v1/working-capital/breach/breaches` | `retrieveAllWorkingCapitalBreaches` |  |
| GET | `/v1/working-capital/breach/breaches/{breachId}` | `retrieveWorkingCapitalBreach` |  |
| POST | `/v1/working-capital/breach/breaches` | `createWorkingCapitalBreach` |  |
| PUT | `/v1/working-capital/breach/breaches/{breachId}` | `updateWorkingCapitalBreach` |  |
| DELETE | `/v1/working-capital/breach/breaches/{breachId}` | `deleteWorkingCapitalBreach` |  |

## WorkingCapitalNearBreachApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloannearbreach/api/WorkingCapitalNearBreachApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloannearbreach/api/WorkingCapitalNearBreachApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| GET | `/v1/working-capital/near-breach` | `retrieveAllWorkingCapitalNearBreaches` |  |
| GET | `/v1/working-capital/near-breach/{breachId}` | `retrieveWorkingCapitalNearBreach` |  |
| POST | `/v1/working-capital/near-breach` | `createWorkingCapitalNearBreach` |  |
| PUT | `/v1/working-capital/near-breach/{breachId}` | `updateWorkingCapitalNearBreach` |  |
| DELETE | `/v1/working-capital/near-breach/{breachId}` | `deleteWorkingCapitalNearBreach` |  |

## WorkingCapitalLoanProductApiResource

源码：[platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloanproduct/api/WorkingCapitalLoanProductApiResource.java](../../platform/fineract/fineract-working-capital-loan/src/main/java/org/apache/fineract/portfolio/workingcapitalloanproduct/api/WorkingCapitalLoanProductApiResource.java)

| 方法 | 路径 | operationId / 方法名 | 用途（源码摘要） |
| --- | --- | --- | --- |
| POST | `/v1/working-capital-loan-products` | `createWorkingCapitalLoanProduct` |  |
| GET | `/v1/working-capital-loan-products` | `retrieveAllWorkingCapitalLoanProducts` |  |
| GET | `/v1/working-capital-loan-products/template` | `retrieveTemplateWorkingCapitalLoanProduct` | Retrieve Working Capital Loan Product Details Template |
| GET | `/v1/working-capital-loan-products/{productId}` | `retrieveOneWorkingCapitalLoanProduct` | Retrieve a Working Capital Loan Product |
| PUT | `/v1/working-capital-loan-products/{productId}` | `updateWorkingCapitalLoanProduct` | Update a Working Capital Loan Product |
| DELETE | `/v1/working-capital-loan-products/{productId}` | `deleteWorkingCapitalLoanProduct` | Delete a Working Capital Loan Product |
| DELETE | `/v1/working-capital-loan-products/external-id/{externalProductId}` | `deleteWorkingCapitalLoanProductByExternalId` | Delete a Working Capital Loan Product |
| GET | `/v1/working-capital-loan-products/external-id/{externalProductId}` | `retrieveOneWorkingCapitalLoanProductByExternalId` | Retrieve a Working Capital Loan Product |
| PUT | `/v1/working-capital-loan-products/external-id/{externalProductId}` | `updateWorkingCapitalLoanProductByExternalId` | Update a Working Capital Loan Product |
