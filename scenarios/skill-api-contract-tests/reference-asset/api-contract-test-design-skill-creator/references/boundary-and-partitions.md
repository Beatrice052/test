# Boundary And Partitions

Use this reference to derive test cases from explicit contract rules.

## Generic Partitions

For each request field, consider these only when relevant to the declared type and rule:

- missing field
- explicit null
- empty string
- whitespace-only string
- wrong type
- invalid format
- valid representative value
- duplicate value where uniqueness matters
- maximum allowed boundary
- just above maximum
- minimum allowed boundary
- just below minimum

## Numeric Fields

For numeric limits, include:

- missing and null
- non-numeric string
- negative value
- zero when minimum is positive
- minimum minus the smallest meaningful unit
- exact minimum
- typical valid value
- exact maximum
- maximum plus the smallest meaningful unit
- unsupported precision
- scientific notation as a Contract Gap if not specified

## Enums

For enum fields, include:

- each supported value
- lowercase or mixed-case value
- unknown value
- empty string
- null
- whitespace

Do not assume case-insensitive behavior unless the contract says so.

## Timestamps

For timestamp rules, include:

- missing and null when optional
- invalid timestamp format
- timestamp in the past
- exact current time
- just after current time
- exact maximum future boundary
- just beyond maximum future boundary
- different valid timezone offsets
- server-clock definition as a Contract Gap if not specified

## Cross-Field Rules

For relationships between fields, include:

- both valid and distinct
- same value where disallowed
- source missing
- destination missing
- one valid and one unauthorized
- mismatched data ownership or tenant boundary when relevant
