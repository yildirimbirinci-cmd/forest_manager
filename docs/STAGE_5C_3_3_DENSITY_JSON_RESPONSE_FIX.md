# Stage 5C.3.3 - Density JSON Response Fix

Observed runtime failure:

    JSONDecodeError: Expecting property name enclosed in double quotes

Root cause:
The SET_DENSITY_METERS command returned a response string with double-escaped
quote characters. The TCP payload therefore started like:

    {\"ok\":true,...

instead of valid JSON:

    {"ok":true,...

Fix:
- only the response wrapper escaping was corrected;
- the requested density remains exactly 75.0 meters by default;
- no density rescaling, substitution, or experimentation was added;
- the CLI now includes the raw bridge payload if JSON decoding fails again.

Bridge version: 0.9.10
