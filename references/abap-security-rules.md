# ABAP Security Vulnerabilities Reference

> **Sources integrated from the following authoritative channels:**
> - SAP ABAP Keyword Documentation (`help.sap.com`, official language reference)
> - SAP Community Blog: *How to Protect Your ABAP Code Against SQL Injection*
> - SAP Code Vulnerability Analyzer (CVA) check categories
> - RedRays ABAP Security Scanner 164-rule classification (real-world production vulnerability statistics)
> - CVE-2025-0063, CVE-2025-42957 official disclosures
> - DSAG ABAP Development Recommendations
>
> **Purpose**: This file serves as the authoritative reference for the AI Agent when reviewing code in the `[SEC]` and `[AUTH]` dimensions.

---

## Category Overview

| Category | Code | Severity Range |
|----------|------|----------------|
| SQL Injection | SEC-SQL | CRITICAL |
| Code Injection | SEC-CODE | CRITICAL |
| OS Command Injection | SEC-OS | CRITICAL |
| File Path Attack | SEC-FILE | HIGH–CRITICAL |
| RFC / Network Security | SEC-RFC | HIGH–CRITICAL |
| Missing Authorization | AUTH-MISS | HIGH–CRITICAL |
| Authorization Bypass | AUTH-BYP | CRITICAL |
| Hardcoded Credentials | SEC-CRED | HIGH |
| Sensitive Data Exposure | SEC-DATA | HIGH |
| Web Layer Vulnerabilities | SEC-WEB | HIGH |

---

## SEC-SQL: SQL Injection

### Background

ABAP Open SQL allows dynamic construction of query conditions. When a dynamic part includes **unvalidated input from an external source**, an attacker can inject malicious SQL to alter query logic, access unauthorized data, or modify database content.

*SAP ABAP Keyword Documentation explicitly states:*
> "If a dynamic WHERE condition originates in full or in part from outside the program, users could potentially access data for which they usually do not have authorization."

### Vulnerability Patterns

**[SEC-SQL-1] Dynamic WHERE clause concatenating user input** — 🔴 CRITICAL
```abap
" ❌ Dangerous
PARAMETERS: p_name TYPE string.
DATA(cond) = `NAME = '` && p_name && `'`.
SELECT * FROM scustom WHERE (cond) INTO TABLE @DATA(results).
" Injection example: p_name = "' OR 1=1 --" → returns entire table
```

**[SEC-SQL-2] EXEC SQL (Native SQL) using external input** — 🔴 CRITICAL
```abap
" ❌ Dangerous
EXEC SQL.
  SELECT * FROM zuser WHERE name = :p_name
END-EXEC.
" Native SQL is not protected by Open SQL parameterization
```

**[SEC-SQL-3] ADBC (CL_SQL_STATEMENT) dynamic query** — 🔴 CRITICAL
```abap
" ❌ Dangerous
DATA(sql) = NEW cl_sql_statement( ).
DATA(query) = `SELECT * FROM zdata WHERE id = '` && p_id && `'`.
sql->execute_query( query ).

" ✅ Correct: use parameterized binding
sql->set_param( REF #( p_id ) ).
sql->execute_query( `SELECT * FROM zdata WHERE id = ?` ).
```

**[SEC-SQL-4] EXEC inside AMDP / SQLScript** — 🔴 CRITICAL
```abap
" ❌ Dangerous (inside an AMDP method body)
EXEC 'UPDATE sflight SET seatsocc = seatsocc + ' || :seats;
" Attack example: seats = '2, seatsmax = seatsmax + 999'
```

**[SEC-SQL-5] Dynamic FROM clause (table name from external source)** — 🔴 CRITICAL
```abap
" ❌ Dangerous — table name comes from user input
SELECT * FROM (p_tabname) INTO TABLE @DATA(results).
" Attacker can access any table, including USR02 (password hash table)
```

### Official Remediation

Use the `CL_ABAP_DYN_PRG` class for input validation and escaping:

```abap
" Method 1: QUOTE() — wraps string value in quotes and escapes single quotes
DATA(safe_name) = cl_abap_dyn_prg=>quote( p_name ).
DATA(cond) = `NAME = ` && safe_name.

" Method 2: QUOTE_STR() — returns a quoted string (higher releases)
DATA(safe_cond) = `NAME = ` && cl_abap_dyn_prg=>quote_str( p_name ).

" Method 3: CHECK_TABLE_NAME_STR() — validates table name against a whitelist
cl_abap_dyn_prg=>check_table_name_str(
  val     = p_tabname
  packages = VALUE #( ( `ZPACKAGE` ) ) ).

" Method 4: CHECK_WHITELIST_STR() — whitelist validation for field names
cl_abap_dyn_prg=>check_whitelist_str(
  val       = p_field
  whitelist = `MATNR,WERKS,BUKRS` ).

" Method 5: Use @variable binding instead of literal concatenation (recommended first)
DATA(cond) = `NAME = @p_name`.  " p_name is passed as a parameter, not as SQL code
SELECT * FROM scustom WHERE (cond) INTO TABLE @DATA(results).
```

### Quick-Scan Checklist

When reviewing code, search for the following keywords and evaluate each occurrence:
- `WHERE (` — is the content inside parentheses a variable (dynamic condition)?
- `EXEC SQL` — does external input participate?
- `cl_sql_statement` — is `set_param` parameterization used?
- `GENERATE SUBROUTINE POOL` — is the source validated?
- `INSERT REPORT` — is it controlled by S_DEVELOP authorization?

---

## SEC-CODE: Code Injection

**[SEC-CODE-1] GENERATE SUBROUTINE POOL with external input** — 🔴 CRITICAL
```abap
" ❌ Dangerous — dynamically generates and executes ABAP code
DATA(code) = p_user_input.  " comes from user
GENERATE SUBROUTINE POOL code NAME prog.
" CVE-2025-42957: attacker can execute arbitrary ABAP, create users with SAP_ALL
```

**[SEC-CODE-2] INSERT REPORT without authorization check** — 🔴 CRITICAL
```abap
" ❌ Dangerous
INSERT REPORT p_progname FROM lt_source.
" Must ensure S_DEVELOP OBJTYPE='PROG' ACTVT='01' authorization check is present
```

**[SEC-CODE-3] Dynamic CALL FUNCTION / METHOD / PERFORM** — 🟠 HIGH
```abap
" ❌ Dangerous — function name comes from external source
CALL FUNCTION p_funcname EXPORTING ...
CALL METHOD (p_classname)=>(p_methodname).
PERFORM (p_formname) IN PROGRAM (p_progname).
```

---

## SEC-OS: OS Command Injection

**[SEC-OS-1] CALL 'SYSTEM' with external input** — 🔴 CRITICAL
```abap
" ❌ Dangerous
DATA(cmd) = p_command.  " user input
CALL 'SYSTEM' ID 'COMMAND' FIELD cmd.
```

**[SEC-OS-2] SXPG_COMMAND_EXECUTE with unvalidated input** — 🔴 CRITICAL
```abap
" ❌ Dangerous
CALL FUNCTION 'SXPG_COMMAND_EXECUTE'
  EXPORTING commandname = p_cmd    " should use a predefined command, not free input
            additional_parameters = p_params.
```

**[SEC-OS-3] SXPG_CALL_SYSTEM** — 🔴 CRITICAL

Same as above — all SXPG_* family function calls must have their input source verified.

---

## SEC-FILE: File Path Attack

**[SEC-FILE-1] OPEN DATASET with external input in path** — 🟠 HIGH–🔴 CRITICAL
```abap
" ❌ Dangerous — path traversal risk
DATA(path) = '/data/' && p_filename.
OPEN DATASET path FOR INPUT IN TEXT MODE.
" Attack example: p_filename = '../../etc/passwd'
```

**[SEC-FILE-2] SY-SUBRC not checked after file operation** — 🟠 HIGH
```abap
" ❌ Dangerous — result not checked after file operation
OPEN DATASET lv_path FOR INPUT IN TEXT MODE ENCODING DEFAULT.
READ DATASET lv_path INTO lv_line.  " file may not have been opened successfully

" ✅ Correct
OPEN DATASET lv_path FOR INPUT IN TEXT MODE ENCODING DEFAULT.
IF sy-subrc <> 0.
  RAISE EXCEPTION TYPE cx_file_not_found.
ENDIF.
```

**[SEC-FILE-3] Prefer logical file names** — 🟢 LOW
```abap
" ✅ Define logical file names in transaction FILE; convert using FILE_GET_NAME
CALL FUNCTION 'FILE_GET_NAME'
  EXPORTING logical_filename = 'Z_REPORT_OUTPUT'
  IMPORTING file_name        = lv_physical_path.
```

---

## SEC-RFC: RFC and Network Security

**[SEC-RFC-1] RFC destination from external input** — 🔴 CRITICAL
```abap
" ❌ Dangerous — RFC destination can be manipulated
CALL FUNCTION 'Z_SENSITIVE_FM' DESTINATION p_dest.
" Attacker can point p_dest to a malicious system
```

**[SEC-RFC-2] RFC-enabled FM missing authorization check** — 🔴 CRITICAL
```abap
" ❌ Dangerous — RFC FM with no authorization check
FUNCTION z_delete_records.
  " *"  REMOTE-ENABLED MODULE
  DELETE FROM zdata WHERE id = iv_id.  " any RFC caller can execute this
ENDFUNCTION.
```

**[SEC-RFC-3] MESSAGE TYPE 'A'/'I'/'W' used inside RFC FM** — 🟠 HIGH
```abap
" ❌ Dangerous — dialog messages inside an RFC FM crash the RFC call
FUNCTION z_rfc_fm.
  " *"  REMOTE-ENABLED MODULE
  IF error.
    MESSAGE 'Error occurred' TYPE 'E'.  " throws runtime exception; RFC client cannot catch it
  ENDIF.
ENDFUNCTION.
" ✅ Use EXCEPTIONS parameters to propagate errors instead
```

**[SEC-RFC-4] DESTINATION 'NONE' authorization bypass** — 🔴 CRITICAL
```abap
" ❌ Dangerous — DESTINATION 'NONE' bypasses authorization propagation in certain configurations
CALL FUNCTION 'SENSITIVE_BAPI' DESTINATION 'NONE'.
```

---

## AUTH-MISS: Missing Authorization

### Principle

*SAP explicitly states: SAP doesn't enforce authorization checks at the database level for custom code.*

Therefore, **every operation that reads or modifies sensitive data** requires an explicit AUTHORITY-CHECK.

**[AUTH-MISS-1] No authorization check before reading business-sensitive tables** — 🔴 CRITICAL

High-risk tables (check required):

| Table | Business Context | Recommended Auth Object |
|-------|-----------------|------------------------|
| BKPF / BSEG | FI documents | F_BKPF_BUK, F_BKPF_KOA |
| MKPF / MSEG | MM goods movements | M_MSEG_BWA, M_MSEG_WMB |
| VBAK / VBAP | SD sales orders | V_VBAK_AAT, V_VBAK_VKO |
| EKKO / EKPO | MM purchase orders | M_BEST_BSA, M_BEST_EKG |
| PA* / HRP* | HR personnel data | P_ORGIN, P_PERNR |
| USR* | User master data | S_USER_GRP |
| T001 / T001W | Company code / plant configuration | — |

```abap
" ❌ Dangerous — reading FI documents without authorization check
SELECT * FROM bkpf INTO TABLE @DATA(docs) WHERE bukrs = @p_bukrs.

" ✅ Correct
AUTHORITY-CHECK OBJECT 'F_BKPF_BUK'
  ID 'BUKRS' FIELD p_bukrs
  ID 'ACTVT' FIELD '03'.  " 03 = Display
IF sy-subrc <> 0.
  MESSAGE 'No authorization' TYPE 'E'.
ENDIF.
SELECT * FROM bkpf INTO TABLE @DATA(docs) WHERE bukrs = @p_bukrs.
```

**[AUTH-MISS-2] SY-SUBRC not checked after AUTHORITY-CHECK** — 🔴 CRITICAL
```abap
" ❌ Dangerous — authorization check has no effect
AUTHORITY-CHECK OBJECT 'F_BKPF_BUK'
  ID 'BUKRS' FIELD bukrs
  ID 'ACTVT' FIELD '02'.
" SY-SUBRC is never checked! Any user can continue execution.
UPDATE bkpf SET ...
```

**[AUTH-MISS-3] No authorization check before CALL TRANSACTION** — 🟠 HIGH
```abap
" ❌ Dangerous
CALL TRANSACTION 'FB01' USING bdcdata.

" ✅ Correct
AUTHORITY-CHECK OBJECT 'S_TCODE' ID 'TCD' FIELD 'FB01'.
IF sy-subrc <> 0. RETURN. ENDIF.
CALL TRANSACTION 'FB01' USING bdcdata.
```

**[AUTH-MISS-4] No authorization check before SUBMIT** — 🟠 HIGH
```abap
" ❌ Dangerous — submitting a report directly for execution
SUBMIT zmmr0002 VIA JOB 'BATCH' NUMBER jobno AND RETURN.

" ✅ Check S_PROGRAM or the relevant authorization object first
```

---

## AUTH-BYP: Authorization Bypass

**[AUTH-BYP-1] Using SY-UNAME directly to control access** — 🔴 CRITICAL
```abap
" ❌ Dangerous — hardcoded username acts as "superuser"
IF sy-uname = 'ADMIN' OR sy-uname = 'BASIS'.
  " Skip all checks
  SKIP_AUTHORIZATION = abap_true.
ENDIF.
" SY-UNAME can be spoofed; use AUTHORITY-CHECK instead
```

**[AUTH-BYP-2] Conditional branch based on system ID or client** — 🔴 CRITICAL
```abap
" ❌ Dangerous — backdoor that may be activated in production
IF sy-sysid = 'PRD' AND sy-mandt = '100'.
  AUTHORITY-CHECK OBJECT '...'
ELSE.
  " Skip all authorization checks in development — but what if this code reaches production?
ENDIF.
```

**[AUTH-BYP-3] Wildcard '*' used in authorization object** — 🟠 HIGH
```abap
" ❌ Dangerous — wildcard bypasses precise checking
AUTHORITY-CHECK OBJECT 'M_MSEG_BWA'
  ID 'BWART' FIELD '*'    " * means all movement types — overly broad
  ID 'ACTVT' FIELD '01'.
```

**[AUTH-BYP-4] Dynamic authorization object name** — 🟠 HIGH
```abap
" ❌ Dangerous — authorization object name comes from a variable
DATA(auth_obj) = p_object.
AUTHORITY-CHECK OBJECT (auth_obj) ...
```

---

## SEC-CRED: Hardcoded Credentials

**[SEC-CRED-1] Passwords / keys in source code** — 🟠 HIGH
```abap
" ❌ Dangerous
DATA(password) = 'P@ssw0rd123'.
DATA(api_key)  = 'sk-abcdef1234567890'.
DATA(conn_str) = 'user=admin;pwd=secret'.

" ✅ Use SAP Secure Storage
CALL FUNCTION 'SUSR_USER_AUTH_FOR_RFC_GET'
  " Or use secure credential storage in SM59 RFC destinations
```

**[SEC-CRED-2] Specific username hardcoded** — 🟠 HIGH
```abap
" ❌ Dangerous
CALL FUNCTION 'Z_RFC_FM'
  EXPORTING username = 'BATCHUSER01'
             password = 'Initial1'.
```

---

## SEC-DATA: Sensitive Data Exposure

**[SEC-DATA-1] Personal data written to spool or file without masking** — 🟠 HIGH
```abap
" ❌ Dangerous — ID numbers, bank accounts output in full
WRITE: employee-id_number.
WRITE: vendor-bank_account.

" ✅ Mask at output time
DATA(masked) = '****' && employee-id_number+12(4).
```

**[SEC-DATA-2] Debug messages containing sensitive data** — 🟢 LOW
```abap
" ❌ Avoid
MESSAGE |Debug: user={ sy-uname } pwd={ lv_password }| TYPE 'I'.
```

---

## SEC-WEB: Web Layer Vulnerabilities

> Applicable to BSP, Web Dynpro, ICF Handler, OData DPC Extension, and similar scenarios.

**[SEC-WEB-1] Output not escaped (XSS)** — 🟠 HIGH
```abap
" ❌ Dangerous — BSP directly outputs user input
response->append_cdata( p_input ).

" ✅ Apply HTML escaping
CALL FUNCTION 'ESCAPE_HTML_CHARS'
  EXPORTING unescaped = p_input
  IMPORTING escaped   = lv_safe_output.
```

**[SEC-WEB-2] OData DPC Extension missing backend authorization check** — 🟠 HIGH
```abap
" ❌ Dangerous — hiding a button in Fiori does not constitute security
METHOD zorder_dpc_ext=>orderitem_get_entityset.
  " No AUTHORITY-CHECK; any user with access to the OData service can read this data
  SELECT * FROM vbap INTO TABLE et_entityset.
ENDMETHOD.
```

---

## Priority Quick-Scan Matrix

When reviewing code, scan for the following keywords in this order:

```
Priority 1 — Check immediately (CRITICAL risk):
  EXEC SQL                    → SEC-SQL-2
  GENERATE SUBROUTINE POOL    → SEC-CODE-1
  INSERT REPORT               → SEC-CODE-2
  CALL 'SYSTEM'               → SEC-OS-1
  SXPG_*                      → SEC-OS-2/3
  WHERE (                     → SEC-SQL-1 (dynamic condition)
  DESTINATION (               → SEC-RFC-1 (dynamic destination)

Priority 2 — Important checks (HIGH risk):
  AUTHORITY-CHECK             → SY-SUBRC verified immediately after?
  SELECT ... WHERE (          → is the dynamic WHERE safe?
  OPEN DATASET                → path source; SY-SUBRC checked?
  cl_sql_statement            → set_param used?
  CALL FUNCTION '...' DESTINATION → RFC destination source?
  SY-UNAME =                  → AUTH-BYP-1

Priority 3 — Routine checks (MEDIUM/LOW):
  CALL FUNCTION ... EXCEPTIONS → fully declared + SY-SUBRC checked?
  MESSAGE TYPE                 → no dialog messages inside RFC FMs
  'password'/'key'/'token' literals → SEC-CRED
```

---

## Related CVE References

| CVE | Impact | Pattern | Corresponding Rule |
|-----|--------|---------|-------------------|
| CVE-2025-0063 | SQL Injection (CVSS 9.9) | RFC FM + Informix EXEC SQL + no input validation | SEC-SQL-2 |
| CVE-2025-42957 | Code Injection (/SLOAE/DEPLOY) | RFC FM insufficient parameter validation → GENERATE SUBROUTINE POOL | SEC-CODE-1 |
| CVE-2025-30012 | Deserialization RCE | CL_ABAP_SERIALIZER trusts untrusted byte stream | SEC-CODE |

---

## Tool Reference

| Tool | Coverage | Availability |
|------|---------|-------------|
| SAP Code Vulnerability Analyzer (CVA) | SQL injection, code injection, etc. | Requires additional license |
| ABAP Test Cockpit (ATC) | Basic code quality | Included in standard (no security checks) |
| code-pal-for-ABAP | Clean ABAP rules | Open source, free |
| RedRays ABAP Scanner | 164 security rules | Commercial tool |
| abaplint | Syntax and best practices | Open source, free (CI/CD integration) |

---
*This file consolidates SAP official documentation, security community best practices, and CVE disclosures for use by the AI Agent in static code review.*
*Dynamic runtime behavior, configuration-dependent authorization, and transport environment differences are outside the scope of this file.*
