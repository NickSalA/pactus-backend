# CHANGELOG

<!-- version list -->

## v0.33.2 (2026-04-16)

### Bug Fixes

- Update Dockerfile to install native dependencies for WeasyPrint
  ([`687200e`](https://github.com/NickSalA/ContractAI-Backend/commit/687200e5d31d6eaddbd719a7ae36c5a805a7bf70))


## v0.33.1 (2026-04-16)

### Bug Fixes

- Update .dockerignore and refactor config.py for secret retrieval
  ([`949ab2e`](https://github.com/NickSalA/ContractAI-Backend/commit/949ab2ebef1765512e85881fe6b611c69a5e9f32))


## v0.33.0 (2026-04-15)

### Features

- Enhance template processing with raw field issue detection and placeholder normalization
  ([`2729e98`](https://github.com/NickSalA/ContractAI-Backend/commit/2729e98e491b3bc4e6ecd9147e3b246117ad5c92))


## v0.32.0 (2026-04-15)

### Bug Fixes

- Update configuration to use placeholders for sensitive keys and disable secret retrieval
  ([`4cdc340`](https://github.com/NickSalA/ContractAI-Backend/commit/4cdc340d5e0f0b83be79a4fafdb859365918df39))

- Update CORS settings to allow all origins and format CORS_ORIGINS list
  ([`b29bbf6`](https://github.com/NickSalA/ContractAI-Backend/commit/b29bbf6864c0c5d6c86d785838b8efc2c7696353))

- Update query parameters to use None as default for template format endpoints
  ([`5e35221`](https://github.com/NickSalA/ContractAI-Backend/commit/5e3522196d00a1f2227bed911cffa17b4ce8edb7))

### Features

- Add organization context to file uploads
  ([`cd7e341`](https://github.com/NickSalA/ContractAI-Backend/commit/cd7e34175837638d01517935b445ad7eab90ce7f))

- Add publish method to ITemplateRepository and implement in SQLModelTemplateRepository
  ([`ac77e13`](https://github.com/NickSalA/ContractAI-Backend/commit/ac77e13b472d8f06333950ef1e4e693ec8734cbd))

- Add support for time fields and enhance template processing with new placeholder normalization
  ([`0795ba6`](https://github.com/NickSalA/ContractAI-Backend/commit/0795ba6a792e043f514077434caad2e2952082e1))

- Enhance template authoring service with validation retries and scoring for classifier patterns
  ([`5d60fa9`](https://github.com/NickSalA/ContractAI-Backend/commit/5d60fa9a8b4fa24e6bad892933e9ef6bbb8fee5b))

- Enhance template content synchronization and rendering
  ([`10aa040`](https://github.com/NickSalA/ContractAI-Backend/commit/10aa040af9ce671a890955593bcc5986edf4ae99))

- Enhance template generation with document type and format code support
  ([`52be304`](https://github.com/NickSalA/ContractAI-Backend/commit/52be3045431a55c1ee2c9fbab10b78bec4d79b94))

- Enhance template validation and generation with contract date mapping
  ([`fab91a2`](https://github.com/NickSalA/ContractAI-Backend/commit/fab91a2a6e41d454eac6604c95df9a0bfd1829d4))

- Implement document type-based access control and dynamic date resolution for template generation
  ([`7d1567c`](https://github.com/NickSalA/ContractAI-Backend/commit/7d1567c7de3d9d0d9a2e8131c34f5d7ab11c370a))

- Implement template format repository and integrate into template services
  ([`7c7ccca`](https://github.com/NickSalA/ContractAI-Backend/commit/7c7ccca084d952fa4670c03e6f9b4b624641c5eb))


## v0.31.2 (2026-04-14)

### Bug Fixes

- Dehardcode azure openai settings
  ([`4d5a674`](https://github.com/NickSalA/ContractAI-Backend/commit/4d5a674937bd1ff77f225da7e51e05f5e9fda545))


## v0.31.1 (2026-04-14)

### Bug Fixes

- Change extraction process and chatbot capabilities
  ([`31ad42e`](https://github.com/NickSalA/ContractAI-Backend/commit/31ad42e4669249b8e0cc7af7814270b31afab7b0))


## v0.31.0 (2026-04-11)

### Features

- Update Dockerfile for improved dependency management and add .dockerignore
  ([`1b480af`](https://github.com/NickSalA/ContractAI-Backend/commit/1b480af28f3ee1225953718ce844962d87da219d))


## v0.30.1 (2026-04-11)

### Bug Fixes

- Enhance permissions agent
  ([`5929547`](https://github.com/NickSalA/ContractAI-Backend/commit/5929547bdad08fb81c793da3b34465c1bd686f7e))


## v0.30.0 (2026-04-11)

### Features

- Switch from Azure OpenAI to Google Generative AI for template draft generation
  ([`a33da84`](https://github.com/NickSalA/ContractAI-Backend/commit/a33da84dc3a6be88f4c0bf85dd3b7e01bd3f1c08))


## v0.29.0 (2026-04-10)

### Features

- Migrate to Azure OpenAI for chatbot and template draft generation
  ([`65d4461`](https://github.com/NickSalA/ContractAI-Backend/commit/65d44614699a29ab505ce852e7fe2cfefc16238a))


## v0.28.0 (2026-04-10)

### Features

- Integrate multi agent system
  ([`108a8ac`](https://github.com/NickSalA/ContractAI-Backend/commit/108a8aca0c5840a57b55bc82086e54b5030b1d75))


## v0.27.0 (2026-04-10)

### Features

- Implement Azure Key Vault integration for secret management and update configuration settings
  ([`56fa6de`](https://github.com/NickSalA/ContractAI-Backend/commit/56fa6de5f01b1c1ec51e7b46a1e4484f2906d614))


## v0.26.0 (2026-04-09)

### Features

- Implement role-based access control for document notifications and restrict email alert triggers
  to administrators
  ([`3bc22e2`](https://github.com/NickSalA/ContractAI-Backend/commit/3bc22e2118d9b01875e388a674f5890b096a88b0))

### Refactoring

- Decouple service catalog from documents, add folder deletion constraints, and expand test coverage
  for organizations and notifications.
  ([`e5ee8cf`](https://github.com/NickSalA/ContractAI-Backend/commit/e5ee8cf53762f3fc041d33e16157e406a79682dd))

### Testing

- Implement comprehensive unit test suite for notification and folder management modules
  ([`250da47`](https://github.com/NickSalA/ContractAI-Backend/commit/250da47c17833226f4d5dd98efc8246cf981b5ba))


## v0.25.0 (2026-04-08)

### Features

- Implement catalog and folders modules, refactor document services, and update authentication logic
  ([`b24f778`](https://github.com/NickSalA/ContractAI-Backend/commit/b24f7780a007b37db7de08d06c2210b34ccfa390))


## v0.24.0 (2026-04-08)

### Features

- Implement role-manager access control for document imports
  ([`4ef2711`](https://github.com/NickSalA/ContractAI-Backend/commit/4ef2711fe9dfeacd5571113eaa5091ed8f3a81ff))


## v0.23.0 (2026-04-08)

### Features

- Register organizations router, implement member service, and update auth service to enforce
  admin-only user registration
  ([`fd7eee5`](https://github.com/NickSalA/ContractAI-Backend/commit/fd7eee5d36b185dcf70c3593ea7f8218d1b6b8bd))


## v0.22.0 (2026-04-08)

### Features

- Implement role-HR access control for document operations based on contract type
  ([`f72194f`](https://github.com/NickSalA/ContractAI-Backend/commit/f72194f6514e4aa915a6260b183ddb7ee3c69e63))


## v0.21.0 (2026-04-08)

### Features

- Restrict worker document access
  ([`a2fd269`](https://github.com/NickSalA/ContractAI-Backend/commit/a2fd26958e15654ad23706df2ef6b25667b7622f))


## v0.20.0 (2026-04-08)

### Features

- Implement template content synchronization and enhance error handling in template operations
  ([`2162bd8`](https://github.com/NickSalA/ContractAI-Backend/commit/2162bd8081c60b849c3dab8a55780a1240f8a123))


## v0.19.0 (2026-04-08)

### Features

- Enhance markdown extraction and processing for contract templates
  ([`697a789`](https://github.com/NickSalA/ContractAI-Backend/commit/697a78938363ca67243d9c9c651c672c4db5b8af))


## v0.18.0 (2026-04-07)

### Features

- Enhance template generation with improved request handling and response serialization
  ([`2e8ff78`](https://github.com/NickSalA/ContractAI-Backend/commit/2e8ff78d96eea8af1cc49c34d08c6e53df0988ae))


## v0.17.0 (2026-04-06)

### Features

- Implement configurable notification rules and extend user entity with notification preferences
  ([`9a49981`](https://github.com/NickSalA/ContractAI-Backend/commit/9a499819b641816ed32041aab8d046bc9de91712))


## v0.16.0 (2026-04-06)

### Features

- Refactor template draft generation to support organization context and streamline request handling
  ([`f00fd51`](https://github.com/NickSalA/ContractAI-Backend/commit/f00fd51ed031ef79bfb107aa77ca1360dc14e8a4))


## v0.15.0 (2026-04-05)

### Features

- Enhance template management with draft generation, state handling, and API updates
  ([`d77c15a`](https://github.com/NickSalA/ContractAI-Backend/commit/d77c15a21fd585a406c888b276567b0f7d687ee8))


## v0.14.0 (2026-04-04)

### Features

- Implement template draft generation functionality
  ([`5faf08f`](https://github.com/NickSalA/ContractAI-Backend/commit/5faf08f640ecc7d66751d86f8e2a213d0264b576))

### Testing

- Add unit tests for chatbot, integrations, notifications, organizations, templates, and users
  ([`953e916`](https://github.com/NickSalA/ContractAI-Backend/commit/953e91637bb32ea1387e83bcb311bf7e2c1d3001))


## v0.13.5 (2026-03-31)

### Bug Fixes

- Add more agent capabilities
  ([`50b0dd5`](https://github.com/NickSalA/ContractAI-Backend/commit/50b0dd5cee7820fc197f354535fc4683f921d726))


## v0.13.4 (2026-03-31)

### Bug Fixes

- Change on document module
  ([`e50a7be`](https://github.com/NickSalA/ContractAI-Backend/commit/e50a7be80f1bdea043c3095ef2b41420971110fd))


## v0.13.3 (2026-03-30)

### Bug Fixes

- Change qdrant session managing and database pooling
  ([`f0d914d`](https://github.com/NickSalA/ContractAI-Backend/commit/f0d914db168f05826a0904782656e19ebe2b4cb0))

### Refactoring

- Enhance error logging in PostgresBaseRepository and update organization service documentation
  ([`9d0cf3f`](https://github.com/NickSalA/ContractAI-Backend/commit/9d0cf3f30563ae5d548f935fc738d42c1fcab318))

- Implement structured contract query DTO and refactor related services
  ([`74311a5`](https://github.com/NickSalA/ContractAI-Backend/commit/74311a54da8d1c9ac04f7a06d6fc82be235f224d))


## v0.13.2 (2026-03-28)

### Bug Fixes

- Change prompt rules for better responses
  ([`77e30a9`](https://github.com/NickSalA/ContractAI-Backend/commit/77e30a9665a03fdb32a5989faa0af1757d2b90f2))


## v0.13.1 (2026-03-28)


## v0.13.0 (2026-03-28)


## v0.12.1 (2026-03-28)


## v0.12.0 (2026-03-28)

### Features

- **templates**: Add client contract template
  ([`946c5b3`](https://github.com/NickSalA/ContractAI-Backend/commit/946c5b3aee2016131e67c93f757641576025723c))

### Refactoring

- Refactor document services and enhance validation
  ([`26a9285`](https://github.com/NickSalA/ContractAI-Backend/commit/26a9285940061252e376825cc9f595bf07ebe4cb))


## v0.11.1 (2026-03-27)


## v0.11.0 (2026-03-27)

### Features

- Add ingest flow for drive integration
  ([`2cdb9ec`](https://github.com/NickSalA/ContractAI-Backend/commit/2cdb9ec865f9a95339a418ebb782d7e03a0c8f77))


## v0.10.2 (2026-03-27)

### Bug Fixes

- Apply barrel pattern for chatbot and integrations modules
  ([`4c2bff1`](https://github.com/NickSalA/ContractAI-Backend/commit/4c2bff1b0db95f86762fe9b7bde068473c20fa94))


## v0.10.1 (2026-03-27)

### Bug Fixes

- Limit pool connections for db
  ([`d404217`](https://github.com/NickSalA/ContractAI-Backend/commit/d4042179b0706ee613815d6a92d4beb0e1bd4ace))


## v0.10.0 (2026-03-27)


## v0.9.1 (2026-03-27)

### Bug Fixes

- Add markdown2 and weasyprint dependencies in pyproject.toml and uv.lock
  ([`08d0e68`](https://github.com/NickSalA/ContractAI-Backend/commit/08d0e68b52173b93cbdc3a14aae0ea476b1926a2))

### Refactoring

- Reorganize import statements in routers and template_service modules
  ([`cbd95d6`](https://github.com/NickSalA/ContractAI-Backend/commit/cbd95d6eb711cc00e29dbe51437855c6958e9013))


## v0.9.0 (2026-03-27)

### Features

- Implement template generation API and refactor document handling
  ([`d745da0`](https://github.com/NickSalA/ContractAI-Backend/commit/d745da079dae64468d728714a65d3d7ff7f76cbe))


## v0.8.0 (2026-03-27)

### Features

- Add OrganizationModuleAdapter to connect templates with organization service
  ([`8fe2d72`](https://github.com/NickSalA/ContractAI-Backend/commit/8fe2d7231be4db1ff78bed67562a75558ade80c6))


## v0.7.1 (2026-03-27)


## v0.7.0 (2026-03-26)


## v0.6.0 (2026-03-26)

### Features

- Implement document generation and template management
  ([`a1f7a3c`](https://github.com/NickSalA/ContractAI-Backend/commit/a1f7a3c800ce916d6aabe91701281ce5329e464a))


## v0.5.0 (2026-03-26)

### Bug Fixes

- **checkpointer**: Corregir lógica de guardado
  ([`a704192`](https://github.com/NickSalA/ContractAI-Backend/commit/a7041929e2b85f911ada45aff318a1a7dba247c9))

### Features

- Add template management and extraction scripts
  ([`69ec938`](https://github.com/NickSalA/ContractAI-Backend/commit/69ec938761eaf52d3d521af1909fd2f6ad74eb1f))


## v0.4.1 (2026-03-25)


## v0.4.0 (2026-03-25)

### Features

- Add integration module
  ([`0937b44`](https://github.com/NickSalA/ContractAI-Backend/commit/0937b4472e6dbe3d330690c93e2c0d49bdcad14b))

### Refactoring

- Enhance chatbot and user management with improved dependency injection and error handling
  ([`b0f1f1b`](https://github.com/NickSalA/ContractAI-Backend/commit/b0f1f1bab05e05728708924e4970c6b34eb076b7))

- Update API schemas and router definitions for improved clarity and structure
  ([`1a089ae`](https://github.com/NickSalA/ContractAI-Backend/commit/1a089aea5b53e218856cdc4780296f1f0f7533d8))


## v0.3.1 (2026-03-25)


## v0.2.3 (2026-03-24)

### Bug Fixes

- Add suggestion when agent don't find a file on prompt
  ([`b33527c`](https://github.com/NickSalA/ContractAI-Backend/commit/b33527cf00f078e62a9bcffc4a9bb3670710ad6c))


## v0.2.2 (2026-03-24)


## v0.2.0 (2026-03-23)

### Chores

- Update dependencies and improve VSCode settings
  ([`69e3d96`](https://github.com/NickSalA/ContractAI-Backend/commit/69e3d967ca42e27c101b2bdbfe3726de652bfe8a))

### Features

- Add persistence for chatbot
  ([`b48a76c`](https://github.com/NickSalA/ContractAI-Backend/commit/b48a76c064554ec5e764d024d5fad94691445406))

### Refactoring

- Enhance chatbot model invocation and tool creation, improving async handling and dependency
  injection
  ([`9c4f0ad`](https://github.com/NickSalA/ContractAI-Backend/commit/9c4f0ad2b78ec20d05509d0b8b264aa41668941e))

- Enhance error handling and response types across document services and repositories
  ([`f8fa8d5`](https://github.com/NickSalA/ContractAI-Backend/commit/f8fa8d59c863e32ec933c3ba725aa3381941d240))

- Enhance exception handling in document module, adding specific error classes for better clarity
  and management
  ([`a03f93a`](https://github.com/NickSalA/ContractAI-Backend/commit/a03f93a5dccbaf0440c655010b9b338013708d4c))

- Introduce DocumentValidationError for improved document validation handling
  ([`1524fc5`](https://github.com/NickSalA/ContractAI-Backend/commit/1524fc59ed127718e2e83807f5171883a0a9d555))

- Reorganize database module structure, moving to infrastructure and updating imports
  ([`01c4dad`](https://github.com/NickSalA/ContractAI-Backend/commit/01c4dad663bfe30926467e513cfb050396341044))

- Reorganize llm_provider and vector_repo interfaces, update imports
  ([`a684b12`](https://github.com/NickSalA/ContractAI-Backend/commit/a684b121fd05cd2bafc7143c47be761fca381760))

- Restructure chatbot module, enhance dependency injection and improve LLM integration
  ([`f148d30`](https://github.com/NickSalA/ContractAI-Backend/commit/f148d30e61c616d44f739a4688cd93b7debf47a4))

- Update chatbot architecture by introducing ChatbotService, enhancing message processing and
  dependency management
  ([`656c89a`](https://github.com/NickSalA/ContractAI-Backend/commit/656c89a872282d6d639d3ead8d134fd870051b9e))

- Update DocumentTable validation and improve test cases for currency handling
  ([`f8ccc5c`](https://github.com/NickSalA/ContractAI-Backend/commit/f8ccc5caa406419cfa1032640126fabf544327e1))

### Testing

- Add unit tests for DocumentService, domain entities, and infrastructure components
  ([`0833014`](https://github.com/NickSalA/ContractAI-Backend/commit/0833014ebf90610a851f48b936ea6480c81d3fe3))


## v0.1.6 (2026-03-20)

### Bug Fixes

- Update prompt and visualizer for token costs
  ([`66e472a`](https://github.com/NickSalA/ContractAI-Backend/commit/66e472a69eab59e5c0ca593a575e326eca1fc80b))


## v0.1.5 (2026-03-20)

### Bug Fixes

- Define ContractAI system prompt for chatbot agent
  ([`5f38d52`](https://github.com/NickSalA/ContractAI-Backend/commit/5f38d52caa67a740e7cba539bc0d312baca9be57))


## v0.1.4 (2026-03-20)

### Bug Fixes

- Add ordering to get_all method query
  ([`eff189a`](https://github.com/NickSalA/ContractAI-Backend/commit/eff189a4a1427d58ffd9f4ad882b6b8702874e1a))


## v0.1.3 (2026-03-20)

### Bug Fixes

- Initialize file_data for metadata-only document updates
  ([`d63da6a`](https://github.com/NickSalA/ContractAI-Backend/commit/d63da6a63f148356cbed7c9947cb08f69c2d6ff0))

### Continuous Integration

- Add commit author configuration for semantic release
  ([`e61cb5c`](https://github.com/NickSalA/ContractAI-Backend/commit/e61cb5c712a6b3a62b2a693ed77ecbe2d3c98073))

### Refactoring

- Update return type of get_all method to use Sequence
  ([`44b037c`](https://github.com/NickSalA/ContractAI-Backend/commit/44b037c49e06f0d2b4a7b27fa3e7e59aeeb8943d))


## v0.1.2 (2026-03-20)

### Bug Fixes

- Update semantic release configuration to use version_variables
  ([`b067b9b`](https://github.com/NickSalA/ContractAI-Backend/commit/b067b9bdacc285f026e348111498541c7484ade4))


## v0.1.1 (2026-03-20)

### Bug Fixes

- Test
  ([`43c71f1`](https://github.com/NickSalA/ContractAI-Backend/commit/43c71f10032d100d4745f4a4d59a9bdf510e0b0a))

### Continuous Integration

- Add commit parser options for semantic release
  ([`e971576`](https://github.com/NickSalA/ContractAI-Backend/commit/e971576b98ffb8c92c04c2c8366fe8c1a5013e78))


## v0.3.0 (2026-03-20)


## v0.2.1 (2026-03-20)

### Continuous Integration

- Integrate semantic release for automated versioning and changelog generation
  ([`f0a2f5c`](https://github.com/NickSalA/ContractAI-Backend/commit/f0a2f5c4738d30b8aa530b766e58737e0719e36c))

- Reset version to 0.0.0 and adjust semantic release settings
  ([`3efa5c4`](https://github.com/NickSalA/ContractAI-Backend/commit/3efa5c41181e8ceb2a874d86a2948465b7e5c6ec))

- Restructure branches and changelog configuration
  ([`b0db7d7`](https://github.com/NickSalA/ContractAI-Backend/commit/b0db7d73bea718c6efa6ccc58b28b8b5ce16f4cd))

- Streamline semantic release setup in version workflow
  ([`af4dec9`](https://github.com/NickSalA/ContractAI-Backend/commit/af4dec9b7179285714a18a97803ac9d46841006a))

- Update continuous delivery workflow for semantic versioning
  ([`cd9a0f0`](https://github.com/NickSalA/ContractAI-Backend/commit/cd9a0f0b4f44469390c3c8bd3e36faf3691dbe8c))


## v1.0.0 (2026-03-20)

- Initial Release
