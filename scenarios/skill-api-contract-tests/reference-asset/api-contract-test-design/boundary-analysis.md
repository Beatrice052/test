# Boundary Analysis Reference

For each numeric, string, enum, array, date and cross-field rule, consider:

- missing field
- null
- empty string or empty collection
- whitespace-only string
- wrong type
- invalid format
- just below minimum
- exact minimum
- nominal value
- exact maximum
- just above maximum
- excessive length
- timezone or clock boundary where time is involved

If the contract does not define a server clock, normalization rule, retention rule or error schema, create a Contract Gap instead of inventing an expected result.
