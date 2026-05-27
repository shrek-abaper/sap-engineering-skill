# Clean ABAP Rules Reference

> **Source**: SAP official open-source style guide — `github.com/SAP/styleguides/clean-abap/CleanABAP.md`
> **License**: CC BY 4.0 (open use with attribution)
> **Purpose**: This file serves as the authoritative reference for the AI Agent when reviewing code in the `[STD]` dimension.
> **Scope**: Excerpts focused on the rules most valuable for pre-release assessment. For the full specification, refer to the original repository.

---

## 1. Names

### Priority Levels
Clean ABAP categorizes naming rules into three severity levels:
- **Critical**: Directly affects readability and maintainability; violations should be flagged as 🟠 HIGH
- **Major**: Reduces code understandability; violations should be flagged as 🟡 MEDIUM
- **Minor**: Incremental improvements; violations should be flagged as 🟢 LOW

### Core Rules

**[N-1] Use descriptive names, not abbreviations** *(Major)*
```abap
" ❌ Bad
DATA: flnm TYPE string.
DATA: cnt TYPE i.

" ✅ Good
DATA: file_name TYPE string.
DATA: entry_count TYPE i.
```
*Official basis: "Use intention-revealing names. Reveal the purpose."*

**[N-2] Use one word per concept** *(Major)*
```abap
" ❌ Bad — same concept expressed three different ways
" get_data(), fetch_info(), retrieve_records()

" ✅ Good — consistent terminology
" get_order(), get_delivery(), get_invoice()
```

**[N-3] Classes as nouns, methods as verbs** *(Major)*
```abap
" ❌ Bad
CLASS check IMPLEMENTATION.   " unclear what is being checked
METHOD material TYPE string.  " should be a verb

" ✅ Good
CLASS material_validator IMPLEMENTATION.
METHOD validate_material_number.
```

**[N-4] Avoid encoding prefixes (Hungarian notation)** *(Minor)*
```abap
" ❌ Bad — old-style Hungarian prefixes (still common in legacy code)
DATA: lv_name TYPE string.
DATA: lt_orders TYPE orders_table.
DATA: lo_handler TYPE REF TO cl_handler.

" ✅ SAP Clean ABAP recommended direction (modern code)
DATA: name TYPE string.
DATA: orders TYPE orders_table.
DATA: handler TYPE REF TO cl_handler.
```
> ⚠️ **Review note**: Prefixes are extremely common in legacy systems. This rule does **not** mandate a full refactor.
> Flag as LOW only when new code mixes old and new styles.

**[N-5] Avoid meaningless words** *(Major)*
```abap
" ❌ Bad
DATA: data TYPE string.
DATA: info TYPE string.
DATA: flag TYPE abap_bool.  " "flag" does not say what it flags

" ✅ Good
DATA: customer_name TYPE string.
DATA: payment_overdue TYPE abap_bool.
```

---

## 2. Language

**[L-1] Prefer object-oriented over procedural** *(Major)*
```abap
" ❌ Bad — avoid FORM in new code
FORM calculate_total USING iv_amount TYPE dmbtr.

" ✅ Good
CLASS order_calculator DEFINITION.
  METHODS calculate_total IMPORTING amount TYPE dmbtr.
ENDCLASS.
```
*Official basis: "SAP postulates non-OO code modules as obsolete. Use FMs only where classes cannot be used (RFC, update modules)."*

**[L-2] Prefer functional language constructs** *(Minor)*
```abap
" ❌ Bad
DATA result TYPE i.
result = 1 + 2.

" ✅ Good
DATA(result) = 1 + 2.
```

**[L-3] Avoid deprecated statements** *(Major)*

| Deprecated | Modern Alternative |
|-----------|-------------------|
| `MOVE a TO b` | `b = a` |
| `COMPUTE x = y + z` | `x = y + z` |
| `WRITE val TO str` | `str = \|{ val }\|` or type conversion |
| `REFRESH itab` | `CLEAR itab` |
| `FREE itab` | `CLEAR itab` or `FREE itab` (only when releasing memory is needed) |
| `MULTIPLY x BY y` | `x = x * y` |
| `DIVIDE x BY y` | `x = x / y` |
| `ADD x TO y` | `y = y + x` |

**[L-4] Use inline declarations** *(Minor)*
```abap
" ❌ Bad
DATA result TYPE dmbtr.
SELECT SINGLE amount INTO result FROM bkpf WHERE ...

" ✅ Good
SELECT SINGLE amount INTO @DATA(result) FROM bkpf WHERE ...
```

**[L-5] Avoid obsolete type conversions** *(Major)*
```abap
" ❌ Bad — implicit truncation risk
MOVE long_string TO short_char20.

" ✅ Good — explicit conversion with intent
short_char20 = CONV char20( long_string ).  " explicit, with compile-time checks
```

---

## 3. Constants

**[C-1] Replace magic numbers and literals with constants** *(Major)*
```abap
" ❌ Bad — magic number / literal, meaning unclear
IF status = 'E'.
IF amount > 999999.

" ✅ Good
CONSTANTS: c_status_error TYPE char1 VALUE 'E'.
CONSTANTS: c_max_amount   TYPE dmbtr VALUE 999999.
IF status = c_status_error.
```

**[C-2] Manage related constants with enumeration classes** *(Minor)*
```abap
" ✅ Recommended pattern
CLASS order_status DEFINITION ABSTRACT FINAL.
  PUBLIC SECTION.
    CONSTANTS:
      open      TYPE char1 VALUE 'O',
      confirmed TYPE char1 VALUE 'C',
      cancelled TYPE char1 VALUE 'X'.
ENDCLASS.
```

**[C-3] No hardcoded business configuration values** *(Major → typically HIGH in enterprise settings)*
```abap
" ❌ Bad — hardcoded company code, plant, client
IF bukrs = '1000'.
IF werks = 'SH01'.
DATA(mandt) = '100'.

" ✅ Good — retrieve via parameters, configuration tables, or SY-MANDT
IF bukrs = iv_bukrs.
IF werks IN s_werks.
DATA(mandt) = sy-mandt.
```

---

## 4. Variables

**[V-1] Declare variables in the narrowest possible scope** *(Minor)*
```abap
" ❌ Bad — all variables declared at the top of the method
METHOD process.
  DATA: name TYPE string.
  DATA: amount TYPE dmbtr.
  DATA: flag TYPE abap_bool.
  " ...flag is not used until 100 lines later

" ✅ Good — declare close to the point of use
METHOD process.
  DATA(name) = get_name( ).
  DATA(amount) = calculate( name ).
```

**[V-2] Do not reuse variables for different purposes** *(Major)*
```abap
" ❌ Bad — result used first for row count, then for an amount
DATA: result TYPE i.
result = lines( orders ).
" ...
result = calculate_amount( ).  " completely different semantics
```

---

## 5. Tables

**[T-1] Choose the appropriate internal table type** *(Major)*

| Use Case | Recommended Type | Reason |
|---------|-----------------|--------|
| Sequential processing, sorted iteration | `STANDARD TABLE` | Fast insert |
| Frequent key-based reads (READ TABLE) | `SORTED TABLE` | O(log n) |
| Heavy random key lookups | `HASHED TABLE` | O(1) |

```abap
" ❌ Bad — READ TABLE WITH KEY on STANDARD TABLE inside loop
LOOP AT orders.
  READ TABLE details WITH KEY order_id = orders-id INTO DATA(detail).
ENDLOOP.  " O(n²) complexity

" ✅ Good — use HASHED TABLE or SORTED TABLE
DATA details TYPE HASHED TABLE OF detail_s WITH UNIQUE KEY order_id.
```

**[T-2] Avoid SELECT inside a loop** *(Critical)*
```abap
" ❌ Bad — classic 1+N query, fatal in production
LOOP AT orders INTO DATA(order).
  SELECT SINGLE * FROM vbap INTO DATA(item)
    WHERE vbeln = order-vbeln.  " one DB call per order
ENDLOOP.

" ✅ Good — SELECT ... FOR ALL ENTRIES, then join in memory
SELECT * FROM vbap INTO TABLE @DATA(items)
  FOR ALL ENTRIES IN @orders
  WHERE vbeln = @orders-vbeln.
```

**[T-3] Use projection instead of SELECT \*** *(Major)*
```abap
" ❌ Bad
SELECT * FROM bkpf INTO TABLE @DATA(docs).

" ✅ Good
SELECT bukrs, belnr, gjahr, bldat
  FROM bkpf INTO TABLE @DATA(docs)
  WHERE bukrs = @bukrs.
```

---

## 6. Strings

**[S-1] Use template literals for string concatenation** *(Minor)*
```abap
" ❌ Bad
CONCATENATE first_name ' ' last_name INTO full_name.

" ✅ Good
DATA(full_name) = |{ first_name } { last_name }|.
```

**[S-2] Be aware of trailing spaces in string comparisons** *(Major)*
```abap
" ❌ Error-prone — CHAR type has trailing spaces
DATA: name TYPE char20 VALUE 'SAP'.
IF name = 'SAP'.  " equivalent to 'SAP                 '

" ✅ Use STRING type or explicit CONDENSE
DATA: name TYPE string VALUE 'SAP'.
```

---

## 7. Booleans

**[B-1] Use ABAP_BOOL instead of numeric flags** *(Major)*
```abap
" ❌ Bad
DATA: is_valid TYPE i.
is_valid = 1.
IF is_valid = 1.

" ✅ Good
DATA: is_valid TYPE abap_bool.
is_valid = abap_true.
IF is_valid = abap_true.
```

**[B-2] Use predicate methods to express boolean intent** *(Minor)*
```abap
" ❌ Bad
IF status = 'E' OR status = 'X' OR status = 'A'.

" ✅ Good
IF is_error_status( status ).
```

---

## 8. Conditions

**[CO-1] Avoid negated conditions** *(Minor)*
```abap
" ❌ Bad — double negation is hard to parse
IF NOT is_not_valid.

" ✅ Good
IF is_valid.
```

**[CO-2] Extract complex conditions into methods** *(Major)*
```abap
" ❌ Bad — compound condition is hard to follow
IF status = 'E' AND amount > 0 AND bukrs = '1000' AND NOT blocked.

" ✅ Good
IF is_eligible_for_posting( status = status amount = amount ).
```

---

## 9. Methods

**[M-1] A method should do one thing only** *(Critical)*
```abap
" ❌ Bad — method name implies multiple responsibilities
METHOD validate_and_save_and_notify.

" ✅ Good — separate concerns
METHOD validate_order.
METHOD save_order.
METHOD notify_stakeholders.
```

**[M-2] Keep methods short (ideally 3–5 statements; upper limit 20 lines)** *(Major)*

*Official basis: "Keep methods short. If a method is more than 20 statements, think of splitting it."*

**[M-3] No more than 3 IMPORTING parameters** *(Major)*
```abap
" ❌ Bad
METHODS calculate
  IMPORTING bukrs TYPE bukrs
            belnr TYPE belnr_d
            gjahr TYPE gjahr
            koart TYPE koart
            waers TYPE waers.

" ✅ Good — encapsulate with a structure
METHODS calculate
  IMPORTING document TYPE document_key_s.
```

**[M-4] Use RETURNING instead of EXPORTING** *(Minor)*
```abap
" ❌ Bad
METHODS get_total
  EXPORTING ev_total TYPE dmbtr.

" ✅ Good
METHODS get_total
  RETURNING VALUE(result) TYPE dmbtr.
```

**[M-5] Avoid mixing EXPORTING and RETURNING** *(Major)*

---

## 10. Error Handling

**[E-1] Use class-based exceptions instead of classic exceptions** *(Major)*
```abap
" ❌ Bad — classic exceptions (obsolete)
CALL FUNCTION 'Z_FM'
  EXCEPTIONS
    not_found = 1
    OTHERS    = 2.

" ✅ Good — class-based exceptions
TRY.
  z_object->execute( ).
CATCH cx_not_found INTO DATA(ex).
  " handle exception
ENDTRY.
```

**[E-2] SY-SUBRC must be checked after CALL FUNCTION** *(Critical)*
```abap
" ❌ Bad — return code ignored
CALL FUNCTION 'Z_PROCESS_ORDER'
  EXPORTING iv_order = lv_order.
" Continues immediately without knowing if it succeeded

" ✅ Good
CALL FUNCTION 'Z_PROCESS_ORDER'
  EXPORTING iv_order   = lv_order
  EXCEPTIONS not_found = 1
             OTHERS    = 2.
IF sy-subrc <> 0.
  RAISE EXCEPTION TYPE cx_processing_failed.
ENDIF.
```

**[E-3] Do not swallow exceptions** *(Critical)*
```abap
" ❌ Bad — exception caught and silently ignored
TRY.
  risky_operation( ).
CATCH cx_root.            " catches everything and discards it
ENDTRY.

" ✅ Good
TRY.
  risky_operation( ).
CATCH cx_specific_error INTO DATA(ex).
  log_error( ex ).
  RAISE EXCEPTION TYPE cx_outer_error
    EXPORTING previous = ex.
ENDTRY.
```

**[E-4] CX_STATIC_CHECK vs. CX_DYNAMIC_CHECK** *(Major)*

| Type | When to Use |
|------|------------|
| `CX_STATIC_CHECK` | Expected errors the caller **can reasonably handle** (e.g. file not found) |
| `CX_DYNAMIC_CHECK` | Programming errors (e.g. null pointer); callers cannot prevent them in advance |
| `CX_NO_CHECK` | Serious system errors; should not be handled in business code |

---

## 11. Comments

**[CM-1] Express intent through code, not comments** *(Major)*
```abap
" ❌ Bad — comment explains what the code does (the code itself should be clear)
" Check if the order is valid
IF status = 'C' AND amount > 0.

" ✅ Good — self-documenting code
IF is_confirmed_order( status ) AND has_amount( amount ).
```

**[CM-2] Comments explain "why", not "what"** *(Minor)*
```abap
" ✅ Good comment — explains the business reason
" SAP Note 2847563: FI posting requires BKPF lock before BSEG update
" to prevent duplicate document numbers in concurrent sessions
CALL FUNCTION 'ENQUEUE_EFIBL'.
```

**[CM-3] Commented-out code must not reach production** *(Major)*
```abap
" ❌ Bad — stale commented-out code
* DATA: old_var TYPE string.
* PERFORM old_routine.
```

---

## 12. Formatting

**[F-1] One statement per line** *(Major)*
```abap
" ❌ Bad
DATA: a TYPE i. DATA: b TYPE i.

" ✅ Good
DATA: a TYPE i.
DATA: b TYPE i.
```

**[F-2] Use Pretty Printer for consistent formatting** *(Minor)*

SAP officially recommends running Pretty Printer every time code is saved (configurable in SE38/SE80).

---

## 13. Testing

**[TS-1] Write ABAP Unit Tests** *(Major)*

*Official basis: "Untested code is broken code. Write unit tests."*

Key checkpoints:
- Is there a corresponding test class (`*_TEST` or a separate test include)?
- Are critical business logic paths covered by tests?
- Do tests use Test Doubles / Mocks instead of real DB calls?

**[TS-2] Separate test code from production code** *(Minor)*
```abap
" ✅ Correct — use FOR TESTING designation
CLASS order_validator_test DEFINITION
  FOR TESTING RISK LEVEL HARMLESS DURATION SHORT.
```

---

## Reference Links

| Resource | URL |
|----------|-----|
| Clean ABAP Style Guide (official full version) | `github.com/SAP/styleguides/blob/main/clean-abap/CleanABAP.md` |
| ABAP Code Review Guideline | `github.com/SAP/styleguides/blob/main/abap-code-review/ABAPCodeReview.md` |
| code-pal-for-ABAP (automated checks) | `github.com/SAP/code-pal-for-abap` |
| ABAP Cleaner (100+ auto-fix rules) | `github.com/SAP/abap-cleaner` |

---
*This file is a review-oriented excerpt of the SAP official Clean ABAP Style Guide, for use by the AI Agent in the [STD] dimension.*
*The original specification is published under CC BY 4.0; copyright belongs to SAP SE and its contributors.*
